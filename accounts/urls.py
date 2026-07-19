# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    SellerDashboardView, SignUpView, DeliveryDashboardView, 
    update_rider_location, get_delivery_route, accept_delivery, reject_delivery
)

app_name = 'accounts'

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    
    # 🔑 CHANGED HERE: Pointing directly to the registration directory path
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    
    path('dashboard/seller/', SellerDashboardView.as_view(), name='seller_dashboard'),
    path('dashboard/delivery/', DeliveryDashboardView.as_view(), name='delivery_dashboard'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    path('delivery/accept/<int:attempt_id>/', accept_delivery, name='accept_delivery'),
    path('delivery/reject/<int:attempt_id>/', reject_delivery, name='reject_delivery'),
    
    path('api/location/update/', update_rider_location, name='update_rider_location'),
    path('api/route/<int:order_id>/', get_delivery_route, name='get_delivery_route'),
]