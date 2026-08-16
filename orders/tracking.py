"""
Builds the customer-facing order tracking timeline from an Order and its
OrderStatusHistory records.

Deliberately conservative: a stage is only ever shown as "reached" if the
order's status is actually at or past that point in the sequence. Nothing
here invents progress the order hasn't actually made.
"""

from .models import Order

# (status_key, label) — the normal linear progression for each fulfillment
# method. Only the final label differs (Shipped vs Ready for Pickup),
# matching the wording your emails already use for each case.
_DELIVERY_STAGES = [
    (Order.STATUS_PENDING, 'Order Placed'),
    (Order.STATUS_PAID, 'Payment Confirmed'),
    (Order.STATUS_PROCESSING, 'Processing'),
    (Order.STATUS_COMPLETED, 'Shipped'),
]

_PICKUP_STAGES = [
    (Order.STATUS_PENDING, 'Order Placed'),
    (Order.STATUS_PAID, 'Payment Confirmed'),
    (Order.STATUS_PROCESSING, 'Processing'),
    (Order.STATUS_COMPLETED, 'Ready for Pickup'),
]

# Order the 5 statuses fall in, used to compare "how far along" the order
# is even for stages that don't have their own explicit history record
# (e.g. admin skipped 'processing' and went straight to 'completed').
_STATUS_SEQUENCE = [
    Order.STATUS_PENDING,
    Order.STATUS_PAID,
    Order.STATUS_PROCESSING,
    Order.STATUS_COMPLETED,
]


def build_order_timeline(order):
    """
    Returns a dict describing the timeline to render:
        {
            'cancelled': bool,
            'headline': str,          # e.g. "Your order is being processed"
            'stages': [
                {
                    'status': 'paid',
                    'label': 'Payment Confirmed',
                    'completed': True,
                    'current': False,
                    'timestamp': <datetime or None>,
                    'note': '',
                },
                ...
            ],
        }
    """
    if order.status == Order.STATUS_CANCELLED:
        cancelled_entry = order.status_history.filter(status=Order.STATUS_CANCELLED).last()
        return {
            'cancelled': True,
            'headline': 'This order was cancelled',
            'stages': [{
                'status': Order.STATUS_CANCELLED,
                'label': 'Order Cancelled',
                'completed': True,
                'current': True,
                'timestamp': cancelled_entry.created_at if cancelled_entry else order.updated_at,
                'note': cancelled_entry.note if cancelled_entry else '',
            }],
        }

    stage_defs = _PICKUP_STAGES if order.fulfillment_method == Order.FULFILLMENT_PICKUP else _DELIVERY_STAGES

    history_by_status = {}
    for entry in order.status_history.all():
        # Keep the earliest record per status (first time it was reached),
        # so re-saving admin with the same status twice doesn't shift the
        # displayed timestamp forward.
        if entry.status not in history_by_status:
            history_by_status[entry.status] = entry

    current_index = _STATUS_SEQUENCE.index(order.status) if order.status in _STATUS_SEQUENCE else 0

    stages = []
    for status_key, label in stage_defs:
        stage_index = _STATUS_SEQUENCE.index(status_key)
        history_entry = history_by_status.get(status_key)

        reached = stage_index <= current_index
        stages.append({
            'status': status_key,
            'label': label,
            'completed': reached,
            'current': status_key == order.status,
            'timestamp': history_entry.created_at if history_entry else (order.created_at if status_key == Order.STATUS_PENDING and reached else None),
            'note': history_entry.note if history_entry else '',
        })

    headlines = {
        Order.STATUS_PENDING: 'Waiting for payment',
        Order.STATUS_PAID: 'Payment received — your order is confirmed',
        Order.STATUS_PROCESSING: 'Your order is being prepared',
        Order.STATUS_COMPLETED: (
            'Your order has shipped' if order.fulfillment_method == Order.FULFILLMENT_DELIVERY
            else 'Your order is ready for pickup'
        ),
    }

    return {
        'cancelled': False,
        'headline': headlines.get(order.status, ''),
        'stages': stages,
    }