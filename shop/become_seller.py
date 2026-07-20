# shop/become_seller.py
from django import forms
from .models import SellerApplication

class BecomeSellerForm(forms.ModelForm):
    class Meta:
        model = SellerApplication
        exclude = ['user', 'kyc_status', 'created_at']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply unified Tailwind styling across all elements dynamically
        input_class = 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm p-2 border'
        file_class = 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100'
        
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.FileInput):
                field.widget.attrs.update({'class': file_class})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': input_class, 'rows': 3})
            else:
                field.widget.attrs.update({'class': input_class})