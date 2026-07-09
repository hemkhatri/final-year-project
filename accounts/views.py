# accounts/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import CustomUserCreationForm


class SellerDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    # Specify the template file location
    template_name = 'dashboard/seller.html'

    def test_func(self):
        """
        UserPassesTestMixin runs this method. 
        If it returns True, access is granted. Otherwise, it triggers a 403 Forbidden error.
        """
        return self.request.user.is_authenticated and self.request.user.role == "SELLER"

    def get_context_data(self, **kwargs):
        """
        Pass role-specific metrics or information into your dashboard view context.
        """
        context = super().get_context_data(**kwargs)
        
        # Access profile data seamlessly via the related_name we fixed earlier
        seller_profile = self.request.user.seller_profile
        
        context['store_name'] = seller_profile.store_name
        context['business_license'] = seller_profile.business_licence
        
        # Mock metrics for layout visualization
        context['total_sales'] = "$12,450.00"
        context['active_listings'] = 24
        
        return context


class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('login') # Redirects to login page after successful signup
    template_name = 'registration/signup.html'