# shop/models.py
from django.db import models
from django.conf import settings
import re
from django.contrib.auth import get_user_model
User = get_user_model()


def extract_youtube_id(url):
    match = re.search(r'(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|v/|shorts/))([\w-]{11})', url or '')
    return match.group(1) if match else (url if re.fullmatch(r'[\w-]{11}', url or '') else '')


class Category(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    
    def __str__(self):
        return self.name

class Product(models.Model):
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    available = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    @property
    def cover_image(self):
        first_image = self.media.filter(media_type='IMAGE').first()
        return first_image.url if first_image else None

    
    def __str__(self):
        return self.name

class ProductMedia(models.Model):
    MEDIA_TYPES = (
        ('IMAGE', 'Image'),
        ('VIDEO', 'YouTube Video'),
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='media')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES, default='IMAGE')
    url = models.URLField(max_length=500) # Stores ImgBB CDN url OR Youtube url
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-media_type', 'created_at']

    def __str__(self):
        return f"{self.media_type} for {self.product.name}"
    

class Order(models.Model):
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('RETURNS', 'Returns & Dispute'),
    ]
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shop_orders')
    created_at = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_name = models.CharField(max_length=255)
    shipping_address = models.TextField()


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items')
    product_name_snapshot = models.CharField(max_length=200, blank=True)  # preserved even if product is deleted later
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES, default='NEW')