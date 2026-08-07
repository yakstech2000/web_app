from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

from .models import ProductReview
from product.models import Product
from orders.models import Order


def get_eligible_order_and_product(user, order_id, product_id):
    """
    Returns (order, product) only if:
    - the order belongs to this user
    - the order has reached a status meaning they actually received it
    - the product was actually part of that order
    Returns (None, None) if any check fails.
    """
    order = Order.objects.filter(pk=order_id, user=user).first()
    if order is None:
        return None, None

    if order.status != Order.STATUS_COMPLETED:
        return None, None

    if not order.items.filter(product_id=product_id).exists():
        return None, None

    product = get_object_or_404(Product, pk=product_id)
    return order, product


@login_required
def review_form(request, order_id, product_id):
    """Show the review submission/edit form for a specific product within a specific order"""
    order, product = get_eligible_order_and_product(request.user, order_id, product_id)

    if order is None:
        messages.error(request, "You can only review products from your own delivered orders.")
        return redirect('order_detail', order_id=order_id)

    existing_review = ProductReview.objects.filter(product=product, order=order).first()

    return render(request, 'review_form.html', {
        'product': product,
        'order': order,
        'existing_review': existing_review,
    })


@login_required
@require_http_methods(["POST"])
def submit_review(request, order_id, product_id):
    """Create or update a review for a product tied to a specific order"""
    order, product = get_eligible_order_and_product(request.user, order_id, product_id)

    if order is None:
        return JsonResponse({
            'success': False,
            'error': "You can only review products from your own delivered orders."
        }, status=403)

    rating = request.POST.get('rating')
    title = request.POST.get('title', '').strip()
    review_text = request.POST.get('review_text', '').strip()
    image = request.FILES.get('image')

    if not rating or not review_text:
        return JsonResponse({
            'success': False,
            'error': 'Rating and review text are required.'
        })

    if len(review_text) < 10:
        return JsonResponse({
            'success': False,
            'error': 'Review must be at least 10 characters.'
        })

    review, created = ProductReview.objects.update_or_create(
        product=product,
        order=order,
        defaults={
            'customer': request.user,
            'rating': rating,
            'title': title,
            'review_text': review_text,
        }
    )

    if image:
        review.image = image
        review.save()

    message = 'Thanks for your review!' if created else 'Your review has been updated.'
    return JsonResponse({'success': True, 'message': message})


@login_required
def my_reviews(request):
    """List every review the logged-in customer has written, plus items
    from completed orders that are still awaiting a review."""
    reviews = ProductReview.objects.filter(
        customer=request.user
    ).select_related('product', 'order').order_by('-created_at')

    reviewable_items = []
    completed_orders = Order.objects.filter(
        user=request.user, status=Order.STATUS_COMPLETED
    ).prefetch_related('items', 'reviews')

    for order in completed_orders:
        reviewed_product_ids = set(order.reviews.values_list('product_id', flat=True))
        for item in order.items.all():
            if item.product_id and item.product_id not in reviewed_product_ids:
                reviewable_items.append({'order': order, 'item': item})

    return render(request, 'my_review.html', {
        'reviews': reviews,
        'reviewable_items': reviewable_items,
    })


@login_required
def edit_review(request, review_id):
    """Edit an existing review - reuses the same form as writing a new one"""
    review = get_object_or_404(ProductReview, pk=review_id, customer=request.user)

    return render(request, 'review_form.html', {
        'product': review.product,
        'order': review.order,
        'existing_review': review,
    })


@login_required
@require_http_methods(["POST"])
def delete_review(request, review_id):
    """Delete one of the logged-in customer's own reviews"""
    review = get_object_or_404(ProductReview, pk=review_id, customer=request.user)
    review.delete()
    messages.success(request, 'Review deleted.')
    return redirect('my_reviews')
# Create your views here.
