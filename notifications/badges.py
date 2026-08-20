"""
Section-level and per-object unread-notification helpers, built entirely
on the existing Notification model — no new model, no duplicate tracking
system. Powers the WhatsApp-style sidebar badges and per-item unread dots.
"""
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count

from .models import Notification

# Maps a notification_type to the sidebar "section" it belongs to. Orders
# are further split into pickup/delivery below, since a single
# notification_type (new_order) covers both fulfillment methods — no
# schema change needed, just filtering the related Order objects.
SECTION_BY_TYPE = {
    Notification.TYPE_NEW_ORDER: 'orders',
    Notification.TYPE_RECEIPT_UPLOADED: 'payments',
    Notification.TYPE_NEW_REVIEW: 'reviews',
    Notification.TYPE_NEW_CUSTOMER: 'customers',
    Notification.TYPE_LOW_STOCK: 'products',
    Notification.TYPE_OUT_OF_STOCK: 'products',
}


def get_section_unread_counts(user):
    """
    Returns e.g.:
        {'orders': 4, 'pickup_orders': 2, 'delivery_orders': 2,
         'payments': 2, 'reviews': 1, 'customers': 0, 'products': 1}

    Bounded to 2-3 queries total regardless of notification volume: one
    grouped count query, plus (only when there are unread order
    notifications at all) one more to split those by fulfillment_method.
    Never touches related objects row-by-row — no N+1.
    """
    base = Notification.objects.filter(recipient=user, is_read=False)

    type_counts = dict(
        base.values('notification_type')
        .annotate(count=Count('id'))
        .values_list('notification_type', 'count')
    )

    counts = {'orders': 0, 'pickup_orders': 0, 'delivery_orders': 0,
              'payments': 0, 'reviews': 0, 'customers': 0, 'products': 0}

    for ntype, n in type_counts.items():
        section = SECTION_BY_TYPE.get(ntype)
        if section:
            counts[section] = counts.get(section, 0) + n

    if counts['orders']:
        from orders.models import Order
        order_ct = ContentType.objects.get_for_model(Order)
        order_object_ids = list(base.filter(
            notification_type=Notification.TYPE_NEW_ORDER,
            content_type=order_ct,
        ).values_list('object_id', flat=True))

        fulfillment_counts = dict(
            Order.objects.filter(id__in=order_object_ids)
            .values('fulfillment_method')
            .annotate(count=Count('id'))
            .values_list('fulfillment_method', 'count')
        )
        counts['pickup_orders'] = fulfillment_counts.get('pickup', 0)
        counts['delivery_orders'] = fulfillment_counts.get('delivery', 0)

    return counts


def unread_notification_exists_for(user, obj):
    """True if there's an unread Notification pointing at this specific
    object, for this user — powers the per-item 🔵/⚪ dot."""
    content_type = ContentType.objects.get_for_model(obj)
    return Notification.objects.filter(
        recipient=user,
        content_type=content_type,
        object_id=obj.pk,
        is_read=False,
    ).exists()


def mark_related_read(user, obj):
    """
    Marks any unread Notification pointing at this specific object as read
    for this user. Called when admin opens that object's change/detail
    page — regardless of whether they got there via the notification bell
    or navigated to it directly through an admin changelist. Only that one
    object's notification is touched; everything else stays unread.
    """
    content_type = ContentType.objects.get_for_model(obj)
    Notification.objects.filter(
        recipient=user,
        content_type=content_type,
        object_id=obj.pk,
        is_read=False,
    ).update(is_read=True)