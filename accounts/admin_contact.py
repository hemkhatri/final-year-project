from django import forms
from .models import SupportTicket, Order

class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ['order', 'category', 'subject', 'description']
        
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Dynamically restrict the order dropdown to items relevant to this specific user profile
        if user:
            if user.role == "CUSTOMER":
                self.fields['order'].queryset = Order.objects.filter(customer=user).order_by('-created_at')
            elif user.role == "DELIVERY_BOY":
                self.fields['order'].queryset = Order.objects.filter(current_delivery_boy=user).order_by('-created_at')
            elif user.role == "SELLER":
                # If your orders hook directly into products sold by the seller:
                self.fields['order'].queryset = Order.objects.filter(shop_order_id__isnull=False).order_by('-created_at')
        
        # Make order field optional (in case it's a general app issue)
        self.fields['order'].required = False