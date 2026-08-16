"""
Complete User Authentication Views - Production Ready
13 views for complete account management and security
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.urls import reverse

from account.forms import (
    SecureSignUpForm, SecureLoginForm, PasswordResetRequestForm,
    SetNewPasswordForm, ProfileUpdateForm
)
from account.tokens import (
    generate_email_verification_token, decode_email_verification_token,
    generate_password_reset_token, decode_password_reset_token
)
from account.emails import send_verification_email, send_password_reset_email
from account.decorators import (
    throttle_login_attempts, get_client_ip
)
from account.models import UserAuditLog, LoginAttempt

from django.utils import timezone
from datetime import timedelta

from orders.models import Order


# ==========================================
# SIGNUP / REGISTRATION
# ==========================================

@require_http_methods(["GET", "POST"])
def signup(request):
    """
    User registration with secure validation
    - Email uniqueness check
    - Password complexity validation
    - Audit logging
    - Email verification required
    """
    if request.user.is_authenticated:
        return redirect('account:dashboard')

    if request.method == 'POST':
        form = SecureSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()

            UserAuditLog.objects.create(
                user=user,
                action='signup',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
                details={'email': user.email}
            )

            email_sent = send_verification_email(user, request)

            request.session['pending_verification_user_id'] = user.pk

            if email_sent:
                messages.success(
                    request,
                    '✅ Account created! Check your email to verify your address.'
                )
            else:
                messages.warning(
                    request,
                    '⚠️ Account created, but we couldn\'t send the verification '
                    'email right now. Use the "Resend verification email" button '
                    'below to try again in a moment.'
                )
            return redirect('account:verification-pending')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field.title()}: {error}')
    else:
        form = SecureSignUpForm()

    return render(request, 'signup.html', {'form': form})


# ==========================================
# LOGIN / LOGOUT
# ==========================================
@require_http_methods(["GET", "POST"])
@throttle_login_attempts(max_attempts=5, timeout_minutes=15)
def login_view(request):
    """
    Secure login with throttling and audit logging
    - Login attempt throttling (5 attempts = 15 min lockout)
    - IP tracking
    - Audit logging
    - Generic error messages
    """
    if request.user.is_authenticated:
        # Someone already logged in landed on the login page itself (e.g.
        # clicked the account/login icon in the navbar while signed in) —
        # send them to the dashboard, not order history. Order history is
        # only the destination for an actual successful login action,
        # handled separately below.
        return redirect('account:dashboard')

    if request.method == 'POST':
        form = SecureLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].lower().strip()
            password = form.cleaned_data['password']
            ip = get_client_ip(request)

            try:
                user_obj = User.objects.get(email=email)
                username = user_obj.username
            except User.DoesNotExist:
                user_obj = None
                username = email

            # Check for admin deactivation FIRST and separately from
            # is_active below. is_active is used for email-verification
            # status, not admin bans — checking deactivation here means a
            # banned-but-verified user gets the correct "deactivated"
            # message instead of being routed into the "please verify your
            # email" flow further down.
            if user_obj is not None:
                account_status = getattr(user_obj, 'account_status', None)
                if account_status and account_status.is_deactivated:
                    messages.error(
                        request,
                        '❌ Your account has been deactivated. Please contact support.'
                    )
                    LoginAttempt.objects.create(
                        email=email,
                        ip_address=ip,
                        success=False
                    )
                    return redirect('account:login')

            # Check is_active BEFORE calling authenticate(). Django's default
            # ModelBackend silently returns None for inactive users regardless
            # of whether the password is correct, so checking this only
            # *after* authenticate() (as before) meant this branch could
            # never actually run - inactive users always fell through to the
            # generic "Invalid email or password" message instead.
            if user_obj is not None and not user_obj.is_active:
                request.session['pending_verification_user_id'] = user_obj.pk
                messages.error(request, '❌ Please verify your email first.')
                LoginAttempt.objects.create(
                    email=email,
                    ip_address=ip,
                    success=False
                )
                return redirect('account:resend-verification')

            # Authenticate user
            user = authenticate(request, username=username, password=password)

            if user is not None:
                # Login successful
                login(request, user)

                # Log successful login
                UserAuditLog.objects.create(
                    user=user,
                    action='login',
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
                )

                # Record successful login attempt
                LoginAttempt.objects.create(
                    email=email,
                    ip_address=ip,
                    success=True
                )

                messages.success(request, f'👋 Welcome back, {user.first_name or user.username}!')

                # Redirect to wherever they were headed (e.g. an order-status
                # email's "View My Orders" link, which appends ?next=...),
                # or straight to their order history by default — not the
                # dashboard, so logging in feels like "see my orders" first.
                next_url = request.GET.get('next') or reverse('order_history')
                return redirect(next_url)
            else:
                # Login failed
                LoginAttempt.objects.create(
                    email=email,
                    ip_address=ip,
                    success=False
                )

                # Log failed attempt
                UserAuditLog.objects.create(
                    action='login_failed',
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
                    details={'email': email}
                )

                messages.error(request, '❌ Invalid email or password.')
    else:
        form = SecureLoginForm()

    return render(request, 'login.html', {'form': form})

@login_required(login_url='account:login')
@require_http_methods(["GET", "POST"])
def logout_view(request):
    """Logout user and log action"""
    UserAuditLog.objects.create(
        user=request.user,
        action='logout',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
    )

    logout(request)
    messages.success(request, '👋 Logged out successfully!')
    return redirect('account:login')


# ==========================================
# EMAIL VERIFICATION
# ==========================================

@require_http_methods(["GET"])
@require_http_methods(["GET"])
def verify_email(request, uidb64, token):
    """Verify email with secure token"""
    user = decode_email_verification_token(uidb64, token)

    if user is not None:
        user.is_active = True
        user.save()

        request.session.pop('pending_verification_user_id', None)   # <-- add this line

        UserAuditLog.objects.create(
            user=user,
            action='email_verified',
            ip_address=get_client_ip(request),
        )

        messages.success(request, '✅ Email verified! You can now login.')
        return redirect('account:login')
    else:
        messages.error(request, '❌ Invalid or expired verification link.')
        return redirect('account:resend-verification')

def verification_pending(request):
    """Show verification pending message"""
    return render(request, 'verification_pending.html')

RESEND_COOLDOWN_SECONDS = 60
@require_http_methods(["GET", "POST"])
def resend_verification(request):
    user_id = request.session.get('pending_verification_user_id')
    if not user_id:
        messages.error(request, 'Please sign up or log in first.')
        return redirect('account:signup')

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        messages.error(request, 'Account not found.')
        return redirect('account:signup')

    if user.is_active:
        messages.info(request, 'Your email is already verified.')
        return redirect('account:login')

    last_sent = request.session.get('verification_last_sent')
    remaining = 0
    if last_sent:
        elapsed = timezone.now().timestamp() - last_sent
        remaining = max(0, int(RESEND_COOLDOWN_SECONDS - elapsed))

    if request.method == 'POST':
        if remaining > 0:
            messages.error(request, f'Please wait {remaining}s before requesting another email.')
            return redirect('account:resend-verification')

        email_sent = send_verification_email(user, request)
        request.session['verification_last_sent'] = timezone.now().timestamp()

        if email_sent:
            messages.success(request, '📧 Verification email resent! Check your inbox.')
        else:
            messages.error(
                request,
                '❌ We couldn\'t send the email right now. Please try again '
                'shortly, or contact support if this keeps happening.'
            )
        return redirect('account:resend-verification')

    return render(request, 'resend_verification.html', {
        'user': user,
        'cooldown_remaining': remaining,
    })
# ==========================================
# PASSWORD RESET
# ==========================================

@require_http_methods(["GET", "POST"])
def password_reset(request):
    """Request password reset"""
    if request.user.is_authenticated:
        return redirect('account:dashboard')

    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            # form.clean_email() already raises a ValidationError (caught
            # below via form.is_valid() being False) when the address isn't
            # registered, so this branch only ever runs for a real,
            # existing user.
            user = User.objects.get(email=form.cleaned_data['email'].lower())
            email_sent = send_password_reset_email(user, request)

            if email_sent:
                messages.info(request, '📧 Check your email for password reset instructions.')
            else:
                messages.error(
                    request,
                    '❌ We\'re having trouble sending emails right now. '
                    'Please try again in a few minutes, or contact support.'
                )
            return redirect('account:login')
    else:
        form = PasswordResetRequestForm()

    return render(request, 'password_reset.html', {'form': form})


@require_http_methods(["GET", "POST"])
def password_reset_confirm(request, uidb64, token):
    """Reset password with secure token"""
    user = decode_password_reset_token(uidb64, token)

    if user is None:
        messages.error(request, '❌ Invalid or expired password reset link.')
        return redirect('account:password-reset')

    if request.method == 'POST':
        form = SetNewPasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['password1'])
            user.save()

            UserAuditLog.objects.create(
                user=user,
                action='password_reset',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
            )

            # If this account was never email-verified, resetting the
            # password alone still won't let them log in (is_active=False
            # blocks authenticate() regardless of password), so send them
            # to verify instead of straight to a login page that will fail.
            if not user.is_active:
                messages.info(
                    request,
                    '✅ Password reset! Please verify your email before logging in.'
                )
                return redirect('account:resend-verification')

            messages.success(request, '✅ Password reset successfully! You can now login.')
            return redirect('account:login')
    else:
        form = SetNewPasswordForm()

    return render(request, 'password_reset_confirm.html', {'form': form})


# ==========================================
# ACCOUNT MANAGEMENT
# ==========================================

@login_required(login_url='account:login')
def dashboard(request):
    """User dashboard"""
    user_orders = Order.objects.filter(user=request.user).order_by('-created_at')

    # Items from completed orders that don't have a review yet - shown as
    # a "you can review this" notification on the dashboard.
    reviewable_items = []
    for order in user_orders.filter(status=Order.STATUS_COMPLETED).prefetch_related('items', 'reviews'):
        reviewed_product_ids = set(order.reviews.values_list('product_id', flat=True))
        for item in order.items.all():
            if item.product_id and item.product_id not in reviewed_product_ids:
                reviewable_items.append({'order': order, 'item': item})

    context = {
        'user': request.user,
        'member_since': request.user.date_joined,
        'order_count': user_orders.count(),
        'latest_order': user_orders.first(),
        'reviewable_items': reviewable_items,
    }
    return render(request, 'dashboard.html', context)


@login_required(login_url='account:login')
@require_http_methods(["GET", "POST"])
def edit_profile(request):
    """Edit user profile"""
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()

            UserAuditLog.objects.create(
                user=request.user,
                action='profile_updated',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
                details={'changed_fields': ['first_name', 'last_name', 'email']}
            )

            messages.success(request, '✅ Profile updated successfully!')
            return redirect('account:dashboard')
    else:
        form = ProfileUpdateForm(instance=request.user)

    return render(request, 'edit_profile.html', {'form': form})


@login_required(login_url='account:login')
@require_http_methods(["GET", "POST"])
def change_password(request):
    """Change password"""
    if request.method == 'POST':
        form = SetNewPasswordForm(request.POST)

        if form.is_valid():
            request.user.set_password(form.cleaned_data['password1'])
            request.user.save()

            UserAuditLog.objects.create(
                user=request.user,
                action='password_changed',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
            )

            messages.success(request, '✅ Password changed successfully!')
            return redirect('account:dashboard')
    else:
        form = SetNewPasswordForm()

    return render(request, 'change_password.html', {'form': form})


@login_required(login_url='account:login')
@require_http_methods(["GET", "POST"])
def delete_account(request):
    """Delete user account"""
    if request.method == 'POST':
        user = request.user
        email = user.email

        # Log deletion
        UserAuditLog.objects.create(
            user=user,
            action='account_deleted',
            ip_address=get_client_ip(request),
            details={'email': email}
        )

        # Delete user
        user.delete()

        messages.success(request, '✅ Account deleted successfully.')
        return redirect('account:login')

    return render(request, 'delete_account_confirm.html')


# ==========================================
# SECURITY & ACTIVITY
# ==========================================

@login_required(login_url='account:login')
def security_log(request):
    """View user's security/audit log"""
    audit_logs = UserAuditLog.objects.filter(user=request.user).order_by('-created_at')[:50]

    context = {
        'audit_logs': audit_logs,
    }

    return render(request, 'security_log.html', context)


@login_required(login_url='account:login')
def activity_history(request):
    """View user's login activity"""
    login_history = LoginAttempt.objects.filter(
        email=request.user.email,
        success=True
    ).order_by('-attempted_at')[:20]

    context = {
        'login_history': login_history,
    }

    return render(request, 'activity_history.html', context)

# Create your views here.