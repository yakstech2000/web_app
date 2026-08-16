from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
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
from product.models import Product
from .tracking import build_order_timeline

# Reused so a post-purchase account is created under the same password
# rules and audit logging as a normal signup.
from account.forms import SetNewPasswordForm
from account.decorators import get_client_ip
from account.models import UserAuditLog


def _get_cart(request):
    """Same helper from cart/views.py — gets cart for current user/guest."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    if not request.session.session_key:
        request.session.create()

    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key, user=None)
    return cart


# Flat placeholder fee until real delivery-fee calculation (by state/city,
# weight, etc.) is implemented. Change this one value to adjust it everywhere.
DELIVERY_FEE_PLACEHOLDER = Decimal('2000.00')


class _BuyNowItem:
    """
    Stands in for a CartItem in the "Buy Now" flow, which deliberately
    never touches the Cart/CartItem models. Exposes the same .product,
    .quantity, .get_subtotal() interface checkout.html already renders,
    so the template needs zero changes to support both flows.
    """
    def __init__(self, product, quantity):
        self.product = product
        self.quantity = quantity

    def get_subtotal(self):
        return self.product.selling_price * self.quantity


@require_http_methods(["POST"])
def buy_now(request, product_id):
    """
    Skips the cart entirely. Stores just this product + quantity in the
    session and sends the shopper straight to checkout — the cart (if they
    have one) is left completely untouched.
    """
    product = get_object_or_404(Product, id=product_id)

    if not product.is_available or product.stock_quantity < 1:
        messages.error(request, f"{product.name} is currently out of stock.")
        return redirect('product_detail', product_id)

    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1
    quantity = max(1, min(quantity, product.stock_quantity))

    request.session['buy_now'] = {'product_id': product.id, 'quantity': quantity}
    return redirect('checkout')


@require_http_methods(["GET", "POST"])
def checkout(request):
    buy_now_data = request.session.get('buy_now')
    cart = None

    if buy_now_data:
        product = get_object_or_404(Product, id=buy_now_data['product_id'])
        quantity = min(buy_now_data['quantity'], product.stock_quantity)

        if not product.is_available or quantity < 1:
            messages.error(request, f"{product.name} is no longer available in that quantity.")
            del request.session['buy_now']
            return redirect('product_detail', product.id)

        items = [_BuyNowItem(product, quantity)]
        subtotal = items[0].get_subtotal()
        total_items = quantity
    else:
        cart = _get_cart(request)
        items = cart.items.select_related('product').all()

        if not items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect('cart_detail')

        subtotal = cart.get_total_price()
        total_items = cart.get_total_items()

    pickup_locations = PickupLocation.objects.filter(is_active=True)

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

        for line_item in items:
            OrderItem.objects.create(
                order=order,
                product=line_item.product,
                product_name=line_item.product.name,
                price=line_item.product.selling_price,
                quantity=line_item.quantity,
            )

        if cart is not None:
            cart.items.all().delete()
        if buy_now_data:
            del request.session['buy_now']

        messages.success(request, f"Order created: {order.order_number}")
        return redirect('order_review', order_id=order.id)

    context = {
        'cart': cart,
        'items': items,
        'total_items': total_items,
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


@login_required(login_url='account:login')
def order_history(request):
    """
    User order history — show all orders for logged-in user.
    """
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
        'timeline': build_order_timeline(order),
    }
    return render(request, 'order_detail.html', context)


@login_required(login_url='account:login')
@require_http_methods(["POST"])
def confirm_order_received(request, order_id):
    """
    Customer-initiated final step of the order lifecycle. Once an order's
    `status` has reached STATUS_COMPLETED (shipped / ready for pickup),
    the customer can confirm they actually received it. This stamps
    `customer_confirmed_at` only — it never changes `order.status`, so the
    admin-driven status field, TERMINAL_STATUSES logic, emails, and the
    tracking timeline in tracking.py are completely unaffected.

    Both checks below are enforced server-side and are not optional —
    the button being hidden in the template is not relied on for security.
    """
    order = get_object_or_404(Order, id=order_id)

    # Ownership check — only the customer who placed this order may confirm
    # it (no staff bypass here, unlike the read-only views above: this is
    # a customer attestation, not something staff should do on their behalf).
    if order.user_id != request.user.id:
        messages.error(request, "You don't have permission to confirm this order.")
        return redirect('product_list')

    # Status check — can only be confirmed once the order has actually
    # reached the completed (shipped / ready for pickup) stage.
    if order.status != Order.STATUS_COMPLETED:
        messages.error(request, "This order can't be confirmed as received yet.")
        return redirect('order_detail', order_id=order.id)

    # Prevent duplicate confirmation.
    if order.customer_confirmed_at:
        messages.info(request, "You've already confirmed receipt of this order.")
        return redirect('order_detail', order_id=order.id)

    order.customer_confirmed_at = timezone.now()
    order.save(update_fields=['customer_confirmed_at'])

    messages.success(request, "Order received successfully. Your order is now completed.")
    return redirect('order_detail', order_id=order.id)


@require_http_methods(["GET", "POST"])
def create_account(request, order_id):
    """
    Optional post-purchase account creation. Reached from the "Want to track
    your order easily?" prompt on receipt_upload_success.html. Guests set a
    password only — name/email/phone are already known from the order.

    TEMPORARY: email verification is disabled site-wide until transactional
    email (Resend/Anymail) is wired up — Railway blocks outbound SMTP, so a
    verification link could never arrive. Accounts are active immediately.
    Revert to the is_active=False + send_verification_email() version (see
    git history / earlier version of this function) once email sending is
    confirmed working again, and log the user in only after verification.
    """
    order = get_object_or_404(Order, id=order_id)

    if request.user.is_authenticated:
        return redirect('order_detail', order_id=order.id)

    if order.user_id:
        messages.info(request, "This order is already linked to an account.")
        return redirect('product_list')

    if request.method == 'POST':
        form = SetNewPasswordForm(request.POST)
        if form.is_valid():
            if User.objects.filter(email=order.email).exists():
                messages.error(request, "An account with this email already exists. Please log in instead.")
                return redirect('account:login')

            user = User.objects.create(
                username=order.email,
                email=order.email,
                first_name=order.full_name.split(' ')[0],
                is_active=True,  # TEMPORARY — see note above
            )
            user.set_password(form.cleaned_data['password1'])
            user.save()

            # Link this order + any other guest orders placed with the same email.
            Order.objects.filter(email=order.email, user__isnull=True).update(user=user)

            UserAuditLog.objects.create(
                user=user,
                action='signup',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
                details={'email': user.email, 'source': 'post_purchase'},
            )

            login(request, user)
            messages.success(request, "Account created! You can now track all your orders here.")
            return redirect('order_history')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field.title()}: {error}')
    else:
        form = SetNewPasswordForm()

    return render(request, 'create_account.html', {'order': order, 'form': form})
