"""
User Accounts Models - Complete Authentication & Audit Logging System
"""
from django.contrib.sessions.models import Session
from django.conf import settings
from django.db import models
from django.utils import timezone


class UserAuditLog(models.Model):
    """
    Audit trail for all user account activities
    Tracks: login, logout, password changes, email verification, profile updates, etc.
    """
    ACTION_CHOICES = [
        ('signup', 'User Signup'),
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('login_failed', 'Failed Login Attempt'),
        ('password_changed', 'Password Changed'),
        ('password_reset', 'Password Reset'),
        ('email_changed', 'Email Changed'),
        ('email_verified', 'Email Verified'),
        ('profile_updated', 'Profile Updated'),
        ('account_deleted', 'Account Deleted'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text='User this action relates to (blank for failed logins with no matching account)'
    )
    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
        help_text='Type of action performed'
    )
    ip_address = models.GenericIPAddressField(
        help_text='IP address where action originated'
    )
    user_agent = models.TextField(
        blank=True,
        help_text='Browser/device information'
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional JSON details about the action'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp when action occurred'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action']),
        ]
        verbose_name = 'User Audit Log'
        verbose_name_plural = 'User Audit Logs'

    def __str__(self):
        username = self.user.username if self.user else 'Unknown user'
        return f"{username} - {self.get_action_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    def get_action_color(self):
        """Return Bootstrap badge color for action type"""
        colors = {
            'signup': 'success',
            'login': 'info',
            'logout': 'secondary',
            'login_failed': 'danger',
            'password_changed': 'warning',
            'password_reset': 'warning',
            'email_changed': 'info',
            'email_verified': 'success',
            'profile_updated': 'info',
            'account_deleted': 'danger',
        }
        return colors.get(self.action, 'secondary')


class LoginAttempt(models.Model):
    """
    Track login attempts for security throttling and audit
    Used to prevent brute force attacks
    """
    email = models.EmailField(
        db_index=True,
        help_text='Email address attempted to login'
    )
    ip_address = models.GenericIPAddressField(
        db_index=True,
        help_text='IP address of login attempt'
    )
    success = models.BooleanField(
        default=False,
        help_text='Whether login was successful'
    )
    attempted_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text='When login was attempted'
    )

    class Meta:
        ordering = ['-attempted_at']
        indexes = [
            models.Index(fields=['email', '-attempted_at']),
            models.Index(fields=['ip_address', '-attempted_at']),
        ]
        verbose_name = 'Login Attempt'
        verbose_name_plural = 'Login Attempts'

    def __str__(self):
        status = '✅ Success' if self.success else '❌ Failed'
        return f"{self.email} - {status} - {self.attempted_at.strftime('%Y-%m-%d %H:%M:%S')}"

    @classmethod
    def get_recent_failed_attempts(cls, email, ip_address, minutes=15):
        """Get recent failed login attempts for throttling"""
        from django.utils import timezone
        from datetime import timedelta

        timeout_time = timezone.now() - timedelta(minutes=minutes)
        return cls.objects.filter(
            email=email.lower(),
            success=False,
            attempted_at__gte=timeout_time
        ).count()


class UserAccountStatus(models.Model):
    """
    Tracks whether ADMIN has deactivated a user's account.

    Deliberately separate from User.is_active — that field is already used
    by signup/login_view to mean "has verified their email." Reusing it for
    admin deactivation would make a banned user indistinguishable from an
    unverified one (wrong error message, and a stale verification link
    could accidentally reactivate them).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='account_status',
    )
    is_deactivated = models.BooleanField(default=False)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='deactivated_users',
        help_text='The admin who deactivated this user.',
    )

    class Meta:
        verbose_name = 'User Account Status'
        verbose_name_plural = 'User Account Statuses'

    def __str__(self):
        return f"{self.user.username} - {'Deactivated' if self.is_deactivated else 'Active'}"

    def deactivate(self, by_user):
        self.is_deactivated = True
        self.deactivated_at = timezone.now()
        self.deactivated_by = by_user
        self.save()

    def reactivate(self):
        self.is_deactivated = False
        self.deactivated_at = None
        self.deactivated_by = None
        self.save()


def force_logout_user(user):
    """
    Delete all active DB sessions belonging to this user, logging them out
    of every device/browser immediately. Assumes the default database-backed
    session engine (django.contrib.sessions.backends.db) — if this project
    uses cache or signed-cookie sessions instead, this won't have any effect
    and a different approach (e.g. a session-version field checked in
    middleware) would be needed instead.
    """


    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        data = session.get_decoded()
        if data.get('_auth_user_id') == str(user.pk):
            session.delete()

# Create your models here.