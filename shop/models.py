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
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='subcategories'
    )
    image_url = models.URLField(max_length=500, blank=True, null=True)
    color = models.CharField(
        max_length=7, 
        default='#4F46E5', 
        help_text="Hex color code (e.g., #4F46E5)"
    )

    # 🔑 NEW: Field to store parent/child filter schemas
    filter_schema = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="JSON object defining available filter keys/options"
    )

    class Meta:
        verbose_name_plural = "categories"

    def get_filter_schema(self):
        """
        Returns this category's filter_schema if populated.
        Otherwise inherits the parent category's filter_schema.
        """
        # Fix: Check if dictionary has keys, even if values are None
        if isinstance(self.filter_schema, dict) and len(self.filter_schema) > 0:
            return self.filter_schema
        if self.parent and isinstance(self.parent.filter_schema, dict) and len(self.parent.filter_schema) > 0:
            return self.parent.filter_schema
        return {}

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name




class Product(models.Model):
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    description = models.TextField(blank=True) # Kept intact as requested!
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    available = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    # 🔑 NEW: Dynamic attributes stored in JSON format
    # Examples:
    # Fashion: {"sub_type": "jeans", "size": "XL"}
    # Kitchen: {"sub_type": "rice_cooker", "capacity": "3L"}
    attributes = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="JSON format properties (e.g. {\"sub_type\": \"jeans\", \"size\": \"L\"})"
    )

    # Analytics & Metrics
    total_views = models.PositiveIntegerField(default=0)
    total_search_appears = models.PositiveIntegerField(default=0)
    total_bought = models.PositiveIntegerField(default=0)

    # Reviews Summary
    total_reviews = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)

    # Tagging System
    tags = models.ManyToManyField('SearchTag', blank=True, related_name='products')
    relevant_tags = models.TextField(
        blank=True, 
        help_text="Comma-separated plain text keywords for search indexing"
    )

    @property
    def cover_image(self):
        first_image = self.media.filter(media_type='IMAGE').first()
        return first_image.url if first_image else None

    def __str__(self):
        return self.name
    


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(help_text="Rating from 1 to 5")
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        # Prevents a single user from spamming multiple reviews on one product
        unique_together = ('product', 'user') 

    def __str__(self):
        return f"{self.rating}★ by {self.user.username} on {self.product.name}"
    

    
class ProductMedia(models.Model):
    MEDIA_TYPES = (
        ('IMAGE', 'Image'),
        ('VIDEO', 'YouTube Video'),
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='media')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES, default='IMAGE')
    url = models.URLField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-media_type', 'created_at']

    def __str__(self):
        return f"{self.media_type} for {self.product.name}"
    

class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Payment Pending'),
        ('PAID', 'Payment Successful'),
        ('ASSIGNING', 'Assigning Driver'),
        ('SHIPPED', 'Shipped'),
        ('RETURNS', 'Returns & Dispute'),
    ]
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shop_orders')
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
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items')
    product_name_snapshot = models.CharField(max_length=200, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES, default='PENDING')



class SellerApplication(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Verification'),
        ('ACTIVE', 'Approved/Active'),
        ('SUSPENDED', 'Suspended'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='seller_application')
    store_name = models.CharField(max_length=100, unique=True)
    
    # 1. Legal Proof
    id_document = models.FileField(upload_to='seller_docs/ids/')
    business_license = models.FileField(upload_to='seller_docs/licenses/')
    tax_number = models.CharField(max_length=50, help_text="PAN or VAT number")
    
    # 2. Financial Routing
    bank_name = models.CharField(max_length=100)
    routing_number = models.CharField(max_length=50)
    account_number = models.CharField(max_length=50)
    beneficiary_name = models.CharField(max_length=100)
    bank_statement = models.FileField(upload_to='seller_docs/financials/')
    
    # 3. Operational Metrics
    warehouse_address = models.TextField(help_text="Physical pickup location for delivery couriers")
    support_email = models.EmailField()
    support_phone = models.CharField(max_length=20)
    product_categories = models.TextField(help_text="Comma-separated list of intended categories")
    
    # Technical Architecture Flags
    kyc_status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.store_name} ({self.get_kyc_status_display()})"
    

class SearchTag(models.Model):
    keyword = models.CharField(max_length=100, unique=True, help_text="e.g., 'pants for men', 'freeze 200l'")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    search_count = models.PositiveIntegerField(default=0, help_text="Track popularity")

    class Meta:
        ordering = ['-search_count', 'keyword']

    def __str__(self):
        return self.keyword