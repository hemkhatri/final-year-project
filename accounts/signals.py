from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, SellerProfile, CustomerProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == User.Role.SELLER:
            SellerProfile.objects.create(user=instance)
        elif instance.role == User.Role.CUSTOMER:
            CustomerProfile.objects.create(user=instance)  # Fixed here