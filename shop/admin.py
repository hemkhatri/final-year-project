# shop/admin.py
from django.contrib import admin
from .models import Category, Product

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'parent']
    list_filter = ['parent']  # Allows you to filter by top-level or subcategories easily
    prepopulated_fields = {'slug': ('name',)}

admin.site.register(Product)