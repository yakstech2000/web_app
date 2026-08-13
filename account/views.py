"""
Complete User Authentication Views - Production Ready
Passwordless customer auth (email -> magic link -> logged in), plus the
legacy password-based account-management views kept in place for a
future optional "set a password" feature.
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
    generate_password_reset_token, decode_password_reset_token,
    decode_magic_link_token,
)
from account.emails import (
    send_verification_email, send_password_reset_email, send_magic_link_email,
)
from account.cart_ref import reattach_cart
from account.decorators import get_client_ip
from account.models import UserAuditLog, LoginAttempt

from django.utils import timezone
from datetime import timedelta

from orders.models import Order


# ==========================================
# PASSWORDLESS SIGNUP / LOGIN
# ==========================================
#
# There's no separate "create an account" step anymore — entering an
# email, whether brand-new or returning, goes through the same
# login_view below. signup() just forwards here so any existing links
# to account:signup keep working without a broken URL.

LOGIN_LINK_REQUEST_LIMIT = 3
LOGIN_LINK_REQUEST_WINDOW_MINUTES = 1


@require_http_methods(["GET"])
def signup(request):
    """
    No separate signup flow anymore (see login_view) — this exists only
    so old/bookmarked links to /signup/ still land somewhere sensible
    instead of 404ing, carrying through `next` if present.
    """
    next_url = request.GET.get('next', '')
    target = reverse('account:login')
    if next_url:
        target = f'{target}?next={next_url}'
    return redirect(target)


@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    Single entry point for customer authentication - passwordless.

    Enter an email -> get a secure link -> click it to continue. Works
    identically for brand-new and returning customers: a new User is
    created (with an unusable password, is_active=False) the first time
    an email is seen, and the same magic-link email is sent either way.
    """
    if request.user.is_authenticated:
        return redirect('account:dashboard')

    next_url = request.POST.get('next') or request.GET.get('next', '')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        ip = get_client_ip(request)

        if not email or '@' not in email:
            messages.error(request, 'Please enter a valid email address.')
            return render(request, 'login.html', {'next': next_url})

        # Basic request throttling. Reuses the existing LoginAttempt table
        # rather than adding a new model — here `success` records whether
        # the email actually sent, not whether a login happened (that's
        # recorded separately, in verify_email below).
        window_start = timezone.now() - timedelta(minutes=LOGIN_LINK_REQUEST_WINDOW_MINUTES)
        recent_requests = LoginAttempt.objects.filter(
            email=email, attempted_at__gte=window_start
        ).count()

        if recent_requests >= LOGIN_LINK_REQUEST_LIMIT:
            messages.error(
                request,
                'Too many requests for that email. Please wait a minute and try again.'
            )
            return render(request, 'login.html', {'next': next_url})

        user, created = User.objects.get_or_create(
            email=email,
            defaults={'username': email, 'is_active': False},
        )
        if created:
            # Never a guessable/fake password — Django's proper "no
            # password" state. authenticate() will always reject this
            # account via password; only the magic link can log them in.
            user.set_unusable_password()
            user.save()
            UserAuditLog.objects.create(
                user=user,
                action='signup',
                ip_address=ip,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
                details={'email': email, 'method': 'passwordless'},
            )

        email_sent = send_magic_link_email(user, request, next_url=next_url)

        LoginAttempt.objects.create(email=email, ip_address=ip, success=bool(email_sent))

        # Session key used by resend_verification below to know who to
        # resend to, and to show its cooldown timer.
        request.session['pending_verification_user_id'] = user.pk
        request.session.pop('verification_last_sent', None)

        if email_sent:
            messages.success(request, f'📧 Check {email} for a secure link to continue.')
        else:
            messages.error(
                request,
                '❌ We couldn\'t send that email right now. Please try again shortly, '
                'or contact support if this keeps happening.'
            )

        return redirect('account:verification-pending')

    return render(request, 'login.html', {'next': next_url})


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
    messages.success(request, 'Logged out successfully!')
    return redirect('account:login')


# ==========================================
# EMAIL VERIFICATION / MAGIC-LINK LOGIN
# ==========================================

@require_http_methods(["GET"])
def verify_email(request, uidb64, token):
    """
    The single click that completes the entire passwordless flow: verifies
    the email (first time only) AND logs the user in, in one step.

    login() updates user.last_login, which is part of this token's hash
    (see account/tokens.py) — so the exact link just clicked can never be
    used again, without needing a separate "used" flag or extra model.
    """
    user = decode_magic_link_token(uidb64, token)

    if user is None:
        messages.error(
            request,
            '❌ This link is invalid, expired, or has already been used. Please request a new one.'
        )
        return redirect('account:resend-verification')

    was_new_verification = not user.is_active
    if not user.is_active:
        user.is_active = True
        user.save()

    login(request, user)

    request.session.pop('pending_verification_user_id', None)
    request.session.pop('verification_last_sent', None)

    ip = get_client_ip(request)
    UserAuditLog.objects.create(
        user=user,
        action='email_verified' if was_new_verification else 'login',
        ip_address=ip,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
    )
    LoginAttempt.objects.create(email=user.email, ip_address=ip, success=True)

    # Best-effort: reattach a guest cart built on a different device than
    # the one this link was opened on. No-ops safely if absent/expired.
    cart_ref = request.GET.get('cart_ref')
    if cart_ref:
        reattach_cart(user, cart_ref)

    greeting = f', {user.first_name}' if user.first_name else ''
    messages.success(request, f'Welcome{greeting}!')

    # Only ever redirect to a local path — never an external URL — to
    # avoid this becoming an open redirect.
    next_url = request.GET.get('next')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)

    return redirect('account:dashboard')


def verification_pending(request):
    """Show 'check your email' message"""
    return render(request, 'verification_pending.html')


RESEND_COOLDOWN_SECONDS = 60


@require_http_methods(["GET", "POST"])
def resend_verification(request):
    """
    Resends the sign-in link. Works for both a brand-new unverified
    customer AND a returning already-verified one — under the
    passwordless flow, a verified/returning customer still needs a fresh
    link every time they want to log back in (there's no password to
    fall back on), so this is no longer a one-time-only action.
    """
    user_id = request.session.get('pending_verification_user_id')
    if not user_id:
        messages.error(request, 'Please enter your email first.')
        return redirect('account:login')

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        messages.error(request, 'Account not found.')
        return redirect('account:login')

    last_sent = request.session.get('verification_last_sent')
    remaining = 0
    if last_sent:
        elapsed = timezone.now().timestamp() - last_sent
        remaining = max(0, int(RESEND_COOLDOWN_SECONDS - elapsed))

    if request.method == 'POST':
        if remaining > 0:
            messages.error(request, f'Please wait {remaining}s before requesting another link.')
            return redirect('account:resend-verification')

        email_sent = send_magic_link_email(user, request)
        request.session['verification_last_sent'] = timezone.now().timestamp()

        if email_sent:
            messages.success(request, '📧 Link resent! Check your inbox.')
        else:
            messages.error(
                request,
                '❌ We couldn\'t send that email right now. Please try again shortly, '
                'or contact support if this keeps happening.'
            )
        return redirect('account:resend-verification')

    return render(request, 'resend_verification.html', {
        'user': user,
        'cooldown_remaining': remaining,
    })


# ==========================================
# PASSWORD RESET (legacy — not linked from
# the main nav; kept for a future optional
# "set a password" dashboard feature)
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
            # via form.is_valid() being False) when the address isn't
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
    """
    Change/set password — legacy view, currently not linked from the
    dashboard yet. This is exactly the hook for the future "add a
    password so you can skip the email link next time" feature.
    """
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

        UserAuditLog.objects.create(
            user=user,
            action='account_deleted',
            ip_address=get_client_ip(request),
            details={'email': email}
        )

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