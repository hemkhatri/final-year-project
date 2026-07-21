from django import forms
from django.contrib import admin
from .models import Category, Product
from django.core.exceptions import ValidationError

# ==============================================================================
# DYNAMIC FORM FACTORY
# ==============================================================================

def get_dynamic_product_form(category=None, product_instance=None):
    schema = category.get_filter_schema() if category else {}
    saved_attributes = (
        product_instance.attributes 
        if (product_instance and isinstance(product_instance.attributes, dict)) 
        else {}
    )

    form_fields = {
        'Meta': type('Meta', (), {
            'model': Product,
            'fields': '__all__',
            'widgets': {
                'attributes': forms.HiddenInput(),
                'description': forms.Textarea(attrs={'rows': 5, 'style': 'width: 90%; max-width: 800px;'}),
                # 🔑 WIDENS TAG FIELDS VISUALLY WITHOUT SystemCheckError
                'tags': forms.SelectMultiple(attrs={'style': 'width: 90%; max-width: 800px; height: 180px;'}),
                'relevant_tags': forms.Textarea(attrs={'rows': 3, 'style': 'width: 90%; max-width: 800px;'}),
            }
        })
    }

    # Inject Category Schema Fields
    for attr_key, options in schema.items():
        field_name = f"dynamic_attr_{attr_key}"
        current_value = saved_attributes.get(attr_key)
        formatted_label = attr_key.replace('_', ' ').title()

        if options is None:
            initial_val = current_value if current_value is not None else ''
            form_fields[field_name] = forms.CharField(
                required=False,
                initial=initial_val,
                label=formatted_label,
                widget=forms.TextInput(attrs={'class': 'vTextField', 'style': 'width: 60%; min-width: 300px;'})
            )
        elif isinstance(options, list) and len(options) > 0:
            choices = [(opt, opt) for opt in options]
            initial_val = current_value if isinstance(current_value, list) else ([current_value] if current_value else [])
            form_fields[field_name] = forms.MultipleChoiceField(
                choices=choices,
                required=False,
                initial=initial_val,
                label=formatted_label,
                widget=forms.CheckboxSelectMultiple(attrs={'class': 'dynamic-checkbox-group'})
            )
        else:
            initial_val = current_value if current_value is not None else (options if isinstance(options, str) else '')
            form_fields[field_name] = forms.CharField(
                required=False,
                initial=initial_val,
                label=formatted_label,
                widget=forms.TextInput(attrs={'class': 'vTextField', 'style': 'width: 60%; min-width: 300px;'})
            )

    def clean(self):
        cleaned_data = super(self.__class__, self).clean()

        # Bypass validation for read-only metric fields
        readonly_metrics = ['total_views', 'total_search_appears', 'total_bought', 'total_reviews', 'average_rating']
        for metric in readonly_metrics:
            if metric in self.errors:
                del self.errors[metric]
            if product_instance and hasattr(product_instance, metric):
                cleaned_data[metric] = getattr(product_instance, metric)

        # Raise remaining errors if any exist
        if self.errors:
            error_details = [f"[{f}]: {', '.join(errs)}" for f, errs in self.errors.items()]
            raise ValidationError(f"Validation Failed! Specific field errors: {' | '.join(error_details)}")

        return cleaned_data

    # Custom Save Handler
    def save(self, commit=True):
        product = super(self.__class__, self).save(commit=False)
        attributes_data = {}

        # Package dynamic schema attributes into the JSON field
        for f_name, val in self.cleaned_data.items():
            if f_name.startswith('dynamic_attr_'):
                if val in [None, '', []]:
                    continue
                real_key = f_name.replace('dynamic_attr_', '')
                attributes_data[real_key] = val

        product.attributes = attributes_data

        if commit:
            product.save()
            self.save_m2m()
        return product

    form_fields['clean'] = clean
    form_fields['save'] = save
    return type('DynamicProductForm', (forms.ModelForm,), form_fields)


# ==============================================================================
# ADMIN CONFIGURATIONS
# ==============================================================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'parent', 'color']
    list_filter = ['parent']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'parent')
        }),
        ('Branding & Display', {
            'fields': ('image_url', 'color'),
            'classes': ('collapse',),
        }),
        ('Filter Schema (JSON Engine)', {
            'fields': ('filter_schema',),
            'description': (
                '<b>Parent Category Format:</b> <code>{"Size": null, "Color": null}</code><br>'
                '<b>Child Category Format:</b> <code>{"Size": ["XS", "S", "M", "L"], "Brand": "Nike"}</code>'
            )
        }),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'stock', 'available', 'seller']
    list_filter = ['available', 'category', 'created']
    search_fields = ['name', 'description', 'seller__username']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created', 'total_views', 'total_search_appears', 'total_bought', 'total_reviews', 'average_rating']
    filter_horizontal = ('tags',)  # Only apply to standard ManyToMany fields!

    def get_form(self, request, obj=None, **kwargs):
        """Build form with dynamic schema fields."""
        category = None
        if obj and obj.category_id:
            category = obj.category
        elif request.method == 'POST' and request.POST.get('category'):
            try:
                category = Category.objects.get(id=int(request.POST.get('category')))
            except (Category.DoesNotExist, ValueError, TypeError):
                pass

        return get_dynamic_product_form(category=category, product_instance=obj)

    def get_fieldsets(self, request, obj=None):
        """Organizes form into clear visual fieldsets."""
        form = self.get_form(request, obj)
        all_fields = list(form.base_fields.keys())

        dynamic_fields = [f for f in all_fields if f.startswith('dynamic_attr_')]
        core_fields = [f for f in all_fields if not f.startswith('dynamic_attr_') and f not in ['attributes']]

        fieldsets = [
            ('General Product Information', {
                'fields': [f for f in ['seller', 'category', 'name', 'slug', 'description'] if f in core_fields]
            }),
            ('Pricing & Inventory', {
                'fields': [f for f in ['price', 'stock', 'available'] if f in core_fields]
            }),
        ]

        if dynamic_fields:
            fieldsets.append(
                ('Category Specific Attributes', {
                    'fields': dynamic_fields,
                    'description': 'Configure specific dynamic properties defined by this product category schema.'
                })
            )

        tags_fields = [f for f in ['tags', 'relevant_tags'] if f in core_fields]
        if tags_fields:
            fieldsets.append(('Search & Tagging', {'fields': tags_fields}))

        metrics_fields = [f for f in self.readonly_fields if f in all_fields]
        if metrics_fields:
            fieldsets.append((
                'Performance Metrics & Analytics', {
                    'fields': metrics_fields,
                    'classes': ('collapse',),
                }
            ))

        return fieldsets