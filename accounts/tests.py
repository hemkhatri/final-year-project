import json
from decimal import Decimal
from unittest.mock import patch, MagicMock
import requests

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import DeliveryBoyProfile, SellerProfile, CustomerProfile, Order, AssignmentAttempt
from accounts.services import auto_assign_order, assign_next_delivery_boy
from accounts.tasks import check_assignment_timeout

User = get_user_model()


class AccountsSystemTestCase(TestCase):
    def setUp(self):
        # Fallback Configurations for URLs
        if not hasattr(settings, 'SITE_URL'):
            settings.SITE_URL = "http://testserver"

        # 1. Create Core Mock Users
        self.customer_user = User.objects.create_user(
            username="customer_john", email="john@test.com", password="password123", role=User.Role.CUSTOMER
        )
        self.seller_user = User.objects.create_user(
            username="seller_jack", email="jack@test.com", password="password123", role=User.Role.SELLER
        )
        self.delivery_user_1 = User.objects.create_user(
            username="rider_alpha", email="alpha@test.com", password="password123", role=User.Role.DELIVERY_BOY
        )
        self.delivery_user_2 = User.objects.create_user(
            username="rider_beta", email="beta@test.com", password="password123", role=User.Role.DELIVERY_BOY
        )

        # 2. Configure Delivery Profiles and Coordinates
        self.profile_1 = self.delivery_user_1.delivery_profile
        self.profile_1.latitude = Decimal("27.700769")
        self.profile_1.longitude = Decimal("85.300140")
        self.profile_1.is_available = True
        self.profile_1.is_busy = False
        self.profile_1.save()

        self.profile_2 = self.delivery_user_2.delivery_profile
        self.profile_2.latitude = Decimal("27.717245")
        self.profile_2.longitude = Decimal("85.323960")
        self.profile_2.is_available = True
        self.profile_2.is_busy = False
        self.profile_2.save()

        # 3. Instantiate Orders
        self.order = Order.objects.create(
            customer=self.customer_user,
            delivery_latitude=Decimal("27.701000"),
            delivery_longitude=Decimal("85.301000"),
            status=Order.Status.PLACED
        )

    # ==========================================
    # VIEW ROUTING & DASHBOARD INTERFACES
    # ==========================================

    def test_smart_login_redirect_routing(self):
        """Users should route to specific sub-dashboards matching their instance role maps."""
        self.client.force_login(self.delivery_user_1)
        response = self.client.get('/accounts/dashboard/delivery/')
        self.assertEqual(response.status_code, 200)

    def test_seller_dashboard_restrictions_and_context(self):
        """Seller context should provide listings data, categories, and block customer role entries."""
        self.client.force_login(self.customer_user)
        response = self.client.get(reverse('accounts:seller_dashboard'))
        self.assertEqual(response.status_code, 403)  # Blocked via UserPassesTestMixin

        self.client.force_login(self.seller_user)
        response = self.client.get(reverse('accounts:seller_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('category_tree_json', response.context)
        self.assertIn('active_listings', response.context)

    # ==========================================
    # WORKSPACE ACTION & ASSIGNMENT FLOWS
    # ==========================================

    def test_rider_accept_delivery_view_flow(self):
        """Executing assignment acceptance locks down current delivery profile tracking metrics."""
        attempt = AssignmentAttempt.objects.create(
            order=self.order, driver=self.delivery_user_1, status=AssignmentAttempt.Status.PENDING
        )
        self.client.force_login(self.delivery_user_1)
        
        response = self.client.get(reverse('accounts:accept_delivery', args=[attempt.id]))
        self.assertRedirects(response, '/accounts/dashboard/delivery/')
        
        # Verify Mutated Data States
        self.order.refresh_from_db()
        self.profile_1.refresh_from_db()
        attempt.refresh_from_db()

        self.assertEqual(self.order.status, Order.Status.ACCEPTED)
        self.assertEqual(self.order.current_delivery_boy, self.delivery_user_1)
        self.assertTrue(self.profile_1.is_busy)
        self.assertEqual(attempt.status, AssignmentAttempt.Status.ACCEPTED)

    # We patch accounts.views because that's where the request lifecycle hits the method reference!
    @patch('accounts.views.auto_assign_order')
    def test_rider_reject_delivery_triggers_reassignment_loop(self, mock_auto_assign):
        """Rejecting an order opens rider tracking flags and boots re-assignment algorithms."""
        attempt = AssignmentAttempt.objects.create(
            order=self.order, driver=self.delivery_user_1, status=AssignmentAttempt.Status.PENDING
        )
        self.client.force_login(self.delivery_user_1)
        
        response = self.client.get(reverse('accounts:reject_delivery', args=[attempt.id]))
        
        self.order.refresh_from_db()
        self.profile_1.refresh_from_db()
        attempt.refresh_from_db()

        self.assertEqual(attempt.status, AssignmentAttempt.Status.REJECTED)
        self.assertFalse(self.profile_1.is_busy)
        self.assertIn(self.delivery_user_1, self.order.rejected_by.all())
        mock_auto_assign.assert_called_once_with(self.order.id)

    # ==========================================
    # CORE MATH & ALGORITHM SERVICE LAYERS
    # ==========================================

    @patch('accounts.services.send_mail')
    def test_auto_assign_finds_closest_driver(self, mock_send_mail):
        """The auto assignment algorithm should process haversine/spherical distance parameters accurately."""
        success = auto_assign_order(self.order.id)
        self.assertTrue(success)

        self.order.refresh_from_db()
        self.assertEqual(self.order.current_delivery_boy, self.delivery_user_1)
        self.assertEqual(self.order.status, Order.Status.ASSIGNING)
        mock_send_mail.assert_called_once()

    # ==========================================
    # API ENDPOINTS & MAP GEOMETRY TELEMETRY
    # ==========================================

    def test_update_rider_location_telemetry(self):
        """Verifies incoming AJAX tracking tokens write clean lat/long pairs to target profiles."""
        self.client.force_login(self.delivery_user_1)
        payload = {"latitude": 27.123456, "longitude": 85.654321}
        
        response = self.client.post(
            reverse('accounts:update_rider_location'),
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        self.profile_1.refresh_from_db()
        self.assertEqual(float(self.profile_1.latitude), 27.123456)

    @patch('accounts.views.requests.get')
    def test_get_delivery_route_osrm_integration(self, mock_get):
        """Verifies that OSRM geometry payloads unpack neatly into client-ready dictionary coordinates."""
        self.client.force_login(self.delivery_user_1)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "routes": [
                {
                    "geometry": {"type": "LineString", "coordinates": [[85.30, 27.70], [85.31, 27.71]]},
                    "duration": 600,
                    "distance": 5000
                }
            ]
        }
        mock_get.return_value = mock_response

        response = self.client.get(reverse('accounts:get_delivery_route', args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['distance_km'], 5.0)
        self.assertEqual(data['duration_mins'], 10.0)

    # ==========================================
    # BACKGROUND TASK EXECUTION (CELERY MOCKS)
    # ==========================================

    @patch('accounts.tasks.auto_assign_order')
    def test_check_assignment_timeout_purges_lazy_riders(self, mock_auto_assign):
        """If 20-minute windows lapse with a pending response, automatically skip current rider target records."""
        self.order.current_delivery_boy = self.delivery_user_1
        self.order.status = Order.Status.ASSIGNING
        self.order.save()

        attempt = AssignmentAttempt.objects.create(
            order=self.order, driver=self.delivery_user_1, status=AssignmentAttempt.Status.PENDING
        )

        check_assignment_timeout(attempt.id)

        attempt.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(attempt.status, AssignmentAttempt.Status.TIMEOUT)
        self.assertIn(self.delivery_user_1, self.order.rejected_by.all())
        self.assertIsNone(self.order.current_delivery_boy)
        mock_auto_assign.assert_called_once_with(self.order.id)