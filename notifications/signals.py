"""
Signal-based triggers — used specifically for review creation and stock
changes because these fire regardless of which view/code path actually
saves the model, without needing to modify product_reviews' own views.
(Order creation, receipt upload, and signup are hooked directly into their
views instead, in orders/views.py and account/views.py, since those are
single well-known entry points already.)
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from product.models import Product

from .services import notify_low_stock, notify_new_review

try:
    from product_reviews.models import ProductReview
except ImportError:
    # App/model name assumed — adjust the import above if your actual
    # review model lives elsewhere or is named differently.
    ProductReview = None


@receiver(post_save, sender=Product)
def product_stock_changed(sender, instance, created, **kwargs):
    if created:
        return  # a brand-new product isn't a "stock just dropped" event
    notify_low_stock(instance)


if ProductReview is not None:
    @receiver(post_save, sender=ProductReview)
    def review_created(sender, instance, created, **kwargs):
        if not created:
            return
        notify_new_review(instance)