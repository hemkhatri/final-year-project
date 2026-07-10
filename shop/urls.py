from django.urls import path
from .views import (
    ProductListView, ProductDetailView, ProductCreateView, 
    ProductUpdateAjaxView, ProductDeleteView, ProductCreateAjaxView, SellerOrdersJsonView
)

urlpatterns = [
    path('', ProductListView.as_view(), name='market_home'),
    path('product/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('products/create/', ProductCreateView.as_view(), name='product_create'), # Your standard page
    path('dashboard/seller/products/create-ajax/', ProductCreateAjaxView.as_view(), name='product_create_ajax'), # NEW endpoint
    path('dashboard/seller/products/<int:pk>/update/', ProductUpdateAjaxView.as_view(), name='product_update_ajax'),
    path('dashboard/seller/products/<int:pk>/delete/', ProductDeleteView.as_view(), name='product_delete'),
    path('api/seller/orders/', SellerOrdersJsonView.as_view(), name='seller_orders_api'),
]