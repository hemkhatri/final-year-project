import os
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, CreateView, ListView
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .forms import CustomUserCreationForm
from .models import Order, DeliveryBoyProfile
from .services import assign_next_delivery_boy
from shop.models import Product, Category

# 1. Added Smart Login Redirect View
@login_required
def smart_login_redirect(request):
    user = request.user
    
    if user.role == "DELIVERY_BOY":
        return redirect('/accounts/dashboard/delivery/')  # Direct path string
    elif user.role == "SELLER":
        return redirect('/accounts/dashboard/seller/')    # Direct path string
    elif user.role == "ADMIN":
        return redirect('/admin/')
    else:
        return redirect('/')  # Direct path to your customer home page / market

class SellerDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'dashboard/seller/seller.html'

    def test_func(self):
        """Locks down this view to SELLER profiles only."""
        return self.request.user.is_authenticated and self.request.user.role == "SELLER"

    def get_context_data(self, **kwargs):
        """Pass real, functional database telemetry into the dashboard workspace context panels."""
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
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id, action):
        order = get_object_or_404(Order, id=order_id)

        if order.current_delivery_boy != request.user:
            return Response({"error": "This order is not assigned to you."}, status=403)

        if action == "accept":
            order.status = Order.Status.ACCEPTED
            order.save()

            driver_profile = request.user.delivery_profile
            driver_profile.is_busy = True
            driver_profile.save()

            return Response({"message": "Order accepted successfully!"})

        elif action == "reject":
            order.rejected_by.add(request.user)
            assign_next_delivery_boy(order)

            return Response({"message": "Order rejected. Re-routing to next closest driver."})

        return Response({"error": "Invalid action"}, status=400)
    

class DeliveryDashboardView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'dashboard/delivery/delivery_boy.html'
    context_object_name = 'orders'

    def test_func(self):
        """Restrict access to delivery boys only."""
        return self.request.user.is_authenticated and self.request.user.role == "DELIVERY_BOY"

    def get_queryset(self):
        """Fetch only the orders assigned to this specific delivery boy."""
        # Fixed: Changed field to 'current_delivery_boy' and fixed 'order_dict' typo to 'order_by'
        return Order.objects.filter(current_delivery_boy=self.request.user).order_by('-created_at')

    def get_context_data(self, **kwargs):
            """Add profile info or stats to the dashboard context."""
            context = super().get_context_data(**kwargs)
            
            # FIX: Automatically create a profile on the fly if it doesn't exist yet
            profile, created = DeliveryBoyProfile.objects.get_or_create(user=self.request.user)
            context['profile'] = profile
            
            queryset = self.get_queryset()
            context['pending_deliveries'] = queryset.filter(status='ASSIGNING').count()
            context['completed_deliveries'] = queryset.filter(status='DELIVERED').count()
            return context


class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('login') 
    template_name = 'registration/signup.html'