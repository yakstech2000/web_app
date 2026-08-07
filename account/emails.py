"""
Secure Email System for Account Management
Handles verification emails and password reset emails
"""

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from account.tokens import generate_email_verification_token, generate_password_reset_token


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
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        print(f'✅ Verification email sent to {user.email}')
        return True
    except Exception as e:
        print(f'❌ Failed to send verification email to {user.email}: {str(e)}')
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
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        print(f'✅ Password reset email sent to {user.email}')
        return True
    except Exception as e:
        print(f'❌ Failed to send password reset email to {user.email}: {str(e)}')
        return False