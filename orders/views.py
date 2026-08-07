from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_http_methods
import urllib.parse
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Order
from decimal import Decimal

from cart.models import Cart, CartItem
from .models import Order, OrderItem, PickupLocation


def _get_cart(request):
    """Same helper from cart/views.py — gets cart for current user/guest."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    if not request.session.session_key:
        request.session.create()

    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key, user=None)
    return cart
"""
This is ONLY the parts of orders/views.py that change. Everything else in
your existing orders/views.py (order_review, process_payment,
payment_confirmation, receipt_upload_success, order_history, order_detail)
stays exactly as-is.

WHAT TO DO:
1. Add the two new imports below to the top of orders/views.py.
2. Add the DELIVERY_FEE_PLACEHOLDER constant near the top (after imports).
3. Replace your existing `checkout` function with the one below.
"""
# Flat placeholder fee until real delivery-fee calculation (by state/city,
# weight, etc.) is implemented. Change this one value to adjust it everywhere.
DELIVERY_FEE_PLACEHOLDER = Decimal('2000.00')

@login_required
@require_http_methods(["GET", "POST"])
def checkout(request):
    cart = _get_cart(request)
    items = cart.items.select_related('product').all()

    if not items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('cart_detail')

    pickup_locations = PickupLocation.objects.filter(is_active=True)
    subtotal = cart.get_total_price()

    if request.method == 'POST':
        fulfillment_method = request.POST.get('fulfillment_method', Order.FULFILLMENT_DELIVERY)
        if fulfillment_method not in dict(Order.FULFILLMENT_CHOICES):
            fulfillment_method = Order.FULFILLMENT_DELIVERY

        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()

        if not all([full_name, email, phone]):
            messages.error(request, "Full name, email, and phone are required.")
            return redirect('checkout')

        pickup_location = None
        address = state = city = country = ''

        if fulfillment_method == Order.FULFILLMENT_PICKUP:
            pickup_location_id = request.POST.get('pickup_location')
            if pickup_location_id:
                pickup_location = pickup_locations.filter(id=pickup_location_id).first()
            if pickup_location is None:
                pickup_location = pickup_locations.first()
            if pickup_location is None:
                messages.error(request, "Store pickup isn't available right now — please choose delivery.")
                return redirect('checkout')

        else:  # delivery
            address = request.POST.get('address', '').strip()
            state = request.POST.get('state', '').strip()
            city = request.POST.get('city', '').strip()
            country = request.POST.get('country', '').strip()

            if not all([address, state, city, country]):
                messages.error(request, "All delivery address fields are required.")
                return redirect('checkout')

        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            full_name=full_name,
            email=email,
            phone=phone,
            address=address,
            state=state,
            city=city,
            country=country,
            total_price=subtotal,
            fulfillment_method=fulfillment_method,
            delivery_fee=0,
            pickup_location=pickup_location,
        )

        for cart_item in items:
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                product_name=cart_item.product.name,
                price=cart_item.product.selling_price,
                quantity=cart_item.quantity,
            )

        cart.items.all().delete()

        messages.success(request, f"Order created: {order.order_number}")
        return redirect('order_review', order_id=order.id)

    context = {
        'cart': cart,
        'items': items,
        'total_items': cart.get_total_items(),
        'subtotal': subtotal,
        'total_price': subtotal,
        'pickup_locations': pickup_locations,
    }
    return render(request, 'checkout.html', context)
@require_http_methods(["GET"])
def order_review(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if order.user and order.user != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this order.")
        return redirect('product_list')

    items = order.items.all()

    context = {
        'order': order,
        'items': items,
    }
    return render(request, 'order_review.html', context)


@require_http_methods(["POST"])
def process_payment(request, order_id):
    """
    Route to the payment confirmation page where they can see payment details
    and upload receipt - works for all payment methods.
    """
    order = get_object_or_404(Order, id=order_id)

    # Security check
    if order.user and order.user != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to process this order.")
        return redirect('product_list')

    payment_method = request.POST.get('payment_method', '').strip()

    if not payment_method:
        messages.error(request, "Please select a payment method.")
        return redirect('order_review', order_id=order.id)

    # Save the payment method to the order
    order.payment_method = payment_method
    order.status = Order.STATUS_PENDING
    order.save()

    # Redirect to unified payment confirmation page
    return redirect('payment_confirmation', order_id=order.id)


def payment_confirmation(request, order_id):
    """
    Unified payment confirmation page.
    Shows payment details based on method + receipt upload form.
    """
    from django.utils import timezone
    import urllib.parse

    order = get_object_or_404(Order, id=order_id)

    # Security
    if order.user and order.user != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('product_list')

    # Handle receipt upload
    if request.method == 'POST':
        receipt = request.FILES.get('receipt')
        notes = request.POST.get('notes', '').strip()

        if not receipt:
            messages.error(request, "Please select a receipt file.")
            return redirect('payment_confirmation', order_id=order.id)

        # Validate file size (max 5MB)
        if receipt.size > 5 * 1024 * 1024:
            messages.error(request, "File size exceeds 5MB limit.")
            return redirect('payment_confirmation', order_id=order.id)

        # Save receipt
        order.payment_receipt = receipt
        order.receipt_uploaded_at = timezone.now()
        order.save()

        messages.success(request, "Receipt uploaded successfully! We'll verify it shortly.")
        return redirect('receipt_upload_success', order_id=order.id)

    # Prepare WhatsApp message if payment method is WhatsApp
    whatsapp_message = ""
    whatsapp_number = "2349064216350"  # ← CHANGE THIS TO YOUR WHATSAPP NUMBER

    if order.payment_method == 'whatsapp':
        items_text = "\n".join([f"- {item.product_name} × {item.quantity}" for item in order.items.all()])

        message = f"""Hello Dr Apple Store,

I would like to complete my order payment.

Order Number: {order.order_number}
Customer Name: {order.full_name}
Total Amount: ${order.total_price}

Items:
{items_text}

Please assist me with payment details."""

        whatsapp_message = urllib.parse.quote(message)

    context = {
        'order': order,
        'items': order.items.all(),
        'whatsapp_number': whatsapp_number,
        'whatsapp_message': whatsapp_message,
    }
    return render(request, 'payment_confirmation.html', context)


def receipt_upload_success(request, order_id):
    """
    Success page shown after customer uploads payment receipt.
    """
    order = get_object_or_404(Order, id=order_id)

    # Security: only customer or staff can view
    if order.user and order.user != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this page.")
        return redirect('product_list')

    items = order.items.all()

    context = {
        'order': order,
        'items': items,
    }
    return render(request, 'receipt_upload_success.html', context)

def order_history(request):
    """
    User order history — show all orders for logged-in user.
    """
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to view your orders.")
        return redirect('account:login')

    orders = Order.objects.filter(user=request.user).prefetch_related('items').order_by('-created_at')

    context = {
        'orders': orders,
    }
    return render(request, 'order_history.html', context)


@login_required(login_url='account:login')
def order_detail(request, order_id):
    """
    Show order details - read only. Reviews are written from the dashboard's
    My Reviews flow, not from here; this page just displays whatever review
    already exists for each item, once one has been submitted.
    """
    order = get_object_or_404(Order, id=order_id)

    # Ownership check - without this, any logged-in user could view any
    # order (including someone else's name, address, email, phone) just
    # by changing the number in the URL.
    if order.user and order.user != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to view this order.")
        return redirect('product_list')

    items_with_reviews = []
    for item in order.items.all():
        review = order.reviews.filter(product=item.product).first() if item.product_id else None
        items_with_reviews.append({'item': item, 'review': review})

    context = {
        'order': order,
        'items_with_reviews': items_with_reviews,
    }
    return render(request, 'order_detail.html', context)
