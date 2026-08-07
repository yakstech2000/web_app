"""
Django Signals for Auto-Triggered Actions
Automatically logs user creation and deletion
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from account.models import UserAuditLog


@receiver(post_save, sender=User)
def user_created_signal(sender, instance, created, **kwargs):
    """
    Signal handler for user creation
    Automatically logs when a new user is created
    """
    if created:
        UserAuditLog.objects.create(
            user=instance,
            action='signup',
            ip_address='0.0.0.0',  # IP captured in views, not signals
            details={'email': instance.email, 'auto_logged': True}
        )


@receiver(post_delete, sender=User)
def user_deleted_signal(sender, instance, **kwargs):
    """
    Signal handler for user deletion
    Automatically logs when a user is deleted
    """
    UserAuditLog.objects.create(
        user=instance,
        action='account_deleted',
        ip_address='0.0.0.0',  # IP captured in views, not signals
        details={'email': instance.email, 'auto_logged': True}
    )
