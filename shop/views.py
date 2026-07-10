# shop/views.py
import json, os
from django.http import JsonResponse
from django.views import View
from django.contrib.auth import authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy
from django.utils.text import slugify
from shop.models import Product, Category, ProductMedia
from django.core.mail import send_mail
from django.conf import settings
from .models import Order, OrderItem, Product
from payment.models import OrderItem as PaymentOrderItem
from django.shortcuts import render


# shop/views.py
@method_decorator(csrf_protect, name='dispatch')
class ProductUpdateAjaxView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk, seller=request.user)
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Product not found or not yours.'}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid request data.'}, status=400)

        name = data.get('name', '').strip()
        price = data.get('price')
        stock = data.get('stock')

        if not name:
            return JsonResponse({'success': False, 'error': 'Name cannot be empty.'}, status=400)

        try:
            price = float(price)
            stock = int(stock)
            if price < 0 or stock < 0:
                raise ValueError
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'error': 'Invalid price or stock value.'}, status=400)

        product.name = name
        product.price = price
        product.stock = stock
        update_fields = ['name', 'price', 'stock']

        # Optional fields — only present when editing via the full pencil-edit form
        if 'description' in data:
            product.description = data.get('description', '').strip()
            update_fields.append('description')

        if 'category' in data and data.get('category'):
            try:
                category = Category.objects.get(id=data['category'])
                product.category = category
                update_fields.append('category')
            except (Category.DoesNotExist, ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Invalid category.'}, status=400)

        product.save(update_fields=update_fields)

        # Optional: append newly attached media (existing media is left untouched)
        if 'media_payload' in data:
            try:
                media_items = json.loads(data['media_payload']) if isinstance(data['media_payload'], str) else data['media_payload']
                for item in media_items:
                    ProductMedia.objects.create(
                        product=product,
                        media_type=item.get('type', 'IMAGE'),
                        url=item.get('url')
                    )
            except (json.JSONDecodeError, TypeError):
                pass

        return JsonResponse({
            'success': True,
            'product': {
                'id': product.pk, 'name': product.name,
                'price': str(product.price), 'stock': product.stock
            }
        })

@method_decorator(csrf_protect, name='dispatch')
class ProductDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk, seller=request.user)
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Product not found or not yours.'}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid request data.'}, status=400)

        password = data.get('password', '')
        if not password:
            return JsonResponse({'success': False, 'error': 'Password is required.'}, status=400)

        user = authenticate(request, username=request.user.username, password=password)
        if user is None:
            return JsonResponse({'success': False, 'error': 'Incorrect password.'}, status=403)

        product_name = product.name
        product.delete()
        return JsonResponse({'success': True, 'message': f'"{product_name}" was deleted.'})


class ProductListView(ListView):
    model = Product
    template_name = 'shop/market.html'
    context_object_name = 'products'


class ProductDetailView(DetailView):
    model = Product
    template_name = 'shop/product_detail.html'
    context_object_name = 'product'


class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    fields = ['name', 'price', 'stock']  # Adjust fields based on your Product model fields
    template_name = 'shop/product_form.html'
    success_url = reverse_lazy('market_home')


@method_decorator(csrf_protect, name='dispatch')
class ProductCreateAjaxView(LoginRequiredMixin, View):
    def post(self, request):
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        category_id = request.POST.get('category')
        media_payload = request.POST.get('media_payload', '[]')

        if not all([name, price, stock, category_id]):
            return JsonResponse({'success': False, 'error': 'Name, price, stock, and category are required.'}, status=400)

        try:
            price = float(price)
            stock = int(stock)
            category = Category.objects.get(id=category_id)
        except (ValueError, TypeError, Category.DoesNotExist):
            return JsonResponse({'success': False, 'error': 'Invalid pricing, stock, or category.'}, status=400)

        # Create the base product
        product = Product.objects.create(
            seller=request.user,
            category=category,
            name=name,
            slug=slugify(name),
            description=description,
            price=price,
            stock=stock
        )

        # Process the linked media from ImgBB and YouTube
        try:
            media_items = json.loads(media_payload)
            for item in media_items:
                ProductMedia.objects.create(
                    product=product,
                    media_type=item.get('type', 'IMAGE'),
                    url=item.get('url')
                )
        except json.JSONDecodeError:
            pass # Failsafe if payload is empty or malformed

        return JsonResponse({'success': True, 'product_id': product.pk})
    

@method_decorator(csrf_protect, name='dispatch')
class CreateOrderAjaxView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            items = data.get('items', []) # Expected format: [{'product_id': 1, 'quantity': 2}]
            
            if not items:
                return JsonResponse({'success': False, 'error': 'No items in order.'}, status=400)

            # 1. Create base order
            order = Order.objects.create(
                buyer=request.user,
                total_amount=data.get('total_amount', 0.0),
                shipping_name=data.get('shipping_name', request.user.get_full_name()),
                shipping_address=data.get('shipping_address', '')
            )

            # Track sellers involved for notification emails
            sellers_to_notify = {}

            # 2. Build items and capture seller links
            for item in items:
                product = Product.objects.get(id=item['product_id'])
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=int(item['quantity']),
                    price=product.price
                )
                
                # Group notifications by seller
                if product.seller not in sellers_to_notify:
                    sellers_to_notify[product.seller] = []
                sellers_to_notify[product.seller].append(f"{item['quantity']}x {product.name}")

            # 3. Dispatched transactional emails background lines
            for seller, product_strings in sellers_to_notify.items():
                if seller.email:
                    send_mail(
                        subject=f"🎉 New Order Received: #{order.id}!",
                        message=f"Hello {seller.username},\n\nYou have received a new order for your store.\n\nItems:\n" + "\n".join(product_strings) + f"\n\nFulfill this order via your Seller Hub.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[seller.email],
                        fail_silently=True,
                    )

            return JsonResponse({'success': True, 'order_id': order.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

class SellerOrdersJsonView(LoginRequiredMixin, View):
    def get(self, request):
        order_items = PaymentOrderItem.objects.filter(
            product__seller=request.user
        ).select_related('order', 'order__user', 'product').order_by('-order_id')

        data = {'new': [], 'processing': [], 'shipped': [], 'returns': []}

        for item in order_items:
            current_status = (item.fulfillment_status or 'NEW').strip().upper()
            item_total = float(item.price * item.quantity)

            o_id = item.order.id if item.order else "0"
            o_date = item.order.created_at.strftime('%B %d, %Y') if (item.order and item.order.created_at) else "N/A"
            buyer = "Guest Buyer"
            if item.order and item.order.user:
                buyer = item.order.user.get_full_name() or item.order.user.username

            serialized_item = {
                'id': item.id,
                'order_num': f"#{o_id}",
                'date': o_date,
                'total': f"{item_total:.2f}",
                'product_name': item.product.name if item.product else "Unknown Product",
                'quantity': item.quantity,
                'buyer_name': buyer,
                'address': "N/A",
                'status': current_status.lower()
            }

            if current_status in ('NEW', 'PENDING'):
                data['new'].append(serialized_item)
            elif current_status in ('PROCESSING', 'PAID'):
                data['processing'].append(serialized_item)
            elif current_status == 'SHIPPED':
                data['shipped'].append(serialized_item)
            elif current_status == 'RETURNS':
                data['returns'].append(serialized_item)
            else:
                data['new'].append(serialized_item)

        response = JsonResponse({'success': True, 'orders': data})
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    

def category_list_view(request):
    categories = Category.objects.all()
    return render(request, 'shop/category.html', {'categories': categories})
