from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import F, Value
from django.db.models.functions import ACos, Cos, Radians, Sin
from django.db.models.signals import post_save
from django.dispatch import receiver
# Create your models here.


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        SELLER = "SELLER", "Seller"
        CUSTOMER = "CUSTOMER", "Customer"
        DELIVERY_BOY = "DELIVERY_BOY", "Delivery Boy" #Added new user

        # default role is customer if no role is assigned
    base_role = Role.CUSTOMER
    
    role = models.CharField(
        max_length= 50,
        choices= Role.choices,
        default= base_role
    )

    def save(self, *args, **kwargs):
        # auto set internal flags based on django ecosystem
        if self.role == self.Role.ADMIN:
            self.is_staff = True
        super().save(*args,  **kwargs)


class SellerProfile(models.Model):
    user = models.OneToOneField(User, on_delete= models.CASCADE, related_name= "seller_profile")
    store_name = models.CharField(max_length= 255)
    business_licence = models.CharField(max_length= 100)

    def __str__(self):
        return self.user.username

class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete= models.CASCADE, related_name = "customer_profile")
    shipping_address = models.TextField()
    phone_number = models.CharField(max_length= 20)

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

    # Store real-time coordinates of the delivery boy
    longitude = models.DecimalField(max_digits=9, decimal_places=6, default=0.0)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, default=0.0)

    # Vehicle details moved here where they belong
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
        
        # Fixed mathematical brackets for the longitude cosine difference
        distance_expression = (
            ACos(
                Sin(Radians(F('latitude'))) * Sin(Radians(Value(customer_lat))) +
                Cos(Radians(F('latitude'))) * Cos(Radians(Value(customer_lat))) *
                Cos(Radians(F('longitude') - Value(customer_lon)))                          
            ) * 6371  # Yes, Earth's radius in km! 🌍
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

    # Delivery destination coordinates
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLACED)

    current_delivery_boy = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_deliveries"
    )

    rejected_by = models.ManyToManyField(User, blank=True, related_name="rejected_orders")
    created_at = models.DateTimeField(auto_now_add=True)  # Changed to auto_now_add for creation timestamps

    def __str__(self):
        return f"Order #{self.id} - {self.customer.username}"
    

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically creates the correct profile object based on the 
    user's assigned role when a new user account is registered.
    """
    if created:
        if instance.role == User.Role.DELIVERY_BOY:
            DeliveryBoyProfile.objects.get_or_create(user=instance)
        elif instance.role == User.Role.SELLER:
            SellerProfile.objects.get_or_create(user=instance)
        elif instance.role == User.Role.CUSTOMER:
            CustomerProfile.objects.get_or_create(user=instance)