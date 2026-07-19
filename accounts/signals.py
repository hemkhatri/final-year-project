# accounts/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, SellerProfile, CustomerProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == User.Role.SELLER:
            # 🔑 Change to get_or_create to prevent collisions if already generated
            SellerProfile.objects.get_or_create(user=instance)
        elif instance.role == User.Role.CUSTOMER:
            # 🔑 Change to get_or_create here as well
            CustomerProfile.objects.get_or_create(user=instance)