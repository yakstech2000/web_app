"""
Django Admin Configuration for Accounts App
Read-only audit logs and login attempt tracking, plus a User admin
extension for deactivating/reactivating accounts.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html

from account.models import UserAuditLog, LoginAttempt, UserAccountStatus, force_logout_user


@admin.register(UserAuditLog)
class UserAuditLogAdmin(admin.ModelAdmin):
    """
    Admin interface for viewing user audit logs
    Provides comprehensive view of all user activities with filtering and search
    """
    list_display = ('user', 'action_badge', 'ip_address', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('user__username', 'user__email', 'ip_address')
    readonly_fields = ('user', 'action', 'ip_address', 'user_agent', 'details', 'created_at')
    date_hierarchy = 'created_at'

    fieldsets = (
        ('User & Action', {
            'fields': ('user', 'action', 'created_at')
        }),
        ('Connection Information', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Additional Details', {
            'fields': ('details',),
            'classes': ('collapse',)
        }),
    )

    def action_badge(self, obj):
        """Display action as colored badge"""
        colors = {
            'signup': '#28a745',  # Green
            'login': '#007bff',  # Blue
            'logout': '#6c757d',  # Gray
            'login_failed': '#dc3545',  # Red
            'password_changed': '#ffc107',  # Yellow
            'password_reset': '#ffc107',  # Yellow
            'email_changed': '#007bff',  # Blue
            'email_verified': '#28a745',  # Green
            'profile_updated': '#007bff',  # Blue
            'account_deleted': '#dc3545',  # Red
        }
        color = colors.get(obj.action, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_action_display()
        )

    action_badge.short_description = 'Action'

    def has_add_permission(self, request):
        return False  # Read-only audit log

    def has_delete_permission(self, request, obj=None):
        return False  # Prevent deletion of audit logs

    def has_change_permission(self, request, obj=None):
        return False  # Prevent changes to audit logs


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """
    Admin interface for viewing login attempts
    Track and analyze login security patterns
    """
    list_display = ('email', 'success_badge', 'ip_address', 'attempted_at')
    list_filter = ('success', 'attempted_at')
    search_fields = ('email', 'ip_address')
    readonly_fields = ('email', 'ip_address', 'success', 'attempted_at')
    date_hierarchy = 'attempted_at'

    fieldsets = (
        ('Login Information', {
            'fields': ('email', 'success', 'attempted_at')
        }),
        ('Connection', {
            'fields': ('ip_address',)
        }),
    )

    def success_badge(self, obj):
        """Display success status as colored badge"""
        if obj.success:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 5px 10px; border-radius: 3px;">{}</span>',
                '✅ Success'
            )
        else:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 5px 10px; border-radius: 3px;">{}</span>',
                '❌ Failed'
            )

    success_badge.short_description = 'Status'

    def has_add_permission(self, request):
        return False  # Auto-generated only

    def has_delete_permission(self, request, obj=None):
        return False  # Prevent deletion

    def has_change_permission(self, request, obj=None):
        return False  # Prevent changes


# ---------------------------------------------------------------------------
# Custom User admin — adds an "Account Status" column and Deactivate /
# Reactivate bulk actions.
#
# Deactivating a user sets UserAccountStatus.is_deactivated=True and force-
# logs them out of every active session (see force_logout_user in models.py).
# An admin can't accidentally deactivate their own account — it's skipped
# and reported in the result message. Only staff who already have access to
# /admin/ can run these actions at all — enforced by Django's normal admin
# permission system, no extra guard needed here.
#
# This block must stay at module level (not nested inside another class) so
# it actually registers with admin.site when Django loads this file.
# ---------------------------------------------------------------------------

@admin.action(description="Deactivate selected users")
def deactivate_users(modeladmin, request, queryset):
    count = 0
    skipped_self = False

    for user in queryset:
        if user.pk == request.user.pk:
            skipped_self = True
            continue

        status, _ = UserAccountStatus.objects.get_or_create(user=user)
        if not status.is_deactivated:
            status.deactivate(by_user=request.user)
            force_logout_user(user)
            count += 1

    message = f"Deactivated {count} user(s) and logged them out."
    if skipped_self:
        message += " (Skipped your own account — you can't deactivate yourself.)"
    modeladmin.message_user(request, message)


@admin.action(description="Reactivate selected users")
def reactivate_users(modeladmin, request, queryset):
    count = 0
    for user in queryset:
        status = getattr(user, 'account_status', None)
        if status and status.is_deactivated:
            status.reactivate()
            count += 1

    modeladmin.message_user(request, f"Reactivated {count} user(s).")


admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(DjangoUserAdmin):
    list_display = DjangoUserAdmin.list_display + ('account_status_display',)
    actions = list(DjangoUserAdmin.actions or []) + [deactivate_users, reactivate_users]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('account_status')

    def account_status_display(self, obj):
        status = getattr(obj, 'account_status', None)
        if status and status.is_deactivated:
            return "🚫 Deactivated"
        return "✅ Active"

    account_status_display.short_description = "Account Status"

# Register your models here.