from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Product, Category, Brand


def product_list(request):
    """Display list of all products with search and filter"""
    products = Product.objects.all().order_by('-created_at')

    # Search functionality
    # Split into individual words so "iphone 15pro" still matches a product
    # named "iPhone 15 Pro" even though the spacing/casing differs.
    # Every word must appear somewhere in the name or description (in any order).
    search_query = request.GET.get('search', '')
    if search_query:
        search_terms = search_query.split()
        for term in search_terms:
            products = products.filter(
                Q(name__icontains=term) |
                Q(description__icontains=term)
            )

    # Filter by category
    category_id = request.GET.get('category', '')
    if category_id:
        products = products.filter(category_id=category_id)

    # Filter by brand
    brand_id = request.GET.get('brand', '')
    if brand_id:
        products = products.filter(brand_id=brand_id)

    # Pagination
    paginator = Paginator(products, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get all categories and brands for filter dropdowns
    categories = Category.objects.all()
    brands = Brand.objects.all()

    context = {
        'page_obj': page_obj,
        'products': page_obj.object_list,
        'search_query': search_query,
        'categories': categories,
        'brands': brands,
        'selected_category': category_id,
        'selected_brand': brand_id,
    }

    return render(request, 'products/product_list.html', context)


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    related_products = Product.objects.filter(
        category=product.category
    ).exclude(pk=product_id)[:5]

    return render(request, 'products/product_detail.html', {
        'product': product,
        'related_products': related_products   # plural, matches template
    })

def base(request):
    """Render base template"""
    return render(request, 'base.html')