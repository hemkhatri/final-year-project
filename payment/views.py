import uuid
import hmac
import hashlib
import base64
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from cart.cart import Cart
from .models import Order, OrderItem
from django.http import HttpResponse

@login_required
def checkout_preview(request):
    
    cart = Cart(request)
    if len(cart) == 0:
        return redirect('cart:cart_detail')
        
    order = Order.objects.create(
        user=request.user,
        total_amount=cart.get_total_price(),
        status='PENDING'
    )
    order.transaction_uuid = f"ORDER-{order.id}-{uuid.uuid4().hex[:6].upper()}"
    order.save()
    
    for item in cart:
        OrderItem.objects.create(
            order=order,
            product=item['product'],
            price=item['price'],
            quantity=item['quantity']
        )
        
    # --- FIX 1: Explicitly format to exactly 2 decimal places ---
    formatted_amount = "{:.2f}".format(float(order.total_amount))
    
    secret_key = "8gBm/:&EnhH.1/q"
    product_code = "EPAYTEST"
    
    # 2. Construct the message string
    message = (
        f"total_amount={formatted_amount},"
        f"transaction_uuid={order.transaction_uuid},"
        f"product_code={product_code}"
    )
    
    # 3. Create the signature by encoding the strings to bytes exactly when hashing
    signature = base64.b64encode(
        hmac.new(
            secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).digest()
    ).decode("utf-8")
    
    context = {
        'order': order,
        'formatted_amount': formatted_amount,
        'signature': signature,
        'product_code': product_code,
    }
    
    return render(request, 'payment/checkout.html', context)


def payment_success(request):

    encoded_data = request.GET.get('data')
    cart = Cart(request)
    cart.clear()
    
    # Optional TODO: Decode the data parameter here to verify payment status and update Order status to 'PAID'
    
    return render(request, 'payment/success.html')

def payment_failure(request):
    """
    eSewa redirects here if the payment fails, cancels, or times out.
    """
    return render(request, 'payment/failure.html')
