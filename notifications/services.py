"""
Every trigger point in the app (order creation, receipt upload, review
created, signup, low stock) creates notifications by calling one of the
notify_* functions below, rather than creating Notification objects
directly — keeps the "who receives this" rule (all active staff users) and
the dedupe logic in exactly one place.
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from .models import Notification

User = get_user_model()


def _staff_users():
    return User.objects.filter(is_staff=True, is_active=True)


def notify(notification_type, title, message, link='', related_object=None, dedupe_unread=False):
    """
    Creates a Notification for every active staff user.

    dedupe_unread=True skips creating a new notification for a given
    recipient + type + related object if an UNREAD one already exists for
    it — used for low/out-of-stock so saving a still-low product repeatedly
    doesn't spam duplicate alerts every time admin touches it.
    """
    content_type = None
    object_id = None
    if related_object is not None:
        content_type = ContentType.objects.get_for_model(related_object)
        object_id = related_object.pk

    created = []
    for staff_user in _staff_users():
        if dedupe_unread and content_type is not None:
            already_unread = Notification.objects.filter(
                recipient=staff_user,
                notification_type=notification_type,
                content_type=content_type,
                object_id=object_id,
                is_read=False,
            ).exists()
            if already_unread:
                continue

        created.append(Notification.objects.create(
            recipient=staff_user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            content_type=content_type,
            object_id=object_id,
        ))
    return created


def notify_new_order(order):
    """
    Called once, at order creation (inside checkout()'s POST branch) —
    never on GET/page-render, so refreshing an order page can't trigger
    this again.
    """
    admin_path = 'pickuporder' if order.fulfillment_method == order.FULFILLMENT_PICKUP else 'deliveryorder'
    notify(
        Notification.TYPE_NEW_ORDER,
        'New Order Received',
        f'Order #{order.order_number} has been placed.',
        link=f'/admin/orders/{admin_path}/{order.id}/change/',
        related_object=order,
    )


def notify_receipt_uploaded(order):
    """
    Called once per order — payment_confirmation()'s POST branch already
    rejects a second receipt upload for the same order (checked before
    this would ever be called again), so no dedupe needed here either.
    """
    admin_path = 'pickuporder' if order.fulfillment_method == order.FULFILLMENT_PICKUP else 'deliveryorder'
    notify(
        Notification.TYPE_RECEIPT_UPLOADED,
        'Payment Receipt Uploaded',
        f'A customer uploaded a payment receipt for Order #{order.order_number}.',
        link=f'/admin/orders/{admin_path}/{order.id}/change/',
        related_object=order,
    )


def notify_new_review(review):
    product_name = getattr(getattr(review, 'product', None), 'name', 'a product')
    notify(
        Notification.TYPE_NEW_REVIEW,
        'New Product Review',
        f'A new review has been submitted for {product_name}.',
        link=f'/admin/product_reviews/productreview/{review.id}/change/',
        related_object=review,
    )


def notify_new_customer(user):
    display_name = user.get_full_name() or user.email or user.username
    notify(
        Notification.TYPE_NEW_CUSTOMER,
        'New Customer Registered',
        f'{display_name} created an account.',
        link=f'/admin/auth/user/{user.id}/change/',
        related_object=user,
    )


def notify_low_stock(product):
    """
    Reuses Product.is_low_stock (already exists — used on product_detail.html
    and the badge on that page) rather than inventing a second threshold
    definition, so "low stock" always means the same thing everywhere.
    """
    if product.stock_quantity <= 0:
        notify(
            Notification.TYPE_OUT_OF_STOCK,
            'Product Out of Stock',
            f'{product.name} is now out of stock.',
            link=f'/admin/product/product/{product.id}/change/',
            related_object=product,
            dedupe_unread=True,
        )
    elif product.is_low_stock:
        notify(
            Notification.TYPE_LOW_STOCK,
            'Low Stock Warning',
            f'{product.name} is running low ({product.stock_quantity} left).',
            link=f'/admin/product/product/{product.id}/change/',
            related_object=product,
            dedupe_unread=True,
        )