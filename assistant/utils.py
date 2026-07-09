# assistant/utils.py
from django.urls import reverse
from shop.models import Product


def get_available_products():
    products = (
        Product.objects.filter(available=True, stock__gt=0)
        .select_related('category', 'seller')
        .prefetch_related('media')
    )

    result = []
    for p in products:
        result.append({
            "name": p.name,
            "price": str(p.price),
            "category": p.category.name,
            "link": get_product_url(p),
            "image": p.cover_image,  # already returns a URL string or None
        })
    return result


def get_product_url(product):
    # Adjust to match your actual URL pattern name for product detail pages
    try:
        return reverse('product_detail', kwargs={'slug': product.slug})
    except Exception:
        return f"/product/{product.slug}/"
    
def get_seller_info():
    from django.contrib.auth import get_user_model
    User = get_user_model()

    sellers = User.objects.filter(products__available=True).distinct()
    return [
        {
            "username": s.username,
            "product_count": s.products.filter(available=True).count(),
        }
        for s in sellers
    ]