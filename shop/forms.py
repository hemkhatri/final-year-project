# shop/forms.py
from django import forms
from django.core.exceptions import ValidationError
import json
from .models import Product

class InteractiveProductForm(forms.ModelForm):
    # This hidden field collects all media urls generated on the frontend as a JSON string string array
    media_payload = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'stock', 'category']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:outline-hidden'}),
            'description': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border rounded-lg border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:outline-hidden', 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:outline-hidden', 'step': '0.01'}),
            'stock': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:outline-hidden'}),
            'category': forms.Select(attrs={'class': 'w-full px-4 py-2 border rounded-lg border-gray-300 focus:ring-2 focus:ring-indigo-500 focus:outline-hidden'}),
        }

    def clean_media_payload(self):
        payload = self.cleaned_data.get('media_payload')
        if not payload:
            return []
        try:
            media_list = json.loads(payload) # Format structural rule expected: [{"type": "IMAGE"/"VIDEO", "url": "..."}]
            
            # Enforce limits on the backend level as well
            video_count = sum(1 for item in media_list if item['type'] == 'VIDEO')
            image_count = sum(1 for item in media_list if item['type'] == 'IMAGE')
            
            if video_count > 1:
                raise ValidationError("You can upload a maximum of 1 YouTube video link.")
            if video_count + image_count > 10:
                raise ValidationError("Total combined images and videos cannot exceed 10.")
                
            return media_list
        except ValueError:
            raise ValidationError("Invalid media data format submitted.")