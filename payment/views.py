import base64
import hashlib
import hmac
import json
import uuid
import os
from pathlib import Path
from dotenv import load_dotenv
from django.shortcuts import render  # or your existing imports
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from cart.cart import Cart

from .models import Order, OrderItem
from accounts.models import Order as DeliveryOrder
from accounts.services import auto_assign_order

BASE_DIR = Path(__file__).resolve().parent.parent

# 2. Load the .env file explicitly
load_dotenv(BASE_DIR / ".env")


@login_required
def checkout_preview(request):
    """Display checkout form with location picker"""
    cart = Cart(request)
    if len(cart) == 0:
        return redirect("cart:cart_detail")

    if request.method == "POST":
        shipping_name = request.POST.get("shipping_name", "")
        shipping_address = request.POST.get("shipping_address", "")
        phone_number = request.POST.get("phone_number", "")
        delivery_latitude = request.POST.get("latitude", "")
        delivery_longitude = request.POST.get("longitude", "")

        # Validate coordinates
        if not delivery_latitude or not delivery_longitude:
            return render(
                request,
                "payment/checkout.html",
                {
                    "cart_items": cart,
                    "error": "❌ Please select delivery location on the map",
                },
            )

        try:
            delivery_latitude = Decimal(delivery_latitude)
            delivery_longitude = Decimal(delivery_longitude)
        except:
            return render(
                request,
                "payment/checkout.html",
                {"cart_items": cart, "error": "❌ Invalid coordinates"},
            )

        # Create order
        order = Order.objects.create(
            buyer=request.user,
            shipping_name=shipping_name,
            shipping_address=shipping_address,
            phone_number=phone_number,
            delivery_latitude=delivery_latitude,
            delivery_longitude=delivery_longitude,
            total_amount=cart.get_total_price(),
            status="PENDING",
        )
        order.transaction_uuid = f"ORDER-{order.id}-{uuid.uuid4().hex[:6].upper()}"
        order.save()

        # Create order items
        for item in cart:
            OrderItem.objects.create(
                order=order,
                product=item["product"],
                price=item["price"],
                quantity=item["quantity"],
            )

        # Prepare eSewa payment
        formatted_amount = "{:.2f}".format(float(order.total_amount))

        secret_key = os.environ.get("PAYMENT_SECRET_KEY")
        product_code = os.environ.get("PAYMENT_PRODUCT_CODE")

        message = (
            f"total_amount={formatted_amount},"
            f"transaction_uuid={order.transaction_uuid},"
            f"product_code={product_code}"
        )

        signature = base64.b64encode(
            hmac.new(
                secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
            ).digest()
        ).decode("utf-8")

        context = {
            "order": order,
            "formatted_amount": formatted_amount,
            "signature": signature,
            "product_code": product_code,
        }

        return render(request, "payment/checkout.html", context)

    # GET request - show checkout form
    context = {"cart_items": list(cart), "total_price": cart.get_total_price()}
    return render(request, "payment/checkout.html", context)


def payment_success(request):
    """Handle successful eSewa payment"""
    encoded_data = request.GET.get("data")

    if not encoded_data:
        return HttpResponse("Missing eSewa transaction response data.", status=400)

    try:
        decoded_bytes = base64.b64decode(encoded_data)
        decoded_str = decoded_bytes.decode("utf-8")
        response_data = json.loads(decoded_str)

        status = response_data.get("status")
        transaction_uuid = response_data.get("transaction_uuid")

        if status == "COMPLETE":
            order_id = transaction_uuid.split("-")[1]
            shop_order = get_object_or_404(Order, id=order_id)

            if shop_order.status == "PENDING":
                shop_order.status = "PAID"
                shop_order.save()

                cart = Cart(request)
                cart.clear()

                # ===== CREATE DELIVERY ORDER =====
                delivery_order = DeliveryOrder.objects.create(
                    customer=shop_order.buyer,
                    delivery_latitude=shop_order.delivery_latitude,
                    delivery_longitude=shop_order.delivery_longitude,
                    status=DeliveryOrder.Status.PLACED,
                )

                # Link shop order to delivery order
                shop_order.transaction_uuid = (
                    f"{shop_order.transaction_uuid}-DELIVERY-{delivery_order.id}"
                )
                shop_order.status = "ASSIGNING"
                shop_order.save()

                # ===== SAFE AUTO-ASSIGNMENT WRAPPER =====
                assigned = False
                try:
                    assigned = auto_assign_order(delivery_order.id)
                    print(
                        f"🚚 Delivery Order #{delivery_order.id} - Assigned: {assigned}"
                    )
                except Exception as assign_error:
                    # Capture assignment layout issues (like missing URL names) safely
                    print(
                        f"⚠️ Payment succeeded, but notification assignment crashed: {str(assign_error)}"
                    )

                print(f"✅ Payment Success - Order #{order_id}")
                print(
                    f"📍 Delivery Coords: {shop_order.delivery_latitude}, {shop_order.delivery_longitude}"
                )

                context = {
                    "shop_order": shop_order,
                    "delivery_order": delivery_order,
                    "assigned_success": assigned,
                }
                return render(request, "payment/success.html", context)
            else:
                return render(
                    request, "payment/success.html", {"shop_order": shop_order}
                )

        else:
            return HttpResponse(
                "eSewa payment transaction was not complete.", status=400
            )

    except Exception as e:
        print(f"❌ Payment Error: {str(e)}")
        return HttpResponse(
            f"Error parsing checkout payment success: {str(e)}", status=400
        )


def payment_failure(request):
    """Handle failed eSewa payment"""
    return render(request, "payment/failure.html")
