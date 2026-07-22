# shop/urls.py
from django.urls import path
from .views import (
    ProductListView, ProductDetailView, ProductCreateView, 
    ProductUpdateAjaxView, ProductDeleteView, ProductCreateAjaxView, 
    SellerOrdersJsonView, category_list_view, become_seller_view, 
    become_seller_landing, privacy_policy, careers_landing, 
    product_search_view, autocomplete_search_view, load_more_only_for_you
)

app_name = 'shop'

urlpatterns = [
    path('', ProductListView.as_view(), name='market_home'),
    
    path('become-seller/', become_seller_landing, name='become_seller_landing'),
    path('become-seller/apply/', become_seller_view, name='become_seller'),
    path('privacy-policy/', privacy_policy, name='privacy-policy'),  # Added trailing slash for consistency
    path('careers/', careers_landing, name='careers_landing'),
    path('search/', product_search_view, name='product_search'),
    path('api/autocomplete/', autocomplete_search_view, name='api_autocomplete'),
    
    # Static dashboard & category routes MUST come before <slug:slug>/
    path('category/', category_list_view, name='category_list'),
    path('products/create/', ProductCreateView.as_view(), name='product_create'), 
    path('dashboard/seller/products/create-ajax/', ProductCreateAjaxView.as_view(), name='product_create_ajax'), 
    path('dashboard/seller/products/<int:pk>/update/', ProductUpdateAjaxView.as_view(), name='product_update_ajax'),
    path('dashboard/seller/products/<int:pk>/delete/', ProductDeleteView.as_view(), name='product_delete'),
    path('api/seller/orders/', SellerOrdersJsonView.as_view(), name='seller_orders_api'),
    
    # Catch-all slug pattern LAST
    path('<slug:slug>/', ProductDetailView.as_view(), name='product_detail'),
    path("api/load-more-for-you/", load_more_only_for_you,name="load_more_only_for_you"),
]