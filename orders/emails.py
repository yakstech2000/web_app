from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_payment_confirmed_email(order):
    """
    Send email when admin confirms payment (status: pending → paid).
    No branching needed here in Python — order_payment_confirmed.html
    itself branches on order.fulfillment_method to show delivery address
    vs. pickup location.
    """
    subject = f"Payment Confirmed - Order {order.order_number}"

    context = {
        'order': order,
        'items': order.items.all(),
        'total_items': order.get_total_items(),
    }

    html_message = render_to_string('emails/order_payment_confirmed.html', context)

    send_mail(
        subject=subject,
        message=f"Your payment for order {order.order_number} has been confirmed!",
        from_email='noreply@drapplestore.com',
        recipient_list=[order.email],
        html_message=html_message,
        fail_silently=False,
    )

    print(f"✅ Payment confirmed email sent to {order.email}")


def send_order_shipped_email(order):
    """
    Send email when order status changes to 'completed'.

    Delivery orders get the existing "shipped" email with a tracking number.
    Pickup orders get a separate "ready for pickup" email instead — tracking
    numbers and shipping language don't apply to a pickup, so this branches
    to a different template entirely rather than trying to force one
    template to cover both cases. Callers (e.g. admin.py) don't need to
    know which one gets used — they just call this function either way.
    """
    if order.fulfillment_method == order.FULFILLMENT_PICKUP:
        subject = f"Your Order Is Ready for Pickup - {order.order_number}"
        context = {
            'order': order,
            'items': order.items.all(),
        }
        html_message = render_to_string('emails/order_ready_pickup.html', context)
        plain_message = f"Your order {order.order_number} is ready for pickup!"
        log_label = "Ready-for-pickup"
    else:
        subject = f"Your Order Has Been Shipped - {order.order_number}"
        context = {
            'order': order,
            'items': order.items.all(),
            'tracking_number': f"TRACK{order.id}{order.pk}",  # Generate a tracking number
        }
        html_message = render_to_string('emails/order_shipped.html', context)
        plain_message = f"Your order {order.order_number} has been shipped!"
        log_label = "Shipped"

    send_mail(
        subject=subject,
        message=plain_message,
        from_email='noreply@drapplestore.com',
        recipient_list=[order.email],
        html_message=html_message,
        fail_silently=False,
    )

    print(f"✅ {log_label} email sent to {order.email}")


def send_order_cancelled_email(order):
    """
    Send email when order is cancelled (any status → cancelled).
    No delivery/pickup branching needed — order_cancelled.html doesn't
    reference an address or pickup location either way.
    """
    subject = f"Order Cancelled - {order.order_number}"

    context = {
        'order': order,
        'items': order.items.all(),
    }

    html_message = render_to_string('emails/order_cancelled.html', context)

    send_mail(
        subject=subject,
        message=f"Your order {order.order_number} has been cancelled.",
        from_email='noreply@drapplestore.com',
        recipient_list=[order.email],
        html_message=html_message,
        fail_silently=False,
    )

    print(f"✅ Cancelled email sent to {order.email}")