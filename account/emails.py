"""
Secure Email System for Account Management
Handles verification emails and password reset emails
"""

import logging

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from account.tokens import generate_email_verification_token, generate_password_reset_token

# Using a module-level logger instead of print() so failures show up as
# proper ERROR-level entries (with a full traceback via logger.exception)
# in Railway's log viewer, rather than being mixed in with stdout INFO
# noise or missed entirely depending on how logs are being tailed.
logger = logging.getLogger(__name__)


def send_verification_email(user, request):
    """
    Send email verification link to user
    Email contains 24-hour token for verification

    Args:
        user: User object to verify
        request: HTTP request for building absolute URLs

    Returns:
        Boolean indicating success/failure
    """
    try:
        uid, token = generate_email_verification_token(user)

        verification_url = request.build_absolute_uri(
            reverse('account:verify-email', kwargs={'uidb64': uid, 'token': token})
        )

        context = {
            'user': user,
            'verification_url': verification_url,
            'expiry_hours': 24,
            'site_name': 'Dr Apple Store',
        }

        # Try to render HTML template, fallback to plain text
        try:
            html_message = render_to_string('emails/verification.html', context)
        except Exception:
            html_message = f'Click here to verify: {verification_url}'

        send_mail(
            subject='Verify Your Email - Dr Apple Store',
            message=f'Verify your email: {verification_url}',
            # DEFAULT_FROM_EMAIL (the branded "Dr Apple Store <noreply@...>"
            # address from settings.py) instead of EMAIL_HOST_USER — the
            # raw SMTP login address was being used as the visible sender,
            # which was never actually the intent.
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info('Verification email sent to %s', user.email)
        return True
    except Exception:
        # logger.exception() records the full traceback (SMTP auth errors,
        # timeouts, etc.) at ERROR level — this is what you need to check
        # in Railway's Deploy Logs to find the actual delivery failure
        # reason, instead of a swallowed/silent False.
        logger.exception('Failed to send verification email to %s', user.email)
        return False


def send_password_reset_email(user, request):
    """
    Send password reset link to user
    Email contains 24-hour token for reset

    Args:
        user: User object requesting reset
        request: HTTP request for building absolute URLs

    Returns:
        Boolean indicating success/failure
    """
    try:
        uid, token = generate_password_reset_token(user)

        reset_url = request.build_absolute_uri(
            reverse('account:reset-password-confirm', kwargs={'uidb64': uid, 'token': token})
        )

        context = {
            'user': user,
            'reset_url': reset_url,
            'expiry_hours': 24,
            'site_name': 'Dr Apple Store',
        }

        # Try to render HTML template, fallback to plain text
        try:
            html_message = render_to_string('emails/password_reset.html', context)
        except Exception:
            html_message = f'Click here to reset password: {reset_url}'

        send_mail(
            subject='Reset Your Password - Dr Apple Store',
            message=f'Reset your password: {reset_url}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info('Password reset email sent to %s', user.email)
        return True
    except Exception:
        logger.exception('Failed to send password reset email to %s', user.email)
        return False