"""
REVIEWS APP MODELS
==================
Customer product reviews - one review per product per order,
so a customer can leave a fresh review each time they rebuy something.
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from product.models import Product
from orders.models import Order


class ProductReview(models.Model):
    """
    Customer reviews for products.
    Tied to a specific order (not just product+customer), so a customer
    who buys the same product again in a separate order can review it again.
    """
    RATING_CHOICES = [
        (5, '⭐⭐⭐⭐⭐ Excellent'),
        (4, '⭐⭐⭐⭐ Good'),
        (3, '⭐⭐⭐ Average'),
        (2, '⭐⭐ Poor'),
        (1, '⭐ Terrible'),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='customer_reviews'
    )
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='product_reviews'
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text='The specific order this review is tied to'
    )
    rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=200, blank=True)
    review_text = models.TextField()
    image = models.ImageField(
        upload_to='reviews/',
        blank=True,
        null=True,
        help_text='Optional photo of the product the customer uploaded with their review'
    )

    # Metadata
    is_verified_purchase = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)  # Admin can feature reviews
    helpful_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('product', 'order')
        indexes = [
            models.Index(fields=['product', '-created_at']),
            models.Index(fields=['customer']),
        ]

    def __str__(self):
        return f"{self.customer.username} reviewed {self.product.name} (Order #{self.order.pk})"

    def get_rating_display_stars(self):
        """Return star rating as emoji"""
        return '⭐' * self.rating
# Create your models here.
