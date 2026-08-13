"""
Secure Email System for Account Management
Handles verification emails, password reset emails, and passwordless
magic-link sign-in emails.
"""

import logging

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.utils.http import urlencode

from account.tokens import (
    generate_email_verification_token,
    generate_password_reset_token,
    generate_magic_link_token,
)
from account.cart_ref import guest_cart_ref_for_session

# Using a module-level logger instead of print() so failures show up as
# proper ERROR-level entries (with a full traceback via logger.exception)
# in Railway's log viewer, rather than being mixed in with stdout INFO
# noise or missed entirely depending on how logs are being tailed.
logger = logging.getLogger(__name__)


def send_verification_email(user, request):
    """
    LEGACY — used only by the password-based signup path (account/forms.py
    SecureSignUpForm), which is no longer linked from the main nav but is
    kept working in case a password-based "log in faster next time" option
    is wired back up later. New signups go through send_magic_link_email
    instead.

    Returns Boolean indicating success/failure.
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

        try:
            html_message = render_to_string('emails/verification.html', context)
        except Exception:
            html_message = f'Click here to verify: {verification_url}'

        send_mail(
            subject='Verify Your Email - Dr Apple Store',
            message=f'Verify your email: {verification_url}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info('Verification email sent to %s', user.email)
        return True
    except Exception:
        logger.exception('Failed to send verification email to %s', user.email)
        return False


def send_password_reset_email(user, request):
    """
    LEGACY — supports the password-reset flow, kept for whenever the
    optional "set a password" dashboard feature gets built. Not part of
    the current passwordless signup/login flow.

    Returns Boolean indicating success/failure.
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


def send_magic_link_email(user, request, next_url=''):
    """
    The single email used for the entire passwordless flow — same email
    whether this is a brand-new customer or a returning one signing back
    in, since clicking the link both verifies the address (if new) and
    logs them in, in one step.

    Optionally carries:
    - a 'next' redirect (e.g. back to checkout), validated as a local
      path only (must start with '/') to avoid an open-redirect
    - a signed reference to the customer's guest cart (see cart_ref.py)
      so it survives even if the link is opened on a different device
      than the one the cart was built on

    Returns Boolean indicating success/failure.
    """
    try:
        uid, token = generate_magic_link_token(user)
        path = reverse('account:verify-email', kwargs={'uidb64': uid, 'token': token})

        params = {}
        if next_url and next_url.startswith('/'):
            params['next'] = next_url

        cart_ref = guest_cart_ref_for_session(request.session.session_key)
        if cart_ref:
            params['cart_ref'] = cart_ref

        if params:
            path = f'{path}?{urlencode(params)}'

        auth_url = request.build_absolute_uri(path)

        context = {
            'user': user,
            'verification_url': auth_url,
            'expiry_hours': 24,
            'site_name': 'Dr Apple Store',
        }

        try:
            html_message = render_to_string('emails/verification.html', context)
        except Exception:
            html_message = f'Click here to continue: {auth_url}'

        send_mail(
            subject='Your sign-in link - Dr Apple Store',
            message=f'Click to continue: {auth_url}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info('Magic link email sent to %s', user.email)
        return True
    except Exception:
        logger.exception('Failed to send magic link email to %s', user.email)
        return False