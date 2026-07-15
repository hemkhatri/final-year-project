from .models import DeliveryBoyProfile, Order

def assign_next_delivery_boy(order):
    # Find next delivery boy who is available and didn't rejected the order

    rejected_ids = list(order.rejected_by.value_list('id', flat = True))
    if order.current_delivery_boy:
        rejected_ids.append(order.current_delivery_boy.id)

    next_driver_profile = DeliveryBoyProfile.get_nearest_available(
        customer_lat = order.delivery_latitude,
        customer_lon= order.delivery_longitude,
        excluded_user_ids= rejected_ids
    )

    if next_driver_profile:
        order.current_delivery_boy = next_driver_profile.user
        order.status = Order.Status.ASSIGNING
        order.save()

        print(f"Order #{order.id} offered to {next_driver_profile.user.username}")
        return True
    
    else:
        order.current_delivery_boy = None
        order.status = Order.Status.PLACED
        order.save()
        print(f"No available delivery boys found for Order #{order.id}")
        return False