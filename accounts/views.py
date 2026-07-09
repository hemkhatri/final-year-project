# accounts/views.py
import os
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import CustomUserCreationForm
from shop.models import Product, Category  # <-- add Category here

class SellerDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'dashboard/seller/seller.html'

    def test_func(self):
        """
        Locks down this view to SELLER profiles only.
        """
        return self.request.user.is_authenticated and self.request.user.role == "SELLER"

    def get_context_data(self, **kwargs):
        """
        Pass real, functional database telemetry into the dashboard workspace context panels.
        """
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Pull profile specifics safely using getattr to avoid errors if the relationship doesn't exist yet
        seller_profile = getattr(user, 'seller_profile', None)
        context['store_name'] = seller_profile.store_name if seller_profile else "My Store Front"
        # Handles your database spelling 'business_licence' seamlessly
        context['business_license'] = seller_profile.business_licence if seller_profile else "N/A"
        
        # 1. Fetch real products that belong to this seller from the database (Ordered by newest first)
        seller_products = Product.objects.filter(seller=user).order_by('-created')
        context['products'] = seller_products
        
        # 2. Compute dynamic listing data metric properties instantly
        context['active_listings'] = seller_products.count()
        
        # 3. Dynamic layout string formatting (Placeholder for real checkout/order aggregation formulas later)
        context['total_sales'] = "Rs. 0.00"

        # 4. Category options for the "Add New Product" form dropdown
        context['categories'] = Category.objects.all()

        # 5. ImgBB key for direct client-side image uploads
        context['IMGBB_API_KEY'] = os.getenv('IMGBB_API_KEY', '')
        
        return context


class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('login') 
    template_name = 'registration/signup.html'