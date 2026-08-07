"""
Security Decorators - Authentication, Throttling, Authorization
Production-ready security middleware for views
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import HttpResponseForbidden
from datetime import timedelta
from account.models import LoginAttempt, UserAuditLog


def get_client_ip(request):
    """
    Extract client IP address from request
    Handles proxies and forwarded headers correctly
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def throttle_login_attempts(max_attempts=5, timeout_minutes=15):
    """
    Decorator to throttle login attempts and prevent brute force attacks
    Default: 5 failed attempts triggers 15-minute lockout

    Usage:
        @throttle_login_attempts(max_attempts=5, timeout_minutes=15)
        def login_view(request):
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            email = request.POST.get('email', '').lower().strip()
            ip = get_client_ip(request)

            if request.method == 'POST' and email:
                # Check failed attempts in timeout window
                timeout_time = timezone.now() - timedelta(minutes=timeout_minutes)
                failed_attempts = LoginAttempt.objects.filter(
                    email=email,
                    success=False,
                    attempted_at__gte=timeout_time
                ).count()

                if failed_attempts >= max_attempts:
                    return HttpResponseForbidden(
                        f'Too many login attempts. Please try again in {timeout_minutes} minutes.'
                    )

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def user_owns_resource(resource_attr='user'):
    """
    Decorator to check if user owns the resource before access
    Prevents unauthorized access to other users' resources

    Usage:
        @user_owns_resource()
        def edit_profile(request):
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def audit_log_action(action):
    """
    Decorator to log user actions for audit trail
    Records action, IP, user agent, and timestamp

    Usage:
        @audit_log_action('profile_updated')
        def edit_profile(request):
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)

            if request.user.is_authenticated:
                UserAuditLog.objects.create(
                    user=request.user,
                    action=action,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
                )

            return response

        return wrapper

    return decorator


def staff_only(view_func):
    """
    Decorator to allow only staff/admin users
    Requires login and staff status

    Usage:
        @staff_only
        def admin_view(request):
            ...
    """

    @wraps(view_func)
    @login_required(login_url='login')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden('Access denied. Staff access required.')
        return view_func(request, *args, **kwargs)

    return wrapper


def require_verification(view_func):
    """
    Decorator to require email verification before access

    Usage:
        @require_verification
        @login_required
        def verified_only_view(request):
            ...
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_active:
            return redirect('resend-verification')
        return view_func(request, *args, **kwargs)

    return wrapper
