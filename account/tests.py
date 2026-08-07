"""
Tests for the account app views.

This is PART 1 — covers views that don't depend on your custom forms
(SecureSignUpForm, SecureLoginForm, etc.) or token generation
(email verification / password reset), since I don't have those files yet.

Covered here:
- dashboard (auth required, empty-state context)
- logout_view (auth required, logs out, redirects)
- security_log (auth required, shows audit logs)
- activity_history (auth required, shows login attempts)
- delete_account (auth required, GET shows confirm page, POST deletes user)
- verification_pending (no auth required, just renders)

NOT covered yet (need forms.py / tokens.py / decorators.py to write correctly):
- signup (needs SecureSignUpForm field names)
- login_view (needs SecureLoginForm field names + throttle_login_attempts behavior)
- verify_email / password_reset_confirm (need token generation helpers)
- resend_verification (needs session + cooldown behavior, doable once login form is known)
- edit_profile / change_password (need ProfileUpdateForm / SetNewPasswordForm field names)
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from account.models import UserAuditLog, LoginAttempt


class DashboardTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="jane",
            email="jane@example.com",
            password="StrongPass123!",
            is_active=True,
        )
        self.url = reverse('account:dashboard')

    def test_dashboard_requires_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('account:login')}?next={self.url}"
        )

    def test_dashboard_loads_for_logged_in_user_with_no_orders(self):
        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['order_count'], 0)
        self.assertIsNone(response.context['latest_order'])
        self.assertEqual(response.context['reviewable_items'], [])
        self.assertEqual(response.context['user'], self.user)


class LogoutTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="jane",
            email="jane@example.com",
            password="StrongPass123!",
            is_active=True,
        )
        self.url = reverse('account:logout')

    def test_logout_requires_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('account:login')}?next={self.url}"
        )

    def test_logout_logs_out_and_redirects(self):
        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertRedirects(response, reverse('account:login'))
        # Session should no longer be authenticated
        response2 = self.client.get(reverse('account:dashboard'))
        self.assertNotEqual(response2.status_code, 200)

    def test_logout_creates_audit_log_entry(self):
        self.client.login(username="jane", password="StrongPass123!")
        self.client.get(self.url)

        self.assertTrue(
            UserAuditLog.objects.filter(user=self.user, action='logout').exists()
        )


class SecurityLogTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="jane",
            email="jane@example.com",
            password="StrongPass123!",
            is_active=True,
        )
        self.url = reverse('account:security_log')

    def test_security_log_requires_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('account:login')}?next={self.url}"
        )

    def test_security_log_shows_only_current_users_entries(self):
        other_user = User.objects.create_user(
            username="bob", email="bob@example.com", password="StrongPass123!"
        )
        UserAuditLog.objects.create(user=self.user, action='login', ip_address='127.0.0.1')
        UserAuditLog.objects.create(user=other_user, action='login', ip_address='127.0.0.1')

        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.get(self.url)

        logs = list(response.context['audit_logs'])
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].user, self.user)


class ActivityHistoryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="jane",
            email="jane@example.com",
            password="StrongPass123!",
            is_active=True,
        )
        self.url = reverse('account:activity_history')

    def test_activity_history_requires_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('account:login')}?next={self.url}"
        )

    def test_activity_history_only_shows_successful_attempts_for_this_email(self):
        LoginAttempt.objects.create(email="jane@example.com", ip_address="127.0.0.1", success=True)
        LoginAttempt.objects.create(email="jane@example.com", ip_address="127.0.0.1", success=False)
        LoginAttempt.objects.create(email="bob@example.com", ip_address="127.0.0.1", success=True)

        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.get(self.url)

        history = list(response.context['login_history'])
        self.assertEqual(len(history), 1)
        self.assertTrue(history[0].success)
        self.assertEqual(history[0].email, "jane@example.com")


class DeleteAccountTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="jane",
            email="jane@example.com",
            password="StrongPass123!",
            is_active=True,
        )
        self.url = reverse('account:delete_account')

    def test_delete_account_requires_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('account:login')}?next={self.url}"
        )

    def test_get_shows_confirmation_page_without_deleting(self):
        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_post_deletes_account_and_redirects_to_login(self):
        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.post(self.url)

        self.assertRedirects(response, reverse('account:login'))
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())


class VerificationPendingTests(TestCase):
    def test_verification_pending_loads_without_login(self):
        response = self.client.get(reverse('account:verification-pending'))
        self.assertEqual(response.status_code, 200)