
"""
Tests for the orders app.

NOTE: checkout() is NOT covered here yet — it depends on cart.models.Cart /
CartItem, which I don't have. Send cart/models.py and I'll add checkout tests
(empty cart redirect, missing-field validation, successful order creation +
cart clearing).

Everything downstream of order creation (order_review, process_payment,
payment_confirmation, receipt upload, order_history, order_detail) is
covered by creating Order/OrderItem directly via the ORM, bypassing checkout.

Also see the test `test_order_history_redirect_url_name` below — it targets
a suspected bug: order_history redirects unauthenticated users to the bare
name 'login' instead of the namespaced 'account:login'. If your project has
no top-level url named plain 'login', this will raise NoReverseMatch.
"""

from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch

from product.models import Category, Brand, Product
from orders.models import Order, OrderItem


TINY_GIF = SimpleUploadedFile(
    "test.gif",
    b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
    content_type="image/gif",
)


class OrdersTestBase(TestCase):
    """Shared setup: a product, an owner user, another user, and a staff user."""

    def setUp(self):
        self.client = Client()

        self.brand = Brand.objects.create(name="Apple")
        self.category = Category.objects.create(name="Phones")
        self.product = Product.objects.create(
            name="iPhone 15",
            brand=self.brand,
            category=self.category,
            description="A phone.",
            selling_price=999.00,
            stock_quantity=10,
            product_image=TINY_GIF,
        )

        self.owner = User.objects.create_user(
            username="jane", email="jane@example.com", password="StrongPass123!"
        )
        self.other_user = User.objects.create_user(
            username="bob", email="bob@example.com", password="StrongPass123!"
        )
        self.staff_user = User.objects.create_user(
            username="admin", email="admin@example.com", password="StrongPass123!",
            is_staff=True,
        )

    def _make_order(self, user=None, total_price="999.00"):
        order = Order.objects.create(
            user=user,
            full_name="Jane Doe",
            email="jane@example.com",
            phone="08000000000",
            address="1 Main Street",
            state="Lagos",
            city="Lagos",
            country="Nigeria",
            total_price=Decimal(total_price),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            price=self.product.selling_price,
            quantity=2,
        )
        return order


class OrderModelTests(OrdersTestBase):
    def test_order_number_is_auto_generated_on_creation(self):
        order = self._make_order(user=self.owner)
        self.assertTrue(order.order_number.startswith("DR"))
        self.assertEqual(order.order_number, f"DR{10000 + order.pk}")

    def test_get_total_items_sums_item_quantities(self):
        order = self._make_order(user=self.owner)
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            price=self.product.selling_price,
            quantity=3,
        )
        # First item has quantity=2 (from _make_order), second has quantity=3
        self.assertEqual(order.get_total_items(), 5)

    def test_get_subtotal_on_order_item(self):
        order = self._make_order(user=self.owner)
        item = order.items.first()
        self.assertEqual(item.get_subtotal(), item.price * item.quantity)


class OrderReviewViewTests(OrdersTestBase):
    def test_guest_order_viewable_by_anonymous_user(self):
        order = self._make_order(user=None)
        response = self.client.get(reverse('order_review', args=[order.id]))
        self.assertEqual(response.status_code, 200)

    def test_owner_can_view_their_order(self):
        order = self._make_order(user=self.owner)
        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.get(reverse('order_review', args=[order.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['order'], order)

    def test_other_logged_in_user_is_blocked(self):
        order = self._make_order(user=self.owner)
        self.client.login(username="bob", password="StrongPass123!")
        response = self.client.get(reverse('order_review', args=[order.id]), follow=True)
        self.assertRedirects(response, reverse('product_list'))

    def test_staff_can_view_any_order(self):
        order = self._make_order(user=self.owner)
        self.client.login(username="admin", password="StrongPass123!")
        response = self.client.get(reverse('order_review', args=[order.id]))
        self.assertEqual(response.status_code, 200)


class ProcessPaymentViewTests(OrdersTestBase):
    def test_missing_payment_method_shows_error_and_redirects(self):
        order = self._make_order(user=self.owner)
        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.post(
            reverse('process_payment', args=[order.id]), {}, follow=True
        )
        self.assertRedirects(response, reverse('order_review', args=[order.id]))
        order.refresh_from_db()
        self.assertEqual(order.payment_method, "")

    def test_valid_payment_method_sets_status_and_redirects(self):
        order = self._make_order(user=self.owner)
        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.post(
            reverse('process_payment', args=[order.id]),
            {'payment_method': Order.PAYMENT_BANK_TRANSFER},
        )
        self.assertRedirects(response, reverse('payment_confirmation', args=[order.id]))

        order.refresh_from_db()
        self.assertEqual(order.payment_method, Order.PAYMENT_BANK_TRANSFER)
        self.assertEqual(order.status, Order.STATUS_PENDING)

    def test_other_user_cannot_process_payment_for_someone_elses_order(self):
        order = self._make_order(user=self.owner)
        self.client.login(username="bob", password="StrongPass123!")
        response = self.client.post(
            reverse('process_payment', args=[order.id]),
            {'payment_method': Order.PAYMENT_BANK_TRANSFER},
            follow=True,
        )
        self.assertRedirects(response, reverse('product_list'))
        order.refresh_from_db()
        self.assertEqual(order.payment_method, "")


class PaymentConfirmationViewTests(OrdersTestBase):
    def test_whatsapp_message_built_when_method_is_whatsapp(self):
        order = self._make_order(user=self.owner)
        order.payment_method = Order.PAYMENT_WHATSAPP
        order.save()

        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.get(reverse('payment_confirmation', args=[order.id]))

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.context['whatsapp_message'], "")
        self.assertIn(order.order_number, response.context['whatsapp_message'].replace('%20', ' '))

    def test_no_whatsapp_message_for_other_payment_methods(self):
        order = self._make_order(user=self.owner)
        order.payment_method = Order.PAYMENT_BANK_TRANSFER
        order.save()

        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.get(reverse('payment_confirmation', args=[order.id]))

        self.assertEqual(response.context['whatsapp_message'], "")

    def test_post_without_receipt_shows_error_and_redirects(self):
        order = self._make_order(user=self.owner)
        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.post(
            reverse('payment_confirmation', args=[order.id]), {'notes': 'test'}
        )
        self.assertRedirects(response, reverse('payment_confirmation', args=[order.id]))
        order.refresh_from_db()
        self.assertFalse(order.payment_receipt)

    def test_post_with_oversized_receipt_is_rejected(self):
        order = self._make_order(user=self.owner)
        self.client.login(username="jane", password="StrongPass123!")

        oversized = SimpleUploadedFile(
            "receipt.jpg",
            b"x" * (5 * 1024 * 1024 + 1),
            content_type="image/jpeg",
        )
        response = self.client.post(
            reverse('payment_confirmation', args=[order.id]),
            {'receipt': oversized},
        )
        self.assertRedirects(response, reverse('payment_confirmation', args=[order.id]))
        order.refresh_from_db()
        self.assertFalse(order.payment_receipt)

    def test_post_with_valid_receipt_saves_and_redirects_to_success(self):
        order = self._make_order(user=self.owner)
        self.client.login(username="jane", password="StrongPass123!")

        receipt = SimpleUploadedFile(
            "receipt.jpg", b"small file content", content_type="image/jpeg"
        )
        response = self.client.post(
            reverse('payment_confirmation', args=[order.id]),
            {'receipt': receipt, 'notes': 'Paid via transfer'},
        )
        self.assertRedirects(response, reverse('receipt_upload_success', args=[order.id]))

        order.refresh_from_db()
        self.assertTrue(order.payment_receipt)
        self.assertIsNotNone(order.receipt_uploaded_at)


class ReceiptUploadSuccessViewTests(OrdersTestBase):
    def test_owner_can_view_success_page(self):
        order = self._make_order(user=self.owner)
        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.get(reverse('receipt_upload_success', args=[order.id]))
        self.assertEqual(response.status_code, 200)

    def test_other_user_blocked_from_success_page(self):
        order = self._make_order(user=self.owner)
        self.client.login(username="bob", password="StrongPass123!")
        response = self.client.get(
            reverse('receipt_upload_success', args=[order.id]), follow=True
        )
        self.assertRedirects(response, reverse('product_list'))


class OrderHistoryViewTests(OrdersTestBase):
    def test_order_history_shows_only_current_users_orders(self):
        my_order = self._make_order(user=self.owner)
        self._make_order(user=self.other_user)

        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.get(reverse('order_history'))

        orders = list(response.context['orders'])
        self.assertEqual(orders, [my_order])

    def test_order_history_redirect_url_name(self):
        """
        order_history calls redirect('login') for anonymous users, but the
        account app's login URL is namespaced as 'account:login'. If there's
        no bare top-level url named 'login' in the project, this raises
        NoReverseMatch (i.e. a 500 error in production) instead of a clean
        redirect. This test documents that behavior either way so a fix
        shows up as a passing assertion instead of a silent regression.
        """
        try:
            response = self.client.get(reverse('order_history'))
        except NoReverseMatch:
            self.fail(
                "order_history redirects anonymous users to a URL named "
                "'login', which doesn't resolve — it should redirect to "
                "'account:login' instead. Update the view's redirect('login') "
                "call to redirect('account:login')."
            )
        else:
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse('account:login'))


class OrderDetailViewTests(OrdersTestBase):
    def test_order_detail_requires_login(self):
        order = self._make_order(user=self.owner)
        response = self.client.get(reverse('order_detail', args=[order.id]))
        self.assertRedirects(
            response,
            f"{reverse('account:login')}?next={reverse('order_detail', args=[order.id])}"
        )

    def test_owner_sees_items_with_no_review_yet(self):
        order = self._make_order(user=self.owner)
        self.client.login(username="jane", password="StrongPass123!")
        response = self.client.get(reverse('order_detail', args=[order.id]))

        self.assertEqual(response.status_code, 200)
        items_with_reviews = response.context['items_with_reviews']
        self.assertEqual(len(items_with_reviews), 1)
        self.assertIsNone(items_with_reviews[0]['review'])

    def test_other_user_blocked_from_order_detail(self):
        order = self._make_order(user=self.owner)
        self.client.login(username="bob", password="StrongPass123!")
        response = self.client.get(
            reverse('order_detail', args=[order.id]), follow=True
        )
        self.assertRedirects(response, reverse('product_list'))
# Create your tests here.
