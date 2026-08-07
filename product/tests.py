from django.test import TestCase
"""
Tests for product.views.product_detail

Covers the bug we fixed: the view built `related_product` (singular)
but the template checked `related_products` (plural), so the section
silently never rendered.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from product.models import Category, Brand, Product


TINY_GIF = SimpleUploadedFile(
    "test.gif",
    b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
    content_type="image/gif",
)


class ProductDetailRelatedProductsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.brand = Brand.objects.create(name="Apple")
        self.phones = Category.objects.create(name="Phones")
        self.laptops = Category.objects.create(name="Laptops")

        self.main_product = Product.objects.create(
            name="iPhone 15",
            brand=self.brand,
            category=self.phones,
            description="A phone.",
            selling_price=999.00,
            stock_quantity=10,
            product_image=TINY_GIF,
        )

    def _detail_url(self, product):
        # adjust the url name / kwarg name if yours differs
        return reverse('product_detail', args=[product.id])

    def test_product_detail_loads(self):
        response = self.client.get(self._detail_url(self.main_product))
        self.assertEqual(response.status_code, 200)

    def test_related_products_context_key_is_plural(self):
        """Regression test for the related_product / related_products name mismatch."""
        response = self.client.get(self._detail_url(self.main_product))
        self.assertIn('related_products', response.context)

    def test_related_products_same_category_shown(self):
        related = Product.objects.create(
            name="iPhone 14",
            brand=self.brand,
            category=self.phones,
            description="Last year's phone.",
            selling_price=799.00,
            stock_quantity=5,
            product_image=TINY_GIF,
        )

        response = self.client.get(self._detail_url(self.main_product))
        related_products = response.context['related_products']

        self.assertIn(related, related_products)
        self.assertContains(response, "Related Products")
        self.assertContains(response, "iPhone 14")

    def test_related_products_excludes_itself(self):
        response = self.client.get(self._detail_url(self.main_product))
        related_products = response.context['related_products']
        self.assertNotIn(self.main_product, related_products)

    def test_related_products_different_category_excluded(self):
        other_category_product = Product.objects.create(
            name="MacBook Pro",
            brand=self.brand,
            category=self.laptops,
            description="A laptop.",
            selling_price=1999.00,
            stock_quantity=3,
            product_image=TINY_GIF,
        )

        response = self.client.get(self._detail_url(self.main_product))
        related_products = response.context['related_products']
        self.assertNotIn(other_category_product, related_products)

    def test_no_related_products_section_when_alone_in_category(self):
        response = self.client.get(self._detail_url(self.main_product))
        content = response.content.decode()
        idx = content.find("Related Products")
        print("DEBUG match context:", content[max(0, idx - 200):idx + 200])
        self.assertNotContains(response, "Related Products")
    def test_related_products_capped_at_five(self):
        for i in range(7):
            Product.objects.create(
                name=f"iPhone Variant {i}",
                brand=self.brand,
                category=self.phones,
                description="A phone variant.",
                selling_price=899.00,
                stock_quantity=5,
                product_image=TINY_GIF,
            )

        response = self.client.get(self._detail_url(self.main_product))
        related_products = response.context['related_products']
        self.assertEqual(len(related_products), 5)
# Create your tests here.
