"""
HOME PAGE EMAIL SYSTEM
=====================
Send review requests to customers when orders are completed
"""

from django.core.mail import send_mail
from django.template.loader import render_to_string
from home.models import ReviewRequest


def send_review_request_email(order):
    """
    Send review request email when order is marked as completed/delivered
    """
    if not order.user or not order.user.email:
        return False

    # Get all items in the order
    order_items = order.items.all()

    for item in order_items:
        # Check if review request already sent
        existing_request = ReviewRequest.objects.filter(
            customer=order.user,
            product=item.product,
            order_id=order.id
        ).first()

        if existing_request:
            continue  # Skip if already sent

        # Create review request
        review_request = ReviewRequest.objects.create(
            customer=order.user,
            product=item.product,
            order_id=order.id
        )

        # Prepare email context
        context = {
            'customer_name': order.user.first_name or order.user.username,
            'product_name': item.product.name,
            'order_number': order.order_number,
            'product_id': item.product.id,
            'review_url': f"https://yourdomain.com/review/{item.product.id}/"
        }

        # Render email template
        subject = f"Please Review {item.product.name} - Dr Apple Store"
        html_message = render_to_string('emails/review_request.html', context)

        # Send email
        try:
            send_mail(
                subject=subject,
                message=f"Please review {item.product.name},{item.product.product_image} from your recent order",
                from_email='noreply@drapplestore.com',
                recipient_list=[order.user.email],
                html_message=html_message,
                fail_silently=False,
            )
            print(f"✅ Review request email sent to {order.user.email} for {item.product.name}")
        except Exception as e:
            print(f"❌ Failed to send review request: {str(e)}")
            return False

    return True
