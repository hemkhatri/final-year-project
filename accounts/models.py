from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import F, Value
from django.db.models.functions import ACos, Cos, Radians, Sin
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

# Create your models here.

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        SELLER = "SELLER", "Seller"
        CUSTOMER = "CUSTOMER", "Customer"
        DELIVERY_BOY = "DELIVERY_BOY", "Delivery Boy"

    class Gender(models.TextChoices):
        MALE = "MALE", "Male"
        FEMALE = "FEMALE", "Female"
        OTHER = "OTHER", "Other"
        PREFER_NOT_TO_SAY = "PREFER_NOT_TO_SAY", "Prefer not to say"

    base_role = Role.CUSTOMER

    role = models.CharField(
        max_length=50,
        choices=Role.choices,
        default=base_role
    )

    # Profile fields
    full_name = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    
    # Added gender and age
    gender = models.CharField(
        max_length=20,
        choices=Gender.choices,
        blank=True
    )
    age = models.PositiveIntegerField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # Auto-set internal staff status for Admins
        if self.role == self.Role.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)


class SellerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="seller_profile")
    store_name = models.CharField(max_length=255)
    business_licence = models.CharField(max_length=100)

    def __str__(self):
        return self.user.username


class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer_profile")
    shipping_address = models.TextField()
    phone_number = models.CharField(max_length=20)

    def __str__(self):
        return self.user.username
    

class DeliveryBoyProfile(models.Model):
    class VechileType(models.TextChoices):
        BIKE = "BIKE", "Bike"
        BICYCLE = "BICYCLE", "Bicycle"
        CAR = "CAR", "Car"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="delivery_profile")
    is_available = models.BooleanField(default=True)
    is_busy = models.BooleanField(default=False)

    longitude = models.DecimalField(max_digits=9, decimal_places=6, default=0.0)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, default=0.0)

    licence_number = models.CharField(max_length=50, blank=True, null=True)
    vechile_type = models.CharField(max_length=20, choices=VechileType.choices, default=VechileType.BIKE)

    def __str__(self):
        return f"Delivery Boy: {self.user.username}"

    @classmethod
    def get_nearest_available(cls, customer_lat, customer_lon, excluded_user_ids=None):
        if excluded_user_ids is None:
            excluded_user_ids = []
        
        candidates = cls.objects.filter(
            is_available=True,
            is_busy=False,
        ).exclude(user_id__in=excluded_user_ids)

        if not candidates.exists():
            return None
        
        distance_expression = (
            ACos(
                Sin(Radians(F('latitude'))) * Sin(Radians(Value(customer_lat))) +
                Cos(Radians(F('latitude'))) * Cos(Radians(Value(customer_lat))) *
                Cos(Radians(F('longitude') - Value(customer_lon)))                          
            ) * 6371
        )

        nearest_driver = candidates.annotate(
            distance=distance_expression
        ).order_by('distance').first()

        return nearest_driver


class Order(models.Model):
    class Status(models.TextChoices):
        PLACED = "PLACED", "Placed"
        ASSIGNING = "ASSIGNING", "Assigning Driver"
        ACCEPTED = "ACCEPTED", "Accepted / In Progress"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="account_orders")
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLACED)
    current_delivery_boy = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_deliveries"
    )
    rejected_by = models.ManyToManyField(User, blank=True, related_name="rejected_orders")
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Link to shop order (optional but recommended)
    shop_order_id = models.IntegerField(null=True, blank=True)  # Reference to shop.models.Order.id

    def __str__(self):
        return f"Order #{self.id} - {self.customer.username}"


# Track the 20-minute acceptance lifecycle per dispatch attempt
class AssignmentAttempt(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Response'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        TIMEOUT = 'TIMEOUT', 'Timed Out after 20 mins'
        REJECTED = 'REJECTED', 'Rejected'
        FORCED_BY_ADMIN = 'FORCED_BY_ADMIN', 'Forced by Admin Override' # 👈 Add this row

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='assignment_attempts')
    driver = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)


# Keep your signals intact
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if hasattr(User, 'Role'):  # Safety check for role structures
            if instance.role == User.Role.DELIVERY_BOY:
                DeliveryBoyProfile.objects.get_or_create(user=instance)
            elif instance.role == User.Role.SELLER:
                SellerProfile.objects.get_or_create(user=instance)
            elif instance.role == User.Role.CUSTOMER:
                CustomerProfile.objects.get_or_create(user=instance)




class SupportTicket(models.Model):
    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent / Missing Items"

    class Category(models.TextChoices):
        MISSING_ITEM = "MISSING_ITEM", "Missing Items in Order"
        DAMAGE = "DAMAGE", "Damaged Goods"
        DELIVERY_ISSUE = "DELIVERY_ISSUE", "Delivery Delay or Dispute"
        PAYMENT = "PAYMENT", "Payment / Refund Issue"
        OTHER = "OTHER", "General Inquiry"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "Under Investigation"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="support_tickets")
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="support_tickets")
    
    # Store the role of the user *at the time* they submitted the report
    submitted_as_role = models.CharField(max_length=50, choices=User.Role.choices)
    
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    
    subject = models.CharField(max_length=255)
    description = models.TextField()
    
    admin_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ticket #{self.id} [{self.category}] - {self.user.username}"
