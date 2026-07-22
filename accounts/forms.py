# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

class CustomUserCreationForm(UserCreationForm):
    full_name = forms.CharField(max_length=255, required=True, label="Full Name")
    phone_number = forms.CharField(max_length=20, required=True, label="Phone Number")
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=True, label="Address")
    
    # Explicitly defining choices/widgets for gender and age
    gender = forms.ChoiceField(
        choices=User.Gender.choices, 
        required=False, 
        label="Gender"
    )
    age = forms.IntegerField(
        min_value=1, 
        max_value=120, 
        required=False, 
        label="Age",
        widget=forms.NumberInput(attrs={'placeholder': 'e.g. 25'})
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + (
            'full_name', 
            'email', 
            'phone_number', 
            'address', 
            'gender', 
            'age',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_css = "w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-2 transition-all duration-200"
        
        for field_name, field in self.fields.items():
            if self.errors and field_name in self.errors:
                field.widget.attrs['class'] = f"{base_css} border-red-500 focus:ring-red-500"
            else:
                field.widget.attrs['class'] = f"{base_css} border-gray-300 focus:ring-indigo-500"