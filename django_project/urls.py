# django_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from shop.views import ProductListView 
from django.contrib.auth import views as auth_views

def root_redirect_view(request):
    # If not logged in, let them browse the marketplace anonymously!
    if not request.user.is_authenticated:
        return ProductListView.as_view()(request)
        
    # 🔑 Fixed: Point to your namespaced app targets
    if request.user.role == "DELIVERY_BOY":
        return redirect('accounts:delivery_dashboard')
        
    if request.user.role == "SELLER":
        return redirect('accounts:seller_dashboard')
        
    return ProductListView.as_view()(request)

urlpatterns = [
    path('', root_redirect_view, name='root_redirect'),
    path('admin/', admin.site.urls),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # 🔑 Fixed: Removed duplicate include and mapped apps neatly
    path('accounts/', include('accounts.urls')), 
    path('accounts/', include('django.contrib.auth.urls')), # Provides global 'login' fallback
    
    path('shop/', include(('shop.urls', 'shop'), namespace='shop')),
    path("assistant/", include("assistant.urls")),
    path('cart/', include('cart.urls')),
    path('payment/', include('payment.urls')), 
]