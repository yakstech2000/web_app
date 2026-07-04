from django.conf import settings
from django.db import models

from product.models import Product


class Cart(models.Model):
    """
    A cart belongs to EITHER a logged-in user OR an anonymous session — never
    both, and it's fine for both to be null only transiently (see get_or_create
    logic in views.py). This lets guests build a cart before creating an account.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='carts',
    )
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # A logged-in user should only ever have one cart.
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(user__isnull=False),
                name='unique_cart_per_user',
            ),
        ]

    def __str__(self):
        owner = self.user.username if self.user else f"session:{self.session_key}"
        return f"Cart ({owner})"

    def get_total_items(self):
        return sum(item.quantity for item in self.items.all())

    def get_total_price(self):
        return sum(item.get_subtotal() for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'product')

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    def get_subtotal(self):
        return self.product.selling_price * self.quantity
