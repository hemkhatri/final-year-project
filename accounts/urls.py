# accounts/urls.py
from django.urls import path
from .views import SellerDashboardView, SignUpView, DeliveryDashboardView

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('dashboard/seller/', SellerDashboardView.as_view(), name='seller_dashboard'),
    path('dashboard/delivery/', DeliveryDashboardView.as_view(), name='delivery_dashboard'),
]