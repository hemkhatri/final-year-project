# shop/urls.py
from django.urls import path
from .views import (
    ProductListView, ProductDetailView, ProductCreateView, 
    ProductUpdateAjaxView, ProductDeleteView, ProductCreateAjaxView, 
    SellerOrdersJsonView, category_list_view, become_seller_view, become_seller_landing, privacy_policy, careers_landing
)

app_name = 'shop'

urlpatterns = [
    path('', ProductListView.as_view(), name='market_home'),
    
    path('become-seller/', become_seller_landing, name='become_seller_landing'),
    path('become-seller/apply/', become_seller_view, name='become_seller'),
    path('privacy-policy', privacy_policy, name='privacy-policy'),
    path('careers/', careers_landing, name='careers_landing'),
    
    path('<slug:slug>/', ProductDetailView.as_view(), name='product_detail'),
    path('products/create/', ProductCreateView.as_view(), name='product_create'), 
    path('dashboard/seller/products/create-ajax/', ProductCreateAjaxView.as_view(), name='product_create_ajax'), 
    path('dashboard/seller/products/<int:pk>/update/', ProductUpdateAjaxView.as_view(), name='product_update_ajax'),
    path('dashboard/seller/products/<int:pk>/delete/', ProductDeleteView.as_view(), name='product_delete'),
    path('api/seller/orders/', SellerOrdersJsonView.as_view(), name='seller_orders_api'),
    path('category/', category_list_view, name='category_list'),
    
]