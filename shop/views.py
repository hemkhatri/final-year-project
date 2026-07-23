# shop/views.py
import json
from django.core.cache import cache
from django.db.models import Case, When
from shop.tasks import update_product_recommendations_cache
from django.http import JsonResponse
from django.views import View
from django.contrib.auth import authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy
from django.utils.text import slugify
from shop.models import Product, Category, ProductMedia, SearchTag
from django.core.mail import send_mail
from django.conf import settings
from .models import Order, OrderItem, Product
from payment.models import OrderItem as PaymentOrderItem
from django.shortcuts import render, redirect
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from .become_seller import BecomeSellerForm
import random
from datetime import datetime, timedelta



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

        if 'relevant_tags' in data:
            product.relevant_tags = (data.get('relevant_tags') or '').strip()
            update_fields.append('relevant_tags')

        if 'attributes_payload' in data:
            raw_attrs = data.get('attributes_payload')
            try:
                attributes = json.loads(raw_attrs) if isinstance(raw_attrs, str) else raw_attrs
                if not isinstance(attributes, dict):
                    attributes = {}
            except (json.JSONDecodeError, TypeError):
                attributes = {}
            product.attributes = attributes
            update_fields.append('attributes')

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


# shop/views.py


class ProductListView(ListView):
    model = Product
    template_name = "shop/market.html"
    context_object_name = "products"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 1. Recommended Products
        recommended = Product.objects.filter(available=True).order_by(
            "-average_rating", "-created"
        )[:6]
        if not recommended.exists():
            recommended = Product.objects.all().order_by("-created")[:6]
        context["recommended_products"] = recommended

        # 2. Fashion & Apparel
        fashion_category = Category.objects.filter(
            name__iexact="Fashion & Apparel"
        ).first()
        if fashion_category:
            fashion_cat_ids = Category.objects.filter(
                Q(id=fashion_category.id)
                | Q(parent=fashion_category)
                | Q(parent__parent=fashion_category)
            ).values_list("id", flat=True)
            clothes_products = Product.objects.filter(
                category_id__in=fashion_cat_ids, available=True
            ).order_by("-created")[:6]
        else:
            clothes_products = []
        context["clothes_products"] = clothes_products

        # 3. Dynamic Flash Sale
        flash_products = cache.get("daily_flash_sale_products")
        if flash_products is None:
            all_available_ids = list(
                Product.objects.filter(available=True).values_list(
                    "id", flat=True
                )
            )
            sample_size = min(len(all_available_ids), 6)
            if sample_size > 0:
                selected_ids = random.sample(all_available_ids, sample_size)
                flash_products = list(
                    Product.objects.filter(id__in=selected_ids)
                )
            else:
                flash_products = []

            now = datetime.now()
            next_midnight = datetime.combine(
                now.date() + timedelta(days=1), datetime.min.time()
            )
            seconds_until_midnight = int((next_midnight - now).total_seconds())
            cache.set(
                "daily_flash_sale_products",
                flash_products,
                max(seconds_until_midnight, 60),
            )
        context["flash_products"] = flash_products

        # ---------------------------------------------------------
        # 4. "Only For You" - Initial Batch (12 products)
        # ---------------------------------------------------------
        context["only_for_you_products"] = Product.objects.filter(
            available=True
        ).order_by("?")[:12]

        return context


# AJAX View for loading more products
def load_more_only_for_you(request):
    offset = int(request.GET.get("offset", 0))
    limit = 12

    # Query next batch of available products randomly/by order
    products = Product.objects.filter(available=True).order_by("?")[
        offset : offset + limit
    ]
    total_products = Product.objects.filter(available=True).count()

    products_data = []
    for p in products:
        products_data.append(
            {
                "name": p.name,
                "slug": p.slug,
                "price": str(p.price),
                "cover_image": (
                    p.cover_image
                    if p.cover_image
                    else "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500"
                ),
                "rating": (
                    f"{p.average_rating:.1f}" if p.average_rating else "0.0"
                ),
            }
        )

    has_more = (offset + limit) < total_products

    return JsonResponse({"products": products_data, "has_more": has_more})

class ProductDetailView(DetailView):
    model = Product
    template_name = "shop/product_detail.html"
    context_object_name = "product"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object

        # Consistent cache key using product.slug
        cache_key = f"rec_product_{product.slug}"
        rec_ids = cache.get(cache_key)

        if not rec_ids:
            user_id = (
                self.request.user.id
                if self.request.user.is_authenticated
                else None
            )
            try:
                # Pass product_slug to the task instead of product_id
                update_product_recommendations_cache.delay(
                    product_slug=product.slug, user_id=user_id
                )
            except Exception:
                pass

            # Fallback for current request
            recommendations = (
                Product.objects.filter(available=True)
                .exclude(id=product.id)
                .order_by("-average_rating", "-created")[:4]
            )
        else:
            preserved_order = Case(
                *[When(id=pk, then=pos) for pos, pk in enumerate(rec_ids)]
            )
            recommendations = Product.objects.filter(
                id__in=rec_ids, available=True
            ).order_by(preserved_order)

        context["recommended_products"] = recommendations
        return context

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
        attributes_payload = request.POST.get('attributes_payload', '{}')
        relevant_tags = request.POST.get('relevant_tags', '').strip()

        if not all([name, price, stock, category_id]):
            return JsonResponse({'success': False, 'error': 'Name, price, stock, and category are required.'}, status=400)

        try:
            price = float(price)
            stock = int(stock)
            category = Category.objects.get(id=category_id)
        except (ValueError, TypeError, Category.DoesNotExist):
            return JsonResponse({'success': False, 'error': 'Invalid pricing, stock, or category.'}, status=400)

        # Parse the dynamic category attributes (checkboxes/textboxes from the schema)
        try:
            attributes = json.loads(attributes_payload)
            if not isinstance(attributes, dict):
                attributes = {}
        except json.JSONDecodeError:
            attributes = {}

        # Create the base product
        product = Product.objects.create(
            seller=request.user,
            category=category,
            name=name,
            slug=slugify(name),
            description=description,
            price=price,
            stock=stock,
            attributes=attributes,
            relevant_tags=relevant_tags
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
            pass  # Failsafe if payload is empty or malformed

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
        ).select_related('order', 'order__buyer', 'product').order_by('-order_id')
        
        data = {'new': [], 'processing': [], 'shipped': [], 'returns': []}

        for item in order_items:
            current_status = (item.order.status or 'NEW').strip().upper()
            item_total = float(item.price * item.quantity)

            o_id = item.order.id if item.order else "0"
            o_date = item.order.created_at.strftime('%B %d, %Y') if (item.order and item.order.created_at) else "N/A"
            
            # Fix customer resolution check from .user to .buyer
            buyer = "Guest Buyer"
            if item.order and item.order.buyer:
                buyer = item.order.buyer.get_full_name() or item.order.buyer.username

            # Fetch address directly from the verified field string
            shipping_addr = item.order.shipping_address if item.order else "N/A"

            serialized_item = {
                'id': item.id,
                'order_num': f"#{o_id}",
                'date': o_date,
                'total': f"{item_total:.2f}",
                'product_name': item.product.name if item.product else "Unknown Product",
                'quantity': item.quantity,
                'buyer_name': buyer,
                'address': shipping_addr,
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
    # Fetch ONLY top-level categories (categories without a parent)
    # select_related avoids hitting the DB repeatedly when loading subcategories
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')
    
    return render(request, 'shop/category.html', {'categories': categories})



def become_seller_landing(request):
    """
    Renders an introductory space showing marketplace benefits 
    and legal tracking parameters before launching the form entry.
    """
    return render(request, 'shop/become_seller_landing.html')

def privacy_policy(request):
    """
    render the privacy policies page
    """
    return render(request, 'shop/privacy_policy.html')

@login_required
def become_seller_view(request):
    if request.method == 'POST':
        form = BecomeSellerForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save(commit=False)
            application.user = request.user
            application.save()
            return redirect('shop:market_home')
    else:
        form = BecomeSellerForm()
        
    # 🔑 The key must be 'become_seller' to match your HTML variables!
    return render(request, 'shop/become_seller.html', {'become_seller': form})
    


def careers_landing(request):
    """
    Renders the centralized operations recruitment landing board.
    """
    return render(request, 'shop/careers.html')



def product_search_view(request):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()

    base_products = Product.objects.filter(available=True).select_related('category').prefetch_related('media')
    active_category = None
    category_schema = {}

    # If category slug is supplied directly
    if category_slug:
        active_category = Category.objects.filter(slug=category_slug).first()

    # If user searched for a category name in the search bar (e.g. "Fashion & Apparel")
    elif query:
        matched_cat = Category.objects.filter(name__iexact=query).first()
        if matched_cat:
            active_category = matched_cat
            query = '' # Clear text search so it doesn't filter out products without the exact string

    # 1. APPLY CATEGORY FILTERING & INHERITANCE
    if active_category:
        # Include products in active category OR any child/descendant categories
        child_cats = Category.objects.filter(Q(parent=active_category) | Q(parent__parent=active_category))
        
        if child_cats.exists():
            cat_ids = list(child_cats.values_list('id', flat=True)) + [active_category.id]
            base_products = base_products.filter(category_id__in=cat_ids)
            
            # Combine schema filters from parent and child categories
            for cat in [active_category] + list(child_cats):
                c_schema = cat.get_filter_schema() if hasattr(cat, 'get_filter_schema') else getattr(cat, 'filter_schema', {})
                if isinstance(c_schema, dict):
                    for k, v in c_schema.items():
                        if k not in category_schema:
                            category_schema[k] = []
                        if isinstance(v, list):
                            category_schema[k] = list(set(category_schema[k] + v))
                        elif v and v not in category_schema[k]:
                            category_schema[k].append(v)
        else:
            base_products = base_products.filter(category=active_category)
            category_schema = active_category.get_filter_schema() if hasattr(active_category, 'get_filter_schema') else getattr(active_category, 'filter_schema', {})

    # 2. APPLY TEXT SEARCH QUERY (if not resolved to a category)
    if query:
        keywords = query.split()
        query_filter = Q()
        for word in keywords:
            query_filter &= (
                Q(name__icontains=word) |
                Q(description__icontains=word) |
                Q(category__name__icontains=word) |
                Q(relevant_tags__icontains=word)
            )
        base_products = base_products.filter(query_filter)

    # 3. AGGREGATE PRODUCT ATTRIBUTE COUNTS
    extracted_counts = {}
    for prod in base_products:
        if isinstance(prod.attributes, dict):
            for attr_key, attr_val in prod.attributes.items():
                if attr_key not in extracted_counts:
                    extracted_counts[attr_key] = {}

                val_items = attr_val if isinstance(attr_val, list) else [attr_val]
                for item in val_items:
                    item_str = str(item).strip()
                    if item_str:
                        extracted_counts[attr_key][item_str] = extracted_counts[attr_key].get(item_str, 0) + 1

    # 4. BUILD DYNAMIC SIDEBAR FILTERS
    products = base_products
    has_active_filters = False
    dynamic_filters = []

    allowed_keys = category_schema.keys() if category_schema else extracted_counts.keys()

    for attr_key in allowed_keys:
        options_dict = extracted_counts.get(attr_key, {})
        if not options_dict:
            continue

        selected_values = [v.strip() for v in request.GET.getlist(attr_key) if v.strip()]

        if selected_values:
            has_active_filters = True
            json_q = Q()
            for val in selected_values:
                json_q |= Q(**{f"attributes__{attr_key}__icontains": val})
            products = products.filter(json_q)

        schema_options = category_schema.get(attr_key, [])
        if isinstance(schema_options, str):
            schema_options = [schema_options]

        display_options = schema_options if schema_options else list(options_dict.keys())

        options_list = []
        for opt_val in display_options:
            count = options_dict.get(opt_val, 0)
            if count > 0:
                options_list.append({
                    'value': opt_val,
                    'label': opt_val,
                    'count': count,
                    'is_selected': opt_val in selected_values
                })

        if options_list:
            dynamic_filters.append({
                'id': attr_key,
                'label': attr_key.replace('_', ' ').title(),
                'options': options_list
            })

    products = products.distinct()

    context = {
        'query': query,
        'products': products,
        'count': products.count(),
        'active_category': active_category,
        'dynamic_filters': dynamic_filters,
        'has_active_filters': has_active_filters,
    }

    return render(request, 'shop/search_results.html', context)



def autocomplete_search_view(request):
    query = request.GET.get('term', '').strip()
    data = []

    # Fire only if the user types 2 or more characters
    if len(query) >= 2:
        # SQLite-friendly approach using icontains or complex Q filters
        # __icontains mimics the behavior of autocomplete perfectly for small/mid datasets
        results = Product.objects.filter(
            Q(name__icontains=query),
            available=True
        ).prefetch_related('media')[:6]

        for product in results:
            data.append({
                'name': product.name,
                'slug': product.slug,
                'price': str(product.price),
                # Fallback to standard placeholder if cover_image is empty
                'image': product.cover_image if product.cover_image else 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=150'
            })

    return JsonResponse(data, safe=False)


def market_view(request):
    # Fetch top 6 products regardless of status for testing
    recommended_products = Product.objects.all().order_by("-created")[:6]

    # DEBUG: Print to terminal to see if products exist in the DB
    print(
        "DEBUG recommended_products count:",
        recommended_products.count(),
    )

    context = {
        "recommended_products": recommended_products,
    }
    return render(request, "shop/market.html", context)