from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    verbose_name = 'Admin Notifications'

    def ready(self):
        import notifications.signals  # noqa: F401 — registers the receivers