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
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from accounts.views import SellerDashboardView, SignUpView  # <-- Make sure SignUpView is imported!

# Your dynamic landing router
def root_redirect_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if request.user.role == "SELLER":
        return redirect('seller_dashboard')
    return redirect('login') 

urlpatterns = [
    path('', root_redirect_view, name='root_redirect'),
    path('admin/', admin.site.urls),
    path('dashboard/seller/', SellerDashboardView.as_view(), name='seller_dashboard'),
    
    # 1. Explicitly add the signup route here:
    path('accounts/signup/', SignUpView.as_view(), name='signup'),
    
    # 2. Then include the built-in authentication views:
    path('accounts/', include('django.contrib.auth.urls')), 
]