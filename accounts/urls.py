# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    SignUpView,
    smart_login_redirect,
    AdminDashboardView,
    SellerDashboardView,
    DeliveryDashboardView,
    accept_delivery,
    reject_delivery,
    update_rider_location,
    get_delivery_route,
    AdminOrderOverrideView,
    CreateSupportTicketView,
    AdminSupportDashboardView,
)

app_name = 'accounts'

urlpatterns = [
    # Authentication Operations
    path('signup/', SignUpView.as_view(), name='signup'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Smart Role-Based Redirect Router Gateway
    path('login/redirect/', smart_login_redirect, name='smart_login_redirect'),
    
    # Core Operations Dashboards
    path('dashboard/admin/', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('dashboard/seller/', SellerDashboardView.as_view(), name='seller_dashboard'),
    path('dashboard/delivery/', DeliveryDashboardView.as_view(), name='delivery_dashboard'),
    
    # Delivery Driver Interventions
    path('delivery/accept/<int:attempt_id>/', accept_delivery, name='accept_delivery'),
    path('delivery/reject/<int:attempt_id>/', reject_delivery, name='reject_delivery'),
    
    # Internal Operational Backing Engine APIs
    path('api/location/update/', update_rider_location, name='update_rider_location'),
    path('api/route/<int:order_id>/', get_delivery_route, name='get_delivery_route'),
    path('api/admin/orders/<int:order_id>/override/', AdminOrderOverrideView.as_view(), name='admin_order_override'),
    
    # Customer Service Support Ticketing Suite
    path('support/report/', CreateSupportTicketView.as_view(), name='create_support_ticket'),
    path('admin/support/', AdminSupportDashboardView.as_view(), name='admin_support_dashboard'),
]