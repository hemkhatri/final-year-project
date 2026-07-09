# shop/views.py
from django.views.generic import CreateView, ListView, DetailView  # Added DetailView here
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils.text import slugify
from shop.models import Product, ProductMedia
from shop.forms import InteractiveProductForm

class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = InteractiveProductForm
    template_name = 'shop/product_form.html'
    success_url = reverse_lazy('seller_dashboard')

    def form_valid(self, form):
        form.instance.seller = self.request.user
        form.instance.slug = slugify(form.instance.name)
        
        # Save product first to establish an ID primary key
        response = super().form_valid(form)
        
        # Process the validated media assets list
        media_items = form.cleaned_data.get('media_payload', [])
        for item in media_items:
            ProductMedia.objects.create(
                product=self.object,
                media_type=item['type'],
                url=item['url']
            )
        return response
    
class ProductListView(ListView):
    model = Product
    template_name = 'shop/market.html'
    context_object_name = 'products'

# Add this class so shop/urls.py stops crashing!
class ProductDetailView(DetailView):
    model = Product
    template_name = 'shop/product_detail.html' # Matches your template file tree
    context_object_name = 'product'