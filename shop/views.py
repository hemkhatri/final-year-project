import os  # Ensure you import os at the top of the file
from django.views.generic import CreateView, ListView, DetailView
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

    # 👇 Override get_context_data to inject the .env variable into the page template
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch key from environment. Defaults to empty string if missing.
        context['IMGBB_API_KEY'] = os.getenv('IMGBB_API_KEY', '')
        return context

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

class ProductDetailView(DetailView):
    model = Product
    template_name = 'shop/product_detail.html'
    context_object_name = 'product'


# shop/views.py
import requests
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

class ImgBBProxyUploadView(LoginRequiredMixin, View):
    def post(self, request):
        file = request.FILES.get('image')
        if not file:
            return JsonResponse({'success': False, 'error': 'No file provided'}, status=400)
        if file.size > 1 * 1024 * 1024:
            return JsonResponse({'success': False, 'error': 'File exceeds 1MB'}, status=400)

        resp = requests.post(
            'https://api.imgbb.com/1/upload',
            params={'key': os.getenv('IMGBB_API_KEY', '')},
            files={'image': file.read()},
        )
        data = resp.json()
        if data.get('success'):
            return JsonResponse({'success': True, 'url': data['data']['url']})
        return JsonResponse({'success': False, 'error': 'ImgBB upload failed'}, status=502)