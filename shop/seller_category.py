from django import forms
from .models import Product, Category

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['category', 'name', 'price', 'stock', 'description', 'attributes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing an existing product or category is passed in POST data
        category_id = self.data.get('category') or (self.instance.category_id if self.instance else None)
        
        if category_id:
            category = Category.objects.filter(id=category_id).first()
            if category:
                schema = category.get_filter_schema()
                current_attributes = self.instance.attributes if self.instance else {}

                # Dynamically construct select fields based on the category's JSON schema
                for key, options in schema.items():
                    if not options:
                        continue
                    
                    # Convert single string options into a list
                    option_list = options if isinstance(options, list) else [options]
                    choices = [(opt, opt) for opt in option_list]

                    field_name = f"attr_{key}"
                    
                    # Create Select field (or MultipleChoiceField if seller can pick multiple sizes/colors)
                    self.fields[field_name] = forms.MultipleChoiceField(
                        choices=choices,
                        required=False,
                        widget=forms.CheckboxSelectMultiple, # Or forms.Select for single picks
                        label=key,
                        initial=current_attributes.get(key, [])
                    )

    def save(self, commit=True):
        product = super().save(commit=False)
        
        # Save dynamically generated attribute fields into the product.attributes JSON field
        attributes_data = {}
        for field_name, value in self.cleaned_data.items():
            if field_name.startswith('attr_') and value:
                clean_key = field_name.replace('attr_', '')
                attributes_data[clean_key] = value

        product.attributes = attributes_data

        if commit:
            product.save()
            self.save_m2m()
        return product