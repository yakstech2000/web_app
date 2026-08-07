from django.test import TestCase
"""
Tests for home.views.home

Covers the two bugs we fixed:
  - categories context variable was missing entirely (silent empty state)
  - categories should be capped at 4 on the homepage grid
"""

from django.test import TestCase, Client
from django.urls import reverse

from product.models import Category, Brand, Product
from product_reviews.models import ProductReview
from orders.models import Order
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile


# 1x1 transparent GIF — smallest valid image Django's ImageField will accept
TINY_GIF = SimpleUploadedFile(
    "test.gif",
    b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
    content_type="image/gif",
)


class HomeViewCategoriesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('home')  # adjust name if your urls.py uses a different name

    def test_home_page_loads(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_no_categories_shows_empty_context(self):
        """With zero categories, the template's {% if categories %} should be falsy."""
        response = self.client.get(self.url)
        self.assertIn('categories', response.context)
        self.assertEqual(len(response.context['categories']), 0)
        self.assertContains(response, "No Categories Yet")

    def test_categories_appear_when_present(self):
        Category.objects.create(name="iPhones")
        Category.objects.create(name="MacBooks")

        response = self.client.get(self.url)
        self.assertEqual(len(response.context['categories']), 2)
        self.assertContains(response, "iPhones")
        self.assertContains(response, "MacBooks")
        self.assertNotContains(response, "No Categories Yet")

    def test_categories_capped_at_four(self):
        """Homepage grid should never show more than 4 categories, even with more in the DB."""
        for i in range(6):
            Category.objects.create(name=f"Category {i}")

        response = self.client.get(self.url)
        self.assertEqual(len(response.context['categories']), 4)


class HomeViewReviewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('home')
        self.user = User.objects.create_user(username='reviewer', password='testpass123')
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
        self.order = Order.objects.create(
            user=self.user,
            full_name="Test Reviewer",
            email="reviewer@example.com",
            phone="1234567890",
            address="123 Test St",
            total_price=999.00,
            status=Order.STATUS_COMPLETED,
        )

    def test_no_reviews_shows_empty_state(self):
        response = self.client.get(self.url)
        self.assertContains(response, "No Reviews Yet")

    def test_recent_reviews_shown_when_none_featured(self):
        """If nothing is marked is_featured, should fall back to recent reviews."""
        ProductReview.objects.create(
            product=self.product,
            customer=self.user,
            order=self.order,
            rating=5,
            review_text="Great phone!",
            is_featured=False,
        )
        response = self.client.get(self.url)
        self.assertEqual(len(response.context['reviews']), 1)
        self.assertContains(response, "Great phone!")

    def test_featured_reviews_prioritized(self):
        ProductReview.objects.create(
            product=self.product,
            customer=self.user,
            order=self.order,
            rating=3,
            review_text="It's okay.",
            is_featured=False,
        )
        featured_order = Order.objects.create(
            user=self.user,
            full_name="Test Reviewer",
            email="reviewer@example.com",
            phone="1234567890",
            address="123 Test St",
            total_price=999.00,
            status=Order.STATUS_COMPLETED,
        )
        ProductReview.objects.create(
            product=self.product,
            customer=self.user,
            order=featured_order,
            rating=5,
            review_text="Featured review!",
            is_featured=True,
        )

        response = self.client.get(self.url)
        reviews = response.context['reviews']
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].review_text, "Featured review!")
# Create your tests here.
