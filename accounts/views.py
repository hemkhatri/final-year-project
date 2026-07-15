import os
import requests
import json
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


@login_required
def smart_login_redirect(request):
    """Smart routing post-authentication based on institutional operational roles."""
    user = request.user
    if user.role == "DELIVERY_BOY":
        return redirect('/accounts/dashboard/delivery/')
    elif user.role == "SELLER":
        return redirect('/accounts/dashboard/seller/')
    elif user.role == "ADMIN":
        return redirect('/admin/')
    else:
        return redirect('/')


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
            {'id': c.pk, 'name': c.name, 'parent_id': c.parent_id}
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