from django.db import models
from django.conf import settings
from shop.models import Product  # Adjust to your product model path

class Order(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending Payment'),
        ('PAID', 'Paid / Completed'),
        ('FAILED', 'Payment Failed'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    
    # We will use the Order Primary Key (ID) or a custom tracking string for eSewa's transaction_uuid
    transaction_uuid = models.CharField(max_length=100, unique=True, blank=True, null=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"