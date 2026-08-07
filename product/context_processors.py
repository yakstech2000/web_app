"""
Context processor to make Category and Brand querysets available
in every template's context (e.g. for the site-wide header search/filter form),
without every view needing to pass them in manually.
"""

from .models import Category, Brand


def categories_and_brands(request):
    return {
        'nav_categories': Category.objects.all(),
        'nav_brands': Brand.objects.all(),
    }