import os
import requests
import json
import logging
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, CreateView, ListView
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .forms import CustomUserCreationForm
from .models import DeliveryBoyProfile, Order, AssignmentAttempt
from .services import auto_assign_order, assign_next_delivery_boy
from shop.models import Product, Category
from django.contrib.auth import get_user_model
from django.views.generic import CreateView
from .admin_contact import SupportTicketForm
from .models import SupportTicket

User = get_user_model()
logger = logging.getLogger(__name__)

@login_required
def smart_login_redirect(request):
    """Smart routing post-authentication based on institutional operational roles."""
    user = request.user

    if user.role == "DELIVERY_BOY":
        return redirect('accounts:delivery_dashboard')
    elif user.role == "SELLER":
        return redirect('accounts:seller_dashboard')
    elif user.role == "ADMIN":
        return redirect('accounts:admin_dashboard')
    else:
        # Fallback routing destination for regular consumers/customers
        return redirect('/')
    
    
class AdminOrderOverrideView(APIView):
    """
    Administrative control tower view allowing system admins to manually assign riders, 
    override delivery status parameters, or force-reset broken assignment loops.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        # 1. Verification Safeguard
        if request.user.role != User.Role.ADMIN:
            return Response({"error": "Access Denied: Administrative privileges required."}, status=403)

        order = get_object_or_404(Order, id=order_id)
        action = request.data.get("action")

        # ACTION A: FORCIBLY ASSIGN A SPECIFIC RIDER
        if action == "force_assign":
            rider_id = request.data.get("rider_id")
            if not rider_id:
                return Response({"error": "rider_id parameter is required for forced assignment."}, status=400)
            
            new_rider = get_object_or_404(User, id=rider_id, role=User.Role.DELIVERY_BOY)

            # Clean up the previous rider's operational profile flags if one was assigned
            if order.current_delivery_boy:
                prev_profile = getattr(order.current_delivery_boy, 'delivery_profile', None)
                if prev_profile:
                    prev_profile.is_busy = False
                    prev_profile.save(update_fields=["is_busy"])

            # Clean up any existing pending assignment rows for this specific order
            order.assignment_attempts.filter(status=AssignmentAttempt.Status.PENDING).update(
                status=AssignmentAttempt.Status.TIMEOUT
            )

            # Bind the new driver straight to the order structure
            order.current_delivery_boy = new_rider
            order.status = Order.Status.ACCEPTED
            order.save(update_fields=["current_delivery_boy", "status"])

            # Lock the new rider down as busy
            rider_profile = getattr(new_rider, 'delivery_profile', None)
            if rider_profile:
                rider_profile.is_busy = True
                rider_profile.save(update_fields=["is_busy"])

            # Create an audit trail history entry
            AssignmentAttempt.objects.create(
                order=order,
                driver=new_rider,
                status=AssignmentAttempt.Status.FORCED_BY_ADMIN
            )

            return Response({"message": f"Successfully forced order assignment to {new_rider.username}."})

        # ACTION B: RESET ORDER STATUS & RE-RUN THE AUTO-ASSIGN ALGORITHM
        elif action == "reset_and_reassign":
            if order.current_delivery_boy:
                profile = getattr(order.current_delivery_boy, 'delivery_profile', None)
                if profile:
                    profile.is_busy = False
                    profile.save(update_fields=["is_busy"])

            # Clear out the state fields
            order.current_delivery_boy = None
            order.status = Order.Status.PLACED
            order.rejected_by.clear() # Optional: Clear history blocklists so algorithm can check everyone again
            order.save(update_fields=["current_delivery_boy", "status"])

            # Cancel outstanding notifications
            order.assignment_attempts.filter(status=AssignmentAttempt.Status.PENDING).update(
                status=AssignmentAttempt.Status.TIMEOUT
            )

            # Kick off your background loop script again
            auto_assign_order(order.id)

            return Response({"message": "Order assignments dropped cleanly. Matching algorithm re-initialized."})

        return Response({"error": "Invalid administrative action provided."}, status=400)
    
class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """The central custom dashboard command view for site administrators."""
    template_name = 'dashboard/admin/admin_dashboard.html' # Make sure this matches your template path

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == User.Role.ADMIN

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Grab active orders needing tracking or dispatch attention
        context['active_orders'] = Order.objects.exclude(
            status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED]
        ).select_related('customer', 'current_delivery_boy').order_by('-created_at')
        
        # Grab all delivery boys for the manual assignment drop-downs
        context['available_riders'] = DeliveryBoyProfile.objects.select_related('user').all()
        
        # Pull the latest open support tickets to fill the alert sidebar
        context['recent_tickets'] = SupportTicket.objects.filter(
            status=SupportTicket.Status.OPEN
        ).select_related('user').order_by('-priority', '-created_at')[:5]
        
        return context

class SellerDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'dashboard/seller/seller.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == "SELLER"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        seller_profile = getattr(user, 'seller_profile', None)
        context['store_name'] = seller_profile.store_name if seller_profile else "My Store Front"
        context['business_license'] = seller_profile.business_licence if seller_profile else "N/A"
        
        seller_products = Product.objects.filter(seller=user).order_by('-created')
        context['products'] = seller_products
        context['active_listings'] = seller_products.count()
        context['total_sales'] = "Rs. 0.00"

        context['categories'] = Category.objects.select_related('parent').order_by('name')
        context['category_tree_json'] = [
            {
                'id': c.pk,
                'name': c.name,
                'parent_id': c.parent_id,
                'filter_schema': c.filter_schema if isinstance(c.filter_schema, dict) else {},
            }
            for c in context['categories']
        ]
        context['IMGBB_API_KEY'] = os.getenv('IMGBB_API_KEY', '')
        return context


class OrderActionView(APIView):
    """
    Handles inline interactive AJAX workspace updates straight from the 
    Rider web dashboard console interface buttons.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id, action):
        order = get_object_or_404(Order, id=order_id)

        if order.current_delivery_boy != request.user:
            return Response({"error": "This order is not assigned to you."}, status=403)

        # Look up the matching pending assignment token row for safety
        attempt = order.assignment_attempts.filter(
            driver=request.user,
            status=AssignmentAttempt.Status.PENDING
        ).first()

        if action == "accept":
            if attempt:
                attempt.status = AssignmentAttempt.Status.ACCEPTED
                attempt.save(update_fields=["status"])

            order.status = Order.Status.ACCEPTED
            order.save(update_fields=["status"])

            # 🔒 Driver officially took the job. Lock them down now!
            driver_profile = request.user.delivery_profile
            driver_profile.is_busy = True
            driver_profile.save(update_fields=["is_busy"])

            return Response({"message": "Order accepted successfully!"})

        elif action == "reject":
            order.rejected_by.add(request.user)

            if attempt:
                attempt.status = AssignmentAttempt.Status.REJECTED
                attempt.save(update_fields=["status"])

            # 👍 Driver rejected. Ensure they stay available for other matching tickets!
            profile = request.user.delivery_profile
            profile.is_busy = False
            profile.save(update_fields=["is_busy"])

            order.current_delivery_boy = None
            order.status = Order.Status.PLACED
            order.save(update_fields=["current_delivery_boy", "status"])

            # 🔁 Triggers the loop to find the next nearest driver
            auto_assign_order(order.id)

            return Response({"message": "Order passed to the next available driver."})

        return Response({"error": "Invalid action"}, status=400)
    

class DeliveryDashboardView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'dashboard/delivery/delivery_boy.html'
    context_object_name = 'orders'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == "DELIVERY_BOY"

    def get_queryset(self):
        # Fetch matching rows assigned or actively run by this rider account identity
        return Order.objects.filter(current_delivery_boy=self.request.user).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, created = DeliveryBoyProfile.objects.get_or_create(user=self.request.user)
        context['profile'] = profile
        
        # Also grab their open outstanding PENDING interactive notifications invitations
        context['pending_invitations'] = AssignmentAttempt.objects.filter(
            driver=self.request.user,
            status=AssignmentAttempt.Status.PENDING
        ).select_related('order')

        queryset = self.get_queryset()
        context['pending_deliveries'] = queryset.filter(status=Order.Status.ASSIGNING).count()
        context['completed_deliveries'] = queryset.filter(status=Order.Status.DELIVERED).count()
        return context


class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('login') 
    template_name = 'registration/signup.html'


@login_required
def get_delivery_route(request, order_id):
    """Calculates map route geometry path arrays between driver and dropoff coordinates via OSRM."""
    order = get_object_or_404(Order, id=order_id)
    profile = get_object_or_404(DeliveryBoyProfile, user=request.user)

    if not (profile.latitude and profile.longitude and order.delivery_latitude and order.delivery_longitude):
        return JsonResponse({"success": False, "error": "Missing profile or order map coordinates."}, status=400)

    osrm_url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{profile.longitude},{profile.latitude};{order.delivery_longitude},{order.delivery_latitude}"
        f"?overview=full&geometries=geojson"
    )

    try:
        response = requests.get(osrm_url, timeout=5)
        response_data = response.json()

        if response.status_code == 200 and "routes" in response_data and len(response_data["routes"]) > 0:
            route = response_data["routes"][0]
            return JsonResponse({
                "success": True,
                "route_geometry": route["geometry"],
                "duration_mins": round(route["duration"] / 60, 2),
                "distance_km": round(route["distance"] / 1000, 2)
            })
        return JsonResponse({"success": False, "error": "Could not calculate structural routing path geometry"}, status=400)
    except requests.exceptions.RequestException as e:
        return JsonResponse({"success": False, "error": f"OSRM connection failed: {str(e)}"}, status=500)
    

@login_required
def update_rider_location(request):
    """Saves telemetry updates pushed live from the mobile/desktop browser runtime coordinates."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            lat = data.get("latitude")
            lng = data.get("longitude")
            
            if lat is not None and lng is not None:
                profile, created = DeliveryBoyProfile.objects.get_or_create(user=request.user)
                profile.latitude = lat
                profile.longitude = lng
                profile.save()
                return JsonResponse({"success": True, "message": "Location coordinates updated successfully."})
            return JsonResponse({"success": False, "error": "Missing latitude or longitude in request body."}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Invalid JSON payload."}, status=400)
            
    return JsonResponse({"success": False, "error": "POST method required."}, status=405)


# accounts/views.py

def accept_delivery(request, attempt_id):  # 👈 Change order_id to attempt_id here
    """Landing route executed via the rider email CTA or dashboard tracking components."""
    attempt = get_object_or_404(AssignmentAttempt, id=attempt_id) # 👈 Now attempt_id matches perfectly!
    order = attempt.order
    driver_profile = attempt.driver.delivery_profile

    if attempt.status == AssignmentAttempt.Status.TIMEOUT:
        messages.error(request, "Too late! The response window expired, and this job was reassigned.")
        return redirect('/accounts/dashboard/delivery/')

    if attempt.status == AssignmentAttempt.Status.REJECTED:
        messages.error(request, "You already rejected this order.")
        return redirect('/accounts/dashboard/delivery/')

    # 1. Update confirmation status metrics
    attempt.status = AssignmentAttempt.Status.ACCEPTED
    attempt.save(update_fields=["status"])

    # 2. Update core order object states
    order.status = Order.Status.ACCEPTED
    order.current_delivery_boy = attempt.driver
    order.save(update_fields=["status", "current_delivery_boy"])

    # 3. 🔒 LOCK DRIVER: They officially took the assignment. Mark them busy now.
    driver_profile.is_busy = True
    driver_profile.save(update_fields=["is_busy"])

    messages.success(request, f"Order #{order.id} accepted successfully! Navigate to your active queue.")
    return redirect('/accounts/dashboard/delivery/')

def reject_delivery(request, attempt_id):
    """Landing route used when the rider declines the invitation ticket link."""
    attempt = get_object_or_404(AssignmentAttempt, id=attempt_id)
    order = attempt.order
    driver_profile = attempt.driver.delivery_profile

    if attempt.status == AssignmentAttempt.Status.PENDING:
        attempt.status = AssignmentAttempt.Status.REJECTED
        attempt.save(update_fields=["status"])

        # Log blacklist rejection so algorithm skips them on next recursion loop pass
        order.rejected_by.add(attempt.driver)
        order.current_delivery_boy = None
        order.status = Order.Status.PLACED
        order.save(update_fields=["current_delivery_boy", "status"])

        # 👍 Keep the driver available for other orders
        driver_profile.is_busy = False
        driver_profile.save(update_fields=["is_busy"])

        # 🔁 LOOP AGAIN: Instantly execute a scan to target the next nearest available driver profile
        print(f"🔄 Order #{order.id} rejected by {attempt.driver.username}. Searching for next driver...")
        auto_assign_order(order.id)

        messages.info(request, "You declined the delivery run. The ticket has been passed to another driver.")
    
    return redirect('/accounts/dashboard/delivery/')




class CreateSupportTicketView(LoginRequiredMixin, CreateView):
    model = SupportTicket
    form_class = SupportTicketForm
    template_name = 'dashboard/support/create_ticket.html'
    success_url = reverse_lazy('support_history') # Adjust path as needed

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user # Pass user context down to filter order lists
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.submitted_as_role = self.request.user.role
        
        # System intelligence escalation rule: Auto-escalate missing items to URGENT
        if form.instance.category == SupportTicket.Category.MISSING_ITEM:
            form.instance.priority = SupportTicket.Priority.URGENT
            
        messages.success(self.request, "Your report has been successfully transmitted to the admin team.")
        return super().form_valid(form)


class AdminSupportDashboardView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Control room for Admins to view incoming urgent issues across roles."""
    template_name = 'dashboard/admin/support_list.html'
    context_object_name = 'tickets'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == "ADMIN"

    def get_queryset(self):
        # Sort by urgency level first, then creation timestamp
        return SupportTicket.objects.all().select_related('user', 'order').order_by('-priority', '-created_at')