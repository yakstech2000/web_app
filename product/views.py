from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Product, Category, Brand


@login_required
def product_list(request):
    """Display list of all products with search and filter"""
    products = Product.objects.all().order_by('-created_at')

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
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


@login_required
def product_detail(request, pk):
    """Display product detail page"""
    product = get_object_or_404(Product, pk=pk)
    related_products = Product.objects.filter(
        category=product.category
    ).exclude(pk=pk)[:5]

    context = {
        'product': product,
        'related_products': related_products,
    }

    return render(request, 'products/product_detail.html', context)

""""""
@login_required
def product_create(request):
    """Create a new product"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        cost_price = request.POST.get('cost_price')
        stock = request.POST.get('stock')
        low_stock_threshold = request.POST.get('low_stock_threshold', 10)
        category_id = request.POST.get('category')
        brand_id = request.POST.get('brand')
        image = request.FILES.get('image')

        try:
            product = Product.objects.create(
                name=name,
                description=description,
                price=price,
                cost_price=cost_price or None,
                stock=stock,
                low_stock_threshold=low_stock_threshold,
                category_id=category_id or None,
                brand_id=brand_id or None,
                image=image
            )
            messages.success(request, f'Product "{product.name}" created successfully!')
            return redirect('product_detail', pk=product.pk)
        except Exception as e:
            messages.error(request, f'Error creating product: {str(e)}')

    categories = Category.objects.all()
    brands = Brand.objects.all()

    context = {
        'categories': categories,
        'brands': brands,
    }

    return render(request, 'products/product_form.html', context)


@login_required
def product_update(request, pk):
    """Update an existing product"""
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        product.name = request.POST.get('name', product.name)
        product.description = request.POST.get('description', product.description)
        product.price = request.POST.get('price', product.price)
        product.cost_price = request.POST.get('cost_price') or None
        product.stock = request.POST.get('stock', product.stock)
        product.low_stock_threshold = request.POST.get('low_stock_threshold', product.low_stock_threshold)

        category_id = request.POST.get('category')
        product.category_id = category_id or None

        brand_id = request.POST.get('brand')
        product.brand_id = brand_id or None

        if request.FILES.get('image'):
            product.image = request.FILES.get('image')

        try:
            product.save()
            messages.success(request, f'Product "{product.name}" updated successfully!')
            return redirect('product_detail', pk=product.pk)
        except Exception as e:
            messages.error(request, f'Error updating product: {str(e)}')

    categories = Category.objects.all()
    brands = Brand.objects.all()

    context = {
        'product': product,
        'categories': categories,
        'brands': brands,
    }

    return render(request, 'products/product_form.html', context)


@login_required
@require_http_methods(["POST"])
def product_delete(request, pk):
    """Delete a product"""
    product = get_object_or_404(Product, pk=pk)
    product_name = product.name

    try:
        product.delete()
        messages.success(request, f'Product "{product_name}" deleted successfully!')
        return redirect('product_list')
    except Exception as e:
        messages.error(request, f'Error deleting product: {str(e)}')
        return redirect('product_detail', pk=pk)


@login_required
def low_stock_products(request):
    """Display products with low stock"""
    from django.db.models import F

    products = Product.objects.filter(stock__lte=F('low_stock_threshold')).order_by('stock')

    paginator = Paginator(products, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'products': page_obj.object_list,
        'title': 'Low Stock Products',
    }

    return render(request, 'products/low_stock_products.html', context)


@login_required
def best_selling_products(request):
    """Display best selling products"""
    from django.db.models import Count

    products = Product.objects.annotate(
        total_sold=Count('order_items')
    ).order_by('-total_sold')

    paginator = Paginator(products, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'products': page_obj.object_list,
        'title': 'Best Selling Products',
    }


    return render(request, 'products/best_selling_products.html', context)


# Create your views here


def base(request):

    return render(request, 'base.html')
def home(request):

    return render(request, 'home.html')