# payment/models.py
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Payment Pending'),
        ('PAID', 'Payment Successful'),
        ('ASSIGNING', 'Assigning Driver'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # CHANGED: Renamed related_name to 'payment_orders' to avoid clashing with shop.Order
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_orders')
    created_at = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_name = models.CharField(max_length=255)
    shipping_address = models.TextField()
    phone_number = models.CharField(max_length=20, blank=True)
    
    # ===== CRITICAL: Delivery Location Coordinates =====
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    transaction_uuid = models.CharField(max_length=100, unique=True, null=True, blank=True)
    
    def __str__(self):
        return f"Order #{self.id} - {self.buyer.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    
    # CHANGED: Renamed related_name to 'payment_order_items' to avoid clashing with shop.OrderItem
    product = models.ForeignKey('shop.Product', on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_order_items')
    product_name_snapshot = models.CharField(max_length=200, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.product_name_snapshot or 'Product'} x{self.quantity} - Order #{self.order.id}"