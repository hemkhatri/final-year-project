"""
URL configuration for django_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# django_project/urls.py
# django_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from accounts.views import SellerDashboardView, SignUpView
from shop.views import ProductListView # Make sure this is available

def root_redirect_view(request):
    # If not logged in, let them browse the marketplace anonymously!
    if not request.user.is_authenticated:
        return ProductListView.as_view()(request)
        
    # If they are a Seller, divert them to their management dashboard
    if request.user.role == "SELLER":
        return redirect('seller_dashboard')
        
    # If they are a Customer, keep them on the storefront marketplace feed
    return ProductListView.as_view()(request)

urlpatterns = [
    path('', root_redirect_view, name='root_redirect'),
    path('admin/', admin.site.urls),
    path('dashboard/seller/', SellerDashboardView.as_view(), name='seller_dashboard'),
    path('accounts/signup/', SignUpView.as_view(), name='signup'),
    path('accounts/', include('django.contrib.auth.urls')), 
    path('shop/', include('shop.urls')), # Kept for explicit sub-routing if needed
    path("assistant/", include("assistant.urls")),
]