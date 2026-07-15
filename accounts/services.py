from django.conf import settings
from django.db import transaction
from django.core.mail import send_mail
from django.urls import reverse

from .models import AssignmentAttempt, DeliveryBoyProfile, Order


def auto_assign_order(order_id):
    """
    Automatically finds the nearest available delivery boy and sends assignment email.
    """

    try:
        order = Order.objects.get(id=order_id)
        print(f"\n🔍 Processing Order #{order.id}")
        print(f"📍 Delivery Location: {order.delivery_latitude}, {order.delivery_longitude}")
    except Order.DoesNotExist:
        print(f"❌ Order {order_id} not found!")
        return False

    if order.status in (Order.Status.DELIVERED, Order.Status.CANCELLED):
        print(f"❌ Order already {order.status}")
        return False

    excluded_driver_ids = list(order.rejected_by.values_list("id", flat=True))
    print(f"Excluding drivers: {excluded_driver_ids}")

    # Find nearest driver
    nearest_profile = DeliveryBoyProfile.get_nearest_available(
        customer_lat=order.delivery_latitude,
        customer_lon=order.delivery_longitude,
        excluded_user_ids=excluded_driver_ids,
    )

    if nearest_profile is None:
        print(f"❌ No available delivery boys!")
        order.current_delivery_boy = None
        order.status = Order.Status.PLACED
        order.save(update_fields=["current_delivery_boy", "status"])
        return False

    driver = nearest_profile.user
    print(f"✅ Found driver: {driver.username} (ID: {driver.id})")
    print(f"📧 Email: {driver.email}")
    print(f"📍 Driver Location: {nearest_profile.latitude}, {nearest_profile.longitude}")

    # 🛑 CHANGED: We DO NOT mark the driver profile as busy here anymore!
    # They stay available to check their dashboard / receive other matches until they accept.
    print(f"📢 Driver left available while waiting for confirmation")

    # Reserve order assignment state
    order.current_delivery_boy = driver
    order.status = Order.Status.ASSIGNING
    order.save(update_fields=["current_delivery_boy", "status"])

    # Log assignment attempt
    attempt = AssignmentAttempt.objects.create(
        order=order,
        driver=driver,
        status=AssignmentAttempt.Status.PENDING,
    )
    print(f"📝 Assignment Attempt #{attempt.id} created")

    # 🛠️ FIX: Unified namespacing for both URLs to prevent Reverse Match exceptions
    accept_url = (
        f"{settings.SITE_URL}"
        f"{reverse('accounts:accept_delivery', args=[attempt.id])}"
    )

    reject_url = (
        f"{settings.SITE_URL}"
        f"{reverse('accounts:reject_delivery', args=[attempt.id])}"
    )

    subject = f"🚚 New Delivery Assignment - Order #{order.id}"

    message = f"""Hello {driver.username},

A new delivery has been assigned to you.

Order ID: {order.id}
Customer: {order.customer.username}

You have 30 minutes to respond.

✅ Accept Delivery:
{accept_url}

❌ Reject Delivery:
{reject_url}

If you do not respond within 30 minutes, this delivery will automatically be offered to another nearby driver.

Thank you!"""

    try:
        print(f"📧 Sending email to {driver.email}...")
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[driver.email],
            fail_silently=False,
        )
        print(f"✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Email failed: {str(e)}")
        # Roll back assignment states
        order.current_delivery_boy = None
        order.status = Order.Status.PLACED
        order.save(update_fields=["current_delivery_boy", "status"])

        attempt.delete()
        return False

    from .tasks import check_assignment_timeout
    check_assignment_timeout.apply_async(args=[attempt.id], countdown=1800)
    print(f"⏱️  Assignment timeout task scheduled (30 mins)\n")

    return True


@transaction.atomic
def assign_next_delivery_boy(order):
    """
    Releases the currently assigned delivery boy (if any) and
    immediately assigns the next nearest available delivery boy.
    """

    # Accept either an Order instance or an order ID
    if isinstance(order, int):
        order = Order.objects.select_for_update().get(id=order)
    else:
        order = Order.objects.select_for_update().get(id=order.id)

    # 🛑 CHANGED: Free the current driver if they were marked busy 
    # (e.g., if they are being skipped/reassigned later after accepting)
    if order.current_delivery_boy:
        try:
            profile = order.current_delivery_boy.delivery_profile
            profile.is_busy = False
            profile.save(update_fields=["is_busy"])
        except DeliveryBoyProfile.DoesNotExist:
            pass

    # Remove current assignment
    order.current_delivery_boy = None
    order.status = Order.Status.PLACED
    order.save(update_fields=["current_delivery_boy", "status"])

    # Run your nearest-driver algorithm
    return auto_assign_order(order.id)