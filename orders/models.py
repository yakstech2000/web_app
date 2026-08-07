from decimal import Decimal

from django.conf import settings
from django.db import models

from product.models import Product


class PickupLocation(models.Model):
    """
    A store location customers can pick up orders from.

    Only one location exists today, but Order references it by FK (not a
    hardcoded string) specifically so adding a second, third, etc. store is
    just adding a row here — no changes needed to checkout view, template,
    or the Order model itself.
    """
    name = models.CharField(max_length=100)
    address = models.TextField()
    confirmation_message = models.TextField(
        blank=True,
        default=(
            "You have selected Store Pickup. Your order will be prepared "
            "for collection at our store. We will contact you when it is ready."
        ),
        help_text="Shown to the customer at checkout when they select this location.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive locations won't be offered as a pickup option at checkout.",
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Pickup Location'
        verbose_name_plural = 'Pickup Locations'

    def __str__(self):
        return self.name


class Order(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    PAYMENT_PAYSTACK = 'paystack'
    PAYMENT_BANK_TRANSFER = 'bank_transfer'
    PAYMENT_WHATSAPP = 'whatsapp'

    PAYMENT_CHOICES = [
        (PAYMENT_PAYSTACK, 'Paystack'),
        (PAYMENT_BANK_TRANSFER, 'Bank Transfer'),
        (PAYMENT_WHATSAPP, 'WhatsApp'),
    ]

    FULFILLMENT_DELIVERY = 'delivery'
    FULFILLMENT_PICKUP = 'pickup'

    FULFILLMENT_CHOICES = [
        (FULFILLMENT_DELIVERY, 'Delivery'),
        (FULFILLMENT_PICKUP, 'Store Pickup'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='orders',
    )

    order_number = models.CharField(max_length=20, unique=True, blank=True)
    full_name = models.CharField(max_length=50)
    email = models.EmailField()
    phone = models.CharField(max_length=20)

    # Delivery-only fields — blank for pickup orders.
    address = models.TextField(blank=True)
    state = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    country = models.CharField(max_length=50, blank=True, null=True)

    fulfillment_method = models.CharField(
        max_length=20,
        choices=FULFILLMENT_CHOICES,
        default=FULFILLMENT_DELIVERY,
    )
    delivery_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Currently always 0 — delivery fee is arranged directly with the customer.",
    )
    pickup_location = models.ForeignKey(
        PickupLocation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='orders',
        help_text="Set only when fulfillment_method is 'pickup'.",
    )

    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    payment_receipt = models.FileField(
        upload_to='receipts/',
        null=True,
        blank=True,
        help_text="Upload bank transfer receipt or payment proof"
    )
    receipt_uploaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.order_number or f"Order #{self.pk}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new and not self.order_number:
            self.order_number = f"DR{10000 + self.pk}"
            super().save(update_fields=['order_number'])

    def get_total_items(self):
        return sum(item.quantity for item in self.items.all())


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name='order_items')

    product_name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"

    def get_subtotal(self):
        return self.price * self.quantity


class DeliveryOrder(Order):
    """
    Proxy model — same table as Order, filtered to fulfillment_method='delivery'
    in DeliveryOrderAdmin. Exists purely so the admin sidebar shows a clean,
    separate "Delivery Orders" list instead of one mixed list admin has to
    mentally filter every time.
    """
    class Meta:
        proxy = True
        verbose_name = 'Delivery Order'
        verbose_name_plural = 'Delivery Orders'


class PickupOrder(Order):
    """
    Proxy model — same table as Order, filtered to fulfillment_method='pickup'
    in PickupOrderAdmin. See DeliveryOrder above for why this exists.
    """
    class Meta:
        proxy = True
        verbose_name = 'Pickup Order'
        verbose_name_plural = 'Pickup Orders'