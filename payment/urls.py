from django.urls import path
from . import views

app_name = 'payment'

urlpatterns = [
    path('checkout/', views.checkout_preview, name='checkout_preview'),
    path('success/', views.payment_success, name='payment_success'),  # ◄ ADD THIS
    path('failure/', views.payment_failure, name='payment_failure'),  # ◄ ADD THIS
]