from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from shop.models import Product # Adjust model path as needed
from .cart import Cart

@require_POST
def cart_add(request, product_id):
    """
    View to handle adding an item to the cart from market.html
    """
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    
    # Grab quantity from post request if available (e.g. from a details page input), 
    # default to 1 for the quick market shelf grid button click.
    quantity = int(request.POST.get('quantity', 1))
    override_quantity = request.POST.get('override', False)
    
    cart.add(product=product, quantity=quantity, override_quantity=override_quantity)
    
    # Redirect safely back to the page the user was looking at
    return redirect(request.META.get('HTTP_REFERER', 'market'))


@require_POST
def cart_remove(request, product_id):
    """
    View to handle removing an item from within the checkout/cart layout page
    """
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product)
    return redirect('cart:cart_detail')


def cart_detail(request):
    """
    View to render the dedicated shopping cart listing overview page
    """
    cart = Cart(request)
    return render(request, 'cart/cart_items.html', {'cart': cart})