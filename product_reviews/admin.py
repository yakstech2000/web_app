from django.contrib import admin
from .models import ProductReview


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('customer', 'product', 'order', 'rating', 'is_featured', 'created_at')
    list_filter = ('rating', 'is_featured', 'created_at')
    search_fields = ('customer__username', 'product__name', 'order__order_number')
    actions = ['mark_featured', 'unmark_featured']

    # Reviews can only be written by customers through the storefront
    # (and only after a verified purchase). Admin can moderate — view,
    # feature/unfeature, or delete — but never create one or edit its
    # content, since that would mean the review isn't really the
    # customer's own words anymore.
    readonly_fields = (
        'customer', 'product', 'order', 'rating', 'title', 'review_text', 'image',
        'is_verified_purchase', 'helpful_count', 'created_at', 'updated_at',
    )

    def has_add_permission(self, request):
        return False

    def mark_featured(self, request, queryset):
        queryset.update(is_featured=True)
    mark_featured.short_description = "Mark selected as featured"

    def unmark_featured(self, request, queryset):
        queryset.update(is_featured=False)
    unmark_featured.short_description = "Unmark selected as featured"
# Register your models here.
