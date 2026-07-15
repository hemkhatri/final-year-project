# payment/admin.py
from django.contrib import admin
from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # CHANGED: 'user' replaced with 'buyer' to perfectly match your Order model field
    list_display = ['id', 'buyer', 'status', 'total_amount', 'created_at']
    list_filter = ['status', 'created_at']
    
    # CHANGED: Updated user__username to buyer__username
    search_fields = ['id', 'buyer__username']
    inlines = [OrderItemInline]
    readonly_fields = ['created_at']