from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'notification_type', 'recipient', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'recipient__username', 'recipient__email')
    readonly_fields = ('recipient', 'notification_type', 'title', 'message', 'link', 'content_type', 'object_id', 'created_at')

    def has_add_permission(self, request):
        # Notifications are only ever created by the system (via
        # notifications/services.py) — never hand-added in admin.
        return False
# Register your models here.
