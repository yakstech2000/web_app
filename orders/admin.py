"""
Orders Admin Configuration
Delivery and Pickup orders are shown as two separate admin sections
(via proxy models) instead of one mixed list, so admin never has to
figure out which type an order is at a glance.

payment_method is read-only everywhere — it reflects whatever the customer
actually selected at checkout (WhatsApp / Bank Transfer / Paystack) and
should never be changed by admin. The only field admin edits is `status`,
which is what drives the email notifications below.
"""

from django.contrib import admin
from django.contrib import messages

from .models import Order, OrderItem, PickupLocation, DeliveryOrder, PickupOrder
from .emails import send_payment_confirmed_email, send_order_shipped_email, send_order_cancelled_email


class OrderItemInline(admin.TabularInline):
    """Inline display of order items"""
    model = OrderItem
    extra = 0
    fields = ('product_name', 'price', 'quantity')
    readonly_fields = ('product_name', 'price', 'quantity')
    can_delete = False


class BaseOrderAdmin(admin.ModelAdmin):
    """
    Shared behavior for Delivery and Pickup order admin. Not registered
    directly — DeliveryOrderAdmin and PickupOrderAdmin below subclass this.
    """
    inlines = [OrderItemInline]
    date_hierarchy = 'created_at'
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('order_number', 'full_name', 'email', 'phone')

    # Everything except `status` is set by the customer at checkout and
    # should never be hand-edited by admin.
    readonly_fields = (
        'order_number', 'created_at', 'total_price', 'full_name',
        'email', 'phone', 'address', 'state', 'city', 'country',
        'fulfillment_method', 'pickup_location', 'payment_method',
        'receipt_uploaded_at',
    )

    def has_add_permission(self, request):
        """Disable adding orders through admin — they're created via checkout only"""
        return False

    def save_model(self, request, obj, form, change):
        """
        Trigger emails based on status changes:
        - pending → paid: payment confirmation
        - paid → completed: shipment/completion + review request
        - any → cancelled: cancellation notice
        """
        if change:  # Only on edit, not on create
            try:
                old_status = Order.objects.get(pk=obj.pk).status
                new_status = obj.status

                if old_status == 'pending' and new_status == 'paid':
                    super().save_model(request, obj, form, change)
                    try:
                        send_payment_confirmed_email(obj)
                        messages.success(request, f"✅ Payment confirmation email sent to {obj.email}")
                    except Exception as e:
                        messages.warning(request, f"⚠️ Payment email failed: {str(e)}")

                elif old_status == 'paid' and new_status == 'completed':
                    super().save_model(request, obj, form, change)
                    try:
                        send_order_shipped_email(obj)
                        messages.success(request, f"✅ Shipment notification email sent to {obj.email}")
                    except Exception as e:
                        messages.warning(request, f"⚠️ Shipment email failed: {str(e)}")

                    try:
                        from home.emails import send_review_request_email
                        send_review_request_email(obj)
                        messages.success(request, f"✅ Review request email sent to {obj.email}")
                    except ImportError:
                        pass  # home app not installed or function doesn't exist
                    except Exception as e:
                        messages.warning(request, f"⚠️ Review request email failed: {str(e)}")

                elif new_status == 'cancelled' and old_status != 'cancelled':
                    super().save_model(request, obj, form, change)
                    try:
                        send_order_cancelled_email(obj)
                        messages.success(request, f"✅ Cancellation email sent to {obj.email}")
                    except Exception as e:
                        messages.warning(request, f"⚠️ Cancellation email failed: {str(e)}")

                else:
                    # No email trigger for this status change
                    super().save_model(request, obj, form, change)

            except Order.DoesNotExist:
                super().save_model(request, obj, form, change)
            except Exception as e:
                messages.error(request, f"❌ Error saving order: {str(e)}")
                raise
        else:
            # Creating new order (not editing) — blocked by has_add_permission anyway
            super().save_model(request, obj, form, change)


@admin.register(DeliveryOrder)
class DeliveryOrderAdmin(BaseOrderAdmin):
    list_display = (
        'order_number', 'full_name', 'email', 'state', 'country',
        'total_price', 'payment_method', 'status', 'created_at',
    )
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'created_at', 'total_price')
        }),
        ('Customer Information', {
            'fields': ('full_name', 'email', 'phone')
        }),
        ('Shipping Address', {
            'fields': ('address', 'state', 'city', 'country')
        }),
        ('Payment & Status', {
            'fields': ('payment_method', 'status', 'payment_receipt', 'receipt_uploaded_at')
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(fulfillment_method=Order.FULFILLMENT_DELIVERY)


@admin.register(PickupOrder)
class PickupOrderAdmin(BaseOrderAdmin):
    list_display = (
        'order_number', 'full_name', 'email', 'pickup_location',
        'total_price', 'payment_method', 'status', 'created_at',
    )
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'created_at', 'total_price')
        }),
        ('Customer Information', {
            'fields': ('full_name', 'email', 'phone')
        }),
        ('Pickup Details', {
            'fields': ('pickup_location',)
        }),
        ('Payment & Status', {
            'fields': ('payment_method', 'status', 'payment_receipt', 'receipt_uploaded_at')
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(fulfillment_method=Order.FULFILLMENT_PICKUP)


@admin.register(PickupLocation)
class PickupLocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('name', 'address')