"""
Drop-in mixin for any ModelAdmin whose objects can have notifications
pointing at them (Order, Product, ProductReview, User, ...). Add it as the
FIRST base class so its change_view/get_list_display take effect:

    class DeliveryOrderAdmin(MarksRelatedNotificationsReadMixin, BaseOrderAdmin):
        list_display = BaseOrderAdmin.list_display + ('unread_dot',)

Gives you:
  - an `unread_dot` column (🔵 unread / ⚪ read) you can add to list_display
  - auto-marks that object's related notification(s) read the moment its
    change page is opened, however admin navigated there

Note: this stashes request.user on `self` during changelist_view() to make
it available to the unread_dot list_display method (Django's list_display
callables only receive `obj`, not `request`). This project runs gunicorn
with a SYNC worker (one request at a time per worker process — confirmed
in this project's earlier deploy logs), so this is safe here. It would
NOT be safe with an async/threaded worker setup, where ModelAdmin
instances can be shared across concurrently-running requests.
"""
from .badges import mark_related_read, unread_notification_exists_for


class MarksRelatedNotificationsReadMixin:
    def changelist_view(self, request, extra_context=None):
        self._current_request_user = request.user
        return super().changelist_view(request, extra_context)

    def unread_dot(self, obj):
        user = getattr(self, '_current_request_user', None)
        if user is None:
            return ''
        return '🔵' if unread_notification_exists_for(user, obj) else '⚪'
    unread_dot.short_description = ''

    def change_view(self, request, object_id, form_url='', extra_context=None):
        obj = self.get_object(request, object_id)
        if obj is not None and request.user.is_authenticated and request.user.is_staff:
            # Marks ONLY this object's related notification(s) as read —
            # every other unread item, in this section or any other,
            # stays exactly as it was.
            mark_related_read(request.user, obj)
        return super().change_view(request, object_id, form_url, extra_context)