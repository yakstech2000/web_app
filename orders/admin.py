"""
Orders Admin Configuration
Delivery and Pickup orders are shown as two separate admin sections
(via proxy models) instead of one mixed list, so admin never has to
figure out which type an order is at a glance.

payment_method is read-only everywhere — it reflects whatever the customer
actually selected at checkout (WhatsApp / Bank Transfer / Paystack) and
should never be changed by admin. The only field admin edits is `status`,
which is what drives the email notifications and the customer-facing
tracking timeline (OrderStatusHistory) below.
"""

from django.contrib import admin
from django.contrib import messages

from .models import Order, OrderItem, OrderStatusHistory, PickupLocation, DeliveryOrder, PickupOrder
from .emails import send_payment_confirmed_email, send_order_shipped_email, send_order_cancelled_email

# Once an order reaches one of these, it shouldn't move backward to an
# earlier stage — there's no return/refund workflow yet, so allowing e.g.
# completed → processing would just corrupt the tracking timeline with an
# out-of-order history entry. Same status → same status (re-saving without
# changing it) is always allowed and simply skips history logging.
TERMINAL_STATUSES = {Order.STATUS_COMPLETED, Order.STATUS_CANCELLED}


class OrderItemInline(admin.TabularInline):
    """Inline display of order items"""
    model = OrderItem
    extra = 0
    fields = ('product_name', 'price', 'quantity')
    readonly_fields = ('product_name', 'price', 'quantity')
    can_delete = False


class OrderStatusHistoryInline(admin.TabularInline):
    """
    Read-only view of this order's tracking history, shown right on the
    order edit page so admin doesn't need to hunt for it elsewhere.
    """
    model = OrderStatusHistory
    extra = 0
    fields = ('status', 'note', 'changed_by', 'created_at')
    readonly_fields = ('status', 'note', 'changed_by', 'created_at')
    can_delete = False
    ordering = ('created_at',)

    def has_add_permission(self, request, obj=None):
        # History entries are only ever created automatically by
        # save_model() below, driven by an actual status change — never
        # hand-added, so there's no invented/fake tracking data.
        return False


class BaseOrderAdmin(admin.ModelAdmin):
    """
    Shared behavior for Delivery and Pickup order admin. Not registered
    directly — DeliveryOrderAdmin and PickupOrderAdmin below subclass this.
    """
    inlines = [OrderItemInline, OrderStatusHistoryInline]
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

    def _log_status_history(self, order, status, request, note=''):
        OrderStatusHistory.objects.create(
            order=order,
            status=status,
            note=note,
            changed_by=request.user,
        )

    def save_model(self, request, obj, form, change):
        """
        Trigger emails + log tracking history based on status changes:
        - pending → paid: payment confirmation
        - paid → processing: tracking checkpoint only (no email — this is
          an optional, low-key "we're preparing your order" milestone)
        - (paid or processing) → completed: shipment/pickup-ready email +
          review request. Accepts either prior state since 'processing' is
          optional — admin can skip straight from paid to completed exactly
          as before.
        - any → cancelled: cancellation notice
        - completed/cancelled → anything else: blocked, no return/refund
          workflow exists yet to make that a valid transition.
        """
        if change:  # Only on edit, not on create
            try:
                old_status = Order.objects.get(pk=obj.pk).status
                new_status = obj.status

                if old_status == new_status:
                    # Nothing actually changed — save normally, no history entry.
                    super().save_model(request, obj, form, change)
                    return

                if old_status in TERMINAL_STATUSES and new_status != old_status:
                    messages.error(
                        request,
                        f"❌ Can't change status from '{obj.get_status_display()}' "
                        f"back to an earlier stage — order status wasn't updated. "
                        f"(No return/refund workflow exists yet for this.)"
                    )
                    # Revert the in-memory status so the save doesn't apply
                    # the blocked change.
                    obj.status = old_status
                    super().save_model(request, obj, form, change)
                    return

                if old_status == Order.STATUS_PENDING and new_status == Order.STATUS_PAID:
                    super().save_model(request, obj, form, change)
                    self._log_status_history(obj, new_status, request)
                    try:
                        send_payment_confirmed_email(obj)
                        messages.success(request, f"✅ Payment confirmation email sent to {obj.email}")
                    except Exception as e:
                        messages.warning(request, f"⚠️ Payment email failed: {str(e)}")

                elif old_status == Order.STATUS_PAID and new_status == Order.STATUS_PROCESSING:
                    super().save_model(request, obj, form, change)
                    self._log_status_history(obj, new_status, request)
                    messages.success(request, "✅ Order marked as processing.")

                elif old_status in (Order.STATUS_PAID, Order.STATUS_PROCESSING) and new_status == Order.STATUS_COMPLETED:
                    super().save_model(request, obj, form, change)
                    self._log_status_history(obj, new_status, request)
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

                elif new_status == Order.STATUS_CANCELLED and old_status != Order.STATUS_CANCELLED:
                    super().save_model(request, obj, form, change)
                    self._log_status_history(obj, new_status, request)
                    try:
                        send_order_cancelled_email(obj)
                        messages.success(request, f"✅ Cancellation email sent to {obj.email}")
                    except Exception as e:
                        messages.warning(request, f"⚠️ Cancellation email failed: {str(e)}")

                else:
                    # Any other transition we don't have specific handling
                    # for (shouldn't normally be reachable given the choices
                    # above, but saved + logged rather than silently ignored).
                    super().save_model(request, obj, form, change)
                    self._log_status_history(obj, new_status, request)

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