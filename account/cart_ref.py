"""
Signed, tamper-proof reference to a guest cart, embedded in magic-link
auth email URLs so a cart built on one device/browser survives even if
the customer opens their sign-in email on a different device.

Only a session key is signed — never cart contents, prices, or personal
data — so nothing sensitive is exposed in the URL itself, and the
signature is timestamped so a stale ref can't be replayed indefinitely.
"""

from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

CART_REF_SALT = 'account.magic-link.cart-ref'
CART_REF_MAX_AGE = 60 * 60 * 24  # 24h — matches the magic-link token expiry


def make_cart_ref(session_key):
    """Sign a guest cart's session key for safe embedding in a URL."""
    signer = TimestampSigner(salt=CART_REF_SALT)
    return signer.sign(session_key)


def guest_cart_ref_for_session(session_key):
    """
    Returns a signed cart_ref for the given session's guest cart, or None
    if that session has no cart, or the cart is empty (nothing worth
    carrying over).
    """
    if not session_key:
        return None

    from cart.models import Cart

    guest_cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()
    if not guest_cart or not guest_cart.items.exists():
        return None

    return make_cart_ref(session_key)


def reattach_cart(user, cart_ref):
    """
    Given a signed cart_ref from a magic-link URL, find the guest cart it
    points to and merge its items into (or assign it as) the now-
    authenticated user's cart.

    Silently does nothing if the ref is invalid, expired, or the cart it
    points to no longer exists/is empty — cart recovery is a best-effort
    convenience here, not a requirement for login to succeed.
    """
    signer = TimestampSigner(salt=CART_REF_SALT)
    try:
        session_key = signer.unsign(cart_ref, max_age=CART_REF_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return

    from cart.models import Cart

    guest_cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()
    if not guest_cart:
        return

    user_cart, _ = Cart.objects.get_or_create(user=user)

    for item in guest_cart.items.select_related('product').all():
        existing = user_cart.items.filter(product=item.product).first()
        if existing:
            max_qty = item.product.stock_quantity
            existing.quantity = max(1, min(existing.quantity + item.quantity, max_qty))
            existing.save()
        else:
            item.cart = user_cart
            item.save()

    guest_cart.delete()