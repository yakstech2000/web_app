"""
Admin dashboard stats context processor.

Computes real numbers for the stat cards, Sales Overview / Orders Overview
charts, and Top Selling Products panel on the admin index page. Guarded to
only run its queries when the request is under /admin/, so it doesn't add
DB load to every storefront page view.
"""

import json
from datetime import timedelta

from django.db.models import Sum, Count
from django.utils import timezone

from .models import Order, OrderItem
from product.models import Product, Brand, Category
from home.models import ReviewRequest

# Which order statuses count as an actual completed sale
SALES_STATUSES = [Order.STATUS_PAID, Order.STATUS_COMPLETED]

# ReviewRequest has no 'pending' status choice — treat anything that
# hasn't reached 'submitted' yet as pending review.
REVIEW_PENDING_STATUSES = ['sent', 'viewed']


def admin_dashboard_stats(request):
    if not request.path.startswith('/admin/'):
        return {}

    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_of_last_month = (start_of_month - timedelta(days=1)).replace(day=1)

    this_month_orders = Order.objects.filter(created_at__gte=start_of_month)
    last_month_orders = Order.objects.filter(
        created_at__gte=start_of_last_month, created_at__lt=start_of_month
    )

    this_month_sales = this_month_orders.filter(
        status__in=SALES_STATUSES
    ).aggregate(total=Sum('total_price'))['total'] or 0
    last_month_sales = last_month_orders.filter(
        status__in=SALES_STATUSES
    ).aggregate(total=Sum('total_price'))['total'] or 0

    this_month_order_count = this_month_orders.count()
    last_month_order_count = last_month_orders.count()

    def pct_change(current, previous):
        if not previous:
            return None
        return round(((current - previous) / previous) * 100, 1)

    sales_change = pct_change(float(this_month_sales), float(last_month_sales))
    orders_change = pct_change(this_month_order_count, last_month_order_count)

    # Last 7 days, for the small line charts
    daily_sales = []
    daily_orders = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date()
        day_orders = Order.objects.filter(created_at__date=day)
        day_sales = day_orders.filter(
            status__in=SALES_STATUSES
        ).aggregate(total=Sum('total_price'))['total'] or 0
        daily_sales.append(float(day_sales))
        daily_orders.append(day_orders.count())

    # Grouped by the snapshot product_name field (not the product FK) so
    # this stays accurate even for order items whose product was later
    # deleted (product FK is on_delete=SET_NULL).
    top_products = list(
        OrderItem.objects.filter(order__status__in=SALES_STATUSES)
        .values('product_name')
        .annotate(sold=Sum('quantity'))
        .order_by('-sold')[:5]
    )

    # ---- Stat cards (all-time totals) ----

    total_orders = Order.objects.count()
    total_products = Product.objects.count()

    # Customer count: product.Customer has no working User link yet, so
    # derive the count from Orders instead — distinct registered users,
    # plus distinct guest emails for orders with no user attached.
    # TODO: once product.Customer.user is wired up, switch this to
    # Customer.objects.count().
    registered_customers = Order.objects.filter(
        user__isnull=False
    ).values('user').distinct().count()
    guest_customers = Order.objects.filter(
        user__isnull=True
    ).values('email').distinct().count()
    total_customers = registered_customers + guest_customers

    pending_review_requests = ReviewRequest.objects.filter(
        status__in=REVIEW_PENDING_STATUSES
    ).count()

    # Week-over-week comparisons for the stat card badges
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    orders_last_7d = Order.objects.filter(created_at__gte=week_ago).count()
    orders_prev_7d = Order.objects.filter(
        created_at__gte=two_weeks_ago, created_at__lt=week_ago
    ).count()

    products_last_7d = Product.objects.filter(created_at__gte=week_ago).count()
    products_prev_7d = Product.objects.filter(
        created_at__gte=two_weeks_ago, created_at__lt=week_ago
    ).count()

    total_orders_change = pct_change(orders_last_7d, orders_prev_7d)
    total_products_change = pct_change(products_last_7d, products_prev_7d)

    return {
        'admin_dashboard': {
            # Monthly overview panels
            'this_month_sales': this_month_sales,
            'sales_change': sales_change,
            'this_month_orders': this_month_order_count,
            'orders_change': orders_change,
            'top_products': top_products,
            'daily_sales_json': json.dumps(daily_sales),
            'daily_orders_json': json.dumps(daily_orders),

            # Stat cards
            'total_orders': total_orders,
            'total_orders_change': total_orders_change,
            'total_customers': total_customers,
            'total_products': total_products,
            'total_products_change': total_products_change,
            'pending_review_requests': pending_review_requests,
        }
    }