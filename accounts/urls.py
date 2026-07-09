# accounts/urls.py
from django.urls import path
from .views import SellerDashboardView, SignUpView

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('dashboard/seller/', SellerDashboardView.as_view(), name='seller_dashboard'),
]