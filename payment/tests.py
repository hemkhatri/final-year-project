import base64
import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cart.cart import Cart
from shop.models import Category, Product
from payment.models import Order, OrderItem
from accounts.models import Order as DeliveryOrder

User = get_user_model()


class PaymentViewsTestCase(TestCase):
    def setUp(self):
        # 1. Ensure a fallback session ID exists for testing the Cart
        if not hasattr(settings, 'CART_SESSION_ID'):
            settings.CART_SESSION_ID = 'cart'

        # 2. Setup users with appropriate roles
        self.buyer = User.objects.create_user(
            username='buyer_user', 
            password='testpassword123', 
            role=User.Role.CUSTOMER
        )
        self.seller = User.objects.create_user(
            username='seller_user', 
            password='testpassword123', 
            role=User.Role.SELLER
        )

        # 3. Setup shop setup prerequisite models
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name='Test Smartphone',
            slug='test-smartphone',
            price=Decimal('15000.00'),
            stock=10,
            available=True
        )

        # 4. Target View URLs
        self.checkout_url = reverse('payment:checkout_preview')
        self.success_url = reverse('payment:payment_success')
        self.failure_url = reverse('payment:payment_failure')

    def add_item_to_session_cart(self):
        """Helper to populate the session-based cart with a product."""
        session = self.client.session
        session[settings.CART_SESSION_ID] = {
            str(self.product.id): {
                'quantity': 2,
                'price': str(self.product.price)
            }
        }
        session.save()

    def generate_esewa_mock_data(self, transaction_uuid, status="COMPLETE"):
        """Helper to mimic eSewa's base64 encoded JSON response payload."""
        response_dict = {
            "status": status,
            "transaction_uuid": transaction_uuid,
            "total_amount": "30000.00",
            "transaction_code": "MOCK_TX_CODE"
        }
        json_str = json.dumps(response_dict)
        encoded_payload = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        return encoded_payload

    # ==========================================
    # CHECKOUT PREVIEW VIEW TESTS
    # ==========================================

    def test_checkout_preview_requires_login(self):
        """Ensure unauthenticated users are redirected to login."""
        response = self.client.get(self.checkout_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)  # Or your app's login path

    def test_checkout_preview_redirects_if_cart_empty(self):
        """Ensure users are booted back to cart details if the cart is empty."""
        self.client.login(username='buyer_user', password='testpassword123')
        response = self.client.get(self.checkout_url)
        self.assertRedirects(response, reverse('cart:cart_detail'))

    def test_checkout_preview_get_with_items(self):
        """Ensure GET request works perfectly when cart contains items."""
        self.client.login(username='buyer_user', password='testpassword123')
        self.add_item_to_session_cart()
        
        response = self.client.get(self.checkout_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payment/checkout.html')
        self.assertIn('cart_items', response.context)
        self.assertEqual(response.context['total_price'], Decimal('30000.00'))

    def test_checkout_preview_post_missing_coordinates(self):
        """POST request should fail if latitude or longitude map picker data is missing."""
        self.client.login(username='buyer_user', password='testpassword123')
        self.add_item_to_session_cart()

        post_data = {
            'shipping_name': 'John Doe',
            'shipping_address': 'Kathmandu, Nepal',
            'phone_number': '9841000000',
            'latitude': '',  # Empty lat
            'longitude': '85.3240'
        }
        response = self.client.post(self.checkout_url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('❌ Please select delivery location on the map', response.context['error'])

    def test_checkout_preview_post_invalid_coordinates(self):
        """POST request should render an error if coordinate casting fails."""
        self.client.login(username='buyer_user', password='testpassword123')
        self.add_item_to_session_cart()

        post_data = {
            'shipping_name': 'John Doe',
            'shipping_address': 'Kathmandu, Nepal',
            'phone_number': '9841000000',
            'latitude': 'not-a-decimal-lat',
            'longitude': '85.3240'
        }
        response = self.client.post(self.checkout_url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('❌ Invalid coordinates', response.context['error'])

    def test_checkout_preview_post_success_creates_order_and_signature(self):
        """Successful POST should build objects and return correct eSewa params/signature."""
        self.client.login(username='buyer_user', password='testpassword123')
        self.add_item_to_session_cart()

        post_data = {
            'shipping_name': 'Hari Bahadur',
            'shipping_address': 'Pokhara, Nepal',
            'phone_number': '9856000000',
            'latitude': '28.2096',
            'longitude': '83.9856'
        }
        
        # Verify database starts empty
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

        response = self.client.post(self.checkout_url, data=post_data)
        self.assertEqual(response.status_code, 200)
        
        # Check order and item creations
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        
        created_order = Order.objects.first()
        self.assertEqual(created_order.buyer, self.buyer)
        self.assertEqual(created_order.status, 'PENDING')
        self.assertEqual(created_order.total_amount, Decimal('30000.00'))

        # Check cryptographic context outputs passed back to checkout.html
        self.assertIn('signature', response.context)
        self.assertEqual(response.context['formatted_amount'], "30000.00")
        self.assertEqual(response.context['product_code'], "EPAYTEST")

    # ==========================================
    # PAYMENT SUCCESS VIEW TESTS
    # ==========================================

    def test_payment_success_missing_data(self):
        """GET request without a ?data parameter returns a 400 response."""
        response = self.client.get(self.success_url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode(), "Missing eSewa transaction response data.")

    def test_payment_success_not_complete_status(self):
        """If eSewa sends a response status other than COMPLETE, reject it."""
        mock_uuid = "ORDER-999-XXXXXX"
        encoded_data = self.generate_esewa_mock_data(transaction_uuid=mock_uuid, status="CANCELED")
        
        response = self.client.get(f"{self.success_url}?data={encoded_data}")
        self.assertEqual(response.status_code, 400)
        self.assertIn("eSewa payment transaction was not complete.", response.content.decode())

    @patch('payment.views.auto_assign_order')
    def test_payment_success_complete_lifecycle(self, mock_auto_assign):
        """Verifies eSewa COMPLETE upgrades order state, clears cart, creates a DeliveryOrder, and dispatches driver assignment."""
        # Setup mock behavior for service function
        mock_auto_assign.return_value = True

        # Generate a model-valid database pending order structure
        shop_order = Order.objects.create(
            buyer=self.buyer,
            shipping_name="Sita Thapa",
            shipping_address="Lalitpur",
            phone_number="9801000000",
            delivery_latitude=Decimal('27.6744'),
            delivery_longitude=Decimal('85.3240'),
            total_amount=Decimal('30000.00'),
            status='PENDING',
            transaction_uuid="ORDER-1-MOCK"
        )
        shop_order.transaction_uuid = f"ORDER-{shop_order.id}-ABCDEF"
        shop_order.save()

        # Place fake contents into user session cart to prove it gets flushed out
        self.add_item_to_session_cart()
        self.assertEqual(len(Cart(self.client)), 2)

        encoded_data = self.generate_esewa_mock_data(transaction_uuid=shop_order.transaction_uuid, status="COMPLETE")

        # Execute GET request to landing path
        response = self.client.get(f"{self.success_url}?data={encoded_data}")
        self.assertEqual(response.status_code, 200)
        self.strip_template_spaces = True
        self.assertTemplateUsed(response, 'payment/success.html')

        # 1. Assert shop order update conditions
        shop_order.refresh_from_db()
        self.assertEqual(shop_order.status, 'ASSIGNING')
        self.assertIn('-DELIVERY-', shop_order.transaction_uuid)

        # 2. Assert session cart gets dropped cleanly
        self.assertEqual(len(Cart(self.client)), 0)

        # 3. Assert DeliveryOrder record generation inside accounts app
        self.assertEqual(DeliveryOrder.objects.count(), 1)
        del_order = DeliveryOrder.objects.first()
        self.assertEqual(del_order.customer, self.buyer)
        self.assertEqual(del_order.status, DeliveryOrder.Status.PLACED)
        self.assertEqual(del_order.delivery_latitude, shop_order.delivery_latitude)

        # 4. Verify auto assignment service execution trigger
        mock_auto_assign.assert_called_once_with(del_order.id)
        self.assertTrue(response.context['assigned_success'])

    @patch('payment.views.auto_assign_order')
    def test_payment_success_graceful_on_assignment_crash(self, mock_auto_assign):
        """Verifies that if auto_assign_order raises an Exception, the payment transaction still succeeds safely."""
        mock_auto_assign.side_effect = Exception("Notification layer failure mock configuration crash")

        shop_order = Order.objects.create(
            buyer=self.buyer,
            shipping_name="Gopal Prasad",
            shipping_address="Butwal",
            delivery_latitude=Decimal('27.7006'),
            delivery_longitude=Decimal('83.4484'),
            total_amount=Decimal('15000.00'),
            status='PENDING'
        )
        shop_order.transaction_uuid = f"ORDER-{shop_order.id}-WXYZ"
        shop_order.save()

        encoded_data = self.generate_esewa_mock_data(transaction_uuid=shop_order.transaction_uuid, status="COMPLETE")
        
        # Executing should NOT trigger a 400 error because the try/except block wraps the assignment function
        response = self.client.get(f"{self.success_url}?data={encoded_data}")
        self.assertEqual(response.status_code, 200)
        
        shop_order.refresh_from_db()
        self.assertEqual(shop_order.status, 'ASSIGNING')  # Payment still went through perfectly
        self.assertFalse(response.context['assigned_success'])

    # ==========================================
    # PAYMENT FAILURE VIEW TESTS
    # ==========================================

    def test_payment_failure_view(self):
        """Ensure failure template lands cleanly."""
        response = self.client.get(self.failure_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payment/failure.html')