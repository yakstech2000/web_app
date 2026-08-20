from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Notification(models.Model):
    """
    One row per admin/staff notification. Uses a generic relation
    (content_type + object_id) rather than separate nullable FKs to Order/
    Product/ProductReview/User, so new notification types can point at any
    model later without a schema change.
    """
    TYPE_NEW_ORDER = 'new_order'
    TYPE_RECEIPT_UPLOADED = 'receipt_uploaded'
    TYPE_NEW_REVIEW = 'new_review'
    TYPE_NEW_CUSTOMER = 'new_customer'
    TYPE_LOW_STOCK = 'low_stock'
    TYPE_OUT_OF_STOCK = 'out_of_stock'

    TYPE_CHOICES = [
        (TYPE_NEW_ORDER, 'New Order'),
        (TYPE_RECEIPT_UPLOADED, 'Payment Receipt Uploaded'),
        (TYPE_NEW_REVIEW, 'New Review'),
        (TYPE_NEW_CUSTOMER, 'New Customer'),
        (TYPE_LOW_STOCK, 'Low Stock'),
        (TYPE_OUT_OF_STOCK, 'Out of Stock'),
    ]

    TYPE_ICONS = {
        TYPE_NEW_ORDER: '🛒',
        TYPE_RECEIPT_UPLOADED: '💳',
        TYPE_NEW_REVIEW: '⭐',
        TYPE_NEW_CUSTOMER: '👤',
        TYPE_LOW_STOCK: '⚠️',
        TYPE_OUT_OF_STOCK: '⚠️',
    }

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text="The staff user this notification is for. Only is_staff "
                   "users are ever assigned here — enforced in "
                   "notifications/services.py at creation time.",
    )
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.CharField(max_length=500)
    link = models.CharField(max_length=300, blank=True, help_text="Relative URL to open when clicked.")

    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')

    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f"{self.title} → {self.recipient}"

    @property
    def icon(self):
        return self.TYPE_ICONS.get(self.notification_type, '🔔')
# Create your models here.
