"""
HOME PAGE MODELS
================
Models for tracking review requests sent to customers.
ProductReview has moved to the reviews app.
"""

from django.db import models
from django.contrib.auth.models import User
from product.models import Product


class ReviewRequest(models.Model):
    """
    Track review requests sent to customers
    Prevents duplicate emails
    """
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('viewed', 'Viewed'),
        ('submitted', 'Submitted'),
    ]

    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    order_id = models.IntegerField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    sent_at = models.DateTimeField(auto_now_add=True)
    viewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('customer', 'product', 'order_id')

    def __str__(self):
        return f"Review request for {self.product.name} to {self.customer.username}"