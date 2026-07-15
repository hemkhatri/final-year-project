# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views # <-- 1. Import Django's Auth Views
from .views import (
    SellerDashboardView, SignUpView, DeliveryDashboardView, 
    update_rider_location, get_delivery_route, accept_delivery, reject_delivery
)

app_name = 'accounts'

# accounts/urls.py

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('dashboard/seller/', SellerDashboardView.as_view(), name='seller_dashboard'),
    path('dashboard/delivery/', DeliveryDashboardView.as_view(), name='delivery_dashboard'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    path('delivery/accept/<int:attempt_id>/', accept_delivery, name='accept_delivery'),
    path('delivery/reject/<int:attempt_id>/', reject_delivery, name='reject_delivery'),
    
    path('api/location/update/', update_rider_location, name='update_rider_location'),
    path('api/route/<int:order_id>/', get_delivery_route, name='get_delivery_route'),
]