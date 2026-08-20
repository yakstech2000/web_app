import json


def notification_bell(request):
    """
    Exposes unread_notification_count + recent_notifications (for the bell
    dropdown) and section_unread_counts / section_unread_counts_json (for
    the WhatsApp-style sidebar badges) to every template automatically —
    same pattern already used by orders.context_processors.admin_dashboard_stats
    in this project. Zero extra queries for non-staff users.
    """
    if not (request.user.is_authenticated and request.user.is_staff):
        return {}

    from .models import Notification
    from .badges import get_section_unread_counts

    recent = Notification.objects.filter(recipient=request.user).select_related('content_type')[:6]
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    section_counts = get_section_unread_counts(request.user)

    return {
        'unread_notification_count': unread_count,
        'recent_notifications': recent,
        'section_unread_counts': section_counts,
        'section_unread_counts_json': json.dumps(section_counts),
    }