# accounts/tasks.py
from celery import shared_task
from .models import AssignmentAttempt, Order, DeliveryBoyProfile
from .services import auto_assign_order

@shared_task
def check_assignment_timeout(attempt_id):
    try:
        attempt = AssignmentAttempt.objects.get(id=attempt_id)
        
        # If the driver hasn't responded after 20 minutes
        if attempt.status == AssignmentAttempt.Status.PENDING:
            attempt.status = AssignmentAttempt.Status.TIMEOUT
            attempt.save()

            order = attempt.order
            driver = attempt.driver

            # Add this driver to the excluded/rejected list so they aren't picked again
            order.rejected_by.add(driver)

            # Free the driver's availability so they can pick up other jobs
            try:
                profile = driver.delivery_profile
                profile.is_busy = False
                profile.save()
            except DeliveryBoyProfile.DoesNotExist:
                pass

            # If the order is still waiting on this specific driver, release it and find someone else
            if order.status == Order.Status.ASSIGNING and order.current_delivery_boy == driver:
                order.current_delivery_boy = None
                order.save()
                
                # Auto-run the assignment algorithm to find the next nearest driver
                auto_assign_order(order.id)

    except AssignmentAttempt.DoesNotExist:
        pass