from django.contrib import admin
from .models import ReviewRequest


@admin.register(ReviewRequest)
class ReviewRequestAdmin(admin.ModelAdmin):
    list_display = ('customer', 'product', 'status', 'sent_at')
    list_filter = ('status', 'sent_at')
    search_fields = ('customer__username', 'product__name')
    readonly_fields = ('sent_at', 'viewed_at')
# Register your models here.