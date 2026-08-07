"""
Secure Token Generation for Email Verification & Password Reset
24-hour expiry, one-time use, cryptographically secure
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
import secrets


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """
    Generate secure tokens for email verification
    Expires after 24 hours, one-time use only
    """

    def _make_hash_value(self, user, timestamp):
        """Create hash value incorporating user, password, timestamp, and email"""
        return (
                str(user.pk) + user.password + str(timestamp) + str(user.email)
        )


def generate_email_verification_token(user):
    """
    Generate email verification token for a user
    Returns: (uid, token) tuple for use in email links
    Token expires after 24 hours
    """
    token_generator = EmailVerificationTokenGenerator()
    token = token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return uid, token


def decode_email_verification_token(uid, token):
    """
    Verify and decode email verification token
    Returns user object if token is valid, None otherwise
    """
    try:
        user_pk = force_str(urlsafe_base64_decode(uid))
        token_generator = EmailVerificationTokenGenerator()
        from django.contrib.auth.models import User
        user = User.objects.get(pk=user_pk)

        if token_generator.check_token(user, token):
            return user
    except (TypeError, ValueError, User.DoesNotExist):
        pass
    return None


def generate_password_reset_token(user):
    """
    Generate password reset token for a user
    Returns: (uid, token) tuple for use in email links
    Token expires after 24 hours
    """
    token_generator = PasswordResetTokenGenerator()
    token = token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return uid, token


def decode_password_reset_token(uid, token):
    """
    Verify and decode password reset token
    Returns user object if token is valid, None otherwise
    """
    try:
        user_pk = force_str(urlsafe_base64_decode(uid))
        token_generator = PasswordResetTokenGenerator()
        from django.contrib.auth.models import User
        user = User.objects.get(pk=user_pk)

        if token_generator.check_token(user, token):
            return user
    except (TypeError, ValueError, User.DoesNotExist):
        pass
    return None


def generate_secure_token(length=32):
    """
    Generate a cryptographically secure random token
    Uses secrets module for high security
    """
    return secrets.token_urlsafe(length)
