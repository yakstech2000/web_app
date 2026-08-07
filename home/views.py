"""
HOME PAGE VIEWS
===============
Views for home page: category grid + reviews.
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Avg, Q

from product.models import Product, Category
from orders.models import Order, OrderItem
from home.models import ReviewRequest
from product_reviews.models import ProductReview


def home(request):
    """
    Home page: category grid + featured/recent reviews.
    """
    categories = Category.objects.all()[:4]

    # Get featured reviews
    featured_reviews = ProductReview.objects.filter(
        is_featured=True
    ).select_related('customer', 'product')[:5]

    # Fall back to the most recent reviews if nothing has been marked
    # as featured yet, so the homepage section isn't perpetually empty
    # on a fresh store before an admin has curated any.
    reviews_to_display = featured_reviews
    if not reviews_to_display.exists():
        reviews_to_display = ProductReview.objects.select_related(
            'customer', 'product'
        ).order_by('-created_at')[:6]

    context = {
        'categories': categories,
        'featured_reviews': featured_reviews,
        'reviews': reviews_to_display,
    }

    return render(request, 'home.html', context)


@require_http_methods(["GET"])
def get_featured_reviews(request):
    """
    AJAX endpoint to get featured reviews dynamically
    """
    featured_reviews = ProductReview.objects.filter(
        is_featured=True
    ).select_related('customer', 'product').values(
        'id',
        'customer__username',
        'customer__first_name',
        'product__name',
        'product__id',
        'rating',
        'review_text',
        'created_at'
    )[:5]

    return JsonResponse({
        'success': True,
        'reviews': list(featured_reviews)
    })


@require_http_methods(["GET"])
def get_product_reviews(request, product_id):
    """
    AJAX endpoint to get all reviews for a specific product
    """
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)

    reviews = ProductReview.objects.filter(
        product=product
    ).select_related('customer').values(
        'id',
        'customer__username',
        'rating',
        'review_text',
        'title',
        'created_at'
    ).order_by('-created_at')

    avg_rating = ProductReview.objects.filter(
        product=product
    ).aggregate(Avg('rating'))['rating__avg'] or 0

    review_count = reviews.count()

    return JsonResponse({
        'success': True,
        'product_name': product.name,
        'avg_rating': float(avg_rating),
        'review_count': review_count,
        'reviews': list(reviews)
    })

# Create your views here.