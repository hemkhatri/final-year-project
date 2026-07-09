from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        SELLER = "SELLER", "Seller"
        CUSTOMER = "CUSTOMER", "Customer"

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