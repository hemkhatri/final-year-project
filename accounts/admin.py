# accounts/admin.py
from django.contrib import admin
from .models import DeliveryBoyProfile, AssignmentAttempt

@admin.register(DeliveryBoyProfile)
class DeliveryBoyProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_available', 'is_busy', 'vechile_type', 'latitude', 'longitude', 'get_email']
    list_filter = ['is_available', 'is_busy', 'vechile_type']
    search_fields = ['user__username', 'licence_number']
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'

@admin.register(AssignmentAttempt)
class AssignmentAttemptAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'driver', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    readonly_fields = ['created_at']