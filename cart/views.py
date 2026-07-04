
# Create your views here.
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from product.models import Product
from .models import Cart, CartItem


def _get_cart(request):
    """
    Returns the Cart for the current visitor, creating one if needed.
    - Logged-in users: cart tied to request.user.
    - Guests: cart tied to the session key (session is created if it
      doesn't exist yet, so anonymous carts persist across requests).
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    if not request.session.session_key:
        request.session.create()

    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key, user=None)
    return cart


def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method != 'POST':
        return redirect('product_detail', product_id)

    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1

    # Clamp between 1 and available stock so nothing invalid gets stored.
    quantity = max(1, min(quantity, product.stock_quantity))

    if not product.is_available or product.stock_quantity < 1:
        messages.error(request, f"{product.name} is currently out of stock.")
        return redirect('product_detail', product_id)

    cart = _get_cart(request)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={'quantity': quantity})

    if not created:
        # Item already in cart — add to the existing quantity, still capped at stock.
        cart_item.quantity = max(1, min(cart_item.quantity + quantity, product.stock_quantity))
        cart_item.save()

    messages.success(request, f"Added {quantity} x {product.name} to your cart.")
    return redirect('cart_detail')


def cart_detail(request):
    cart = _get_cart(request)
    items = cart.items.select_related('product').all()

    context = {
        'cart': cart,
        'items': items,
        'total_price': cart.get_total_price(),
        'total_items': cart.get_total_items(),
    }
    return render(request, 'cart.html', context)


def cart_update(request, item_id):
    cart = _get_cart(request)
    cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)

    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 1))
        except (TypeError, ValueError):
            quantity = 1

        quantity = max(1, min(quantity, cart_item.product.stock_quantity))
        cart_item.quantity = quantity
        cart_item.save()
        messages.success(request, "Cart updated.")

    return redirect('cart_detail')


def cart_remove(request, item_id):
    cart = _get_cart(request)
    cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    product_name = cart_item.product.name
    cart_item.delete()
    messages.success(request, f"Removed {product_name} from your cart.")
    return redirect('cart_detail')
