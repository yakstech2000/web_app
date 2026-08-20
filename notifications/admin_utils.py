"""
Shared admin behavior for marking notifications read when their related
object is viewed. Kept here (rather than duplicated inside each app's
admin.py) so Orders, Reviews, or anything else that gets a notification
type in the future can opt in with one line, and so there's exactly one
place implementing "opening an object clears only that object's unread
notifications."
"""
from django.contrib.contenttypes.models import ContentType

from .models import Notification


class MarksNotificationsReadMixin:
    """
    Mix into any ModelAdmin whose change_view should clear unread
    Notifications pointing at the object being viewed.

    Marks ALL unread notifications for that specific object (any
    notification_type) as read, for the current staff user only:
      - never touches other admins' unread state (filtered by recipient)
      - never touches notifications for other objects (filtered by
        content_type + object_id of the one being opened)
      - never marks an entire section read just because its list view was
        opened — only change_view (opening one specific item) triggers this

    ContentType.objects.get_for_model(self.model) resolves proxy models
    (like DeliveryOrder/PickupOrder) to their concrete model's content
    type automatically, matching how notify() in notifications/services.py
    already records it — so this works correctly even though
    DeliveryOrderAdmin/PickupOrderAdmin operate on proxy models rather
    than Order directly.
    """
    def change_view(self, request, object_id, form_url='', extra_context=None):
        if request.user.is_authenticated and request.user.is_staff:
            content_type = ContentType.objects.get_for_model(self.model)
            Notification.objects.filter(
                recipient=request.user,
                content_type=content_type,
                object_id=object_id,
                is_read=False,
            ).update(is_read=True)
        return super().change_view(request, object_id, form_url, extra_context)
