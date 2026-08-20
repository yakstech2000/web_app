from django import template

register = template.Library()

# admin_url substring → section key. Keep this in sync with
# notifications/badges.py's SECTION_BY_TYPE and admin_badges.js's
# sectionLinks — three places check the same mapping because Django
# templates, Python, and the stock-sidebar JS each need their own way of
# reading it, but they should never drift apart.
_URL_SECTION_MAP = [
    ('/orders/pickuporder/', 'pickup_orders'),
    ('/orders/deliveryorder/', 'delivery_orders'),
    ('/product_reviews/productreview/', 'reviews'),
    ('/auth/user/', 'customers'),
    ('/product/product/', 'products'),
]


@register.simple_tag
def unread_badge_for(admin_url, section_unread_counts):
    """
    {% unread_badge_for model.admin_url section_unread_counts as count %}
    Returns the unread count for whichever section this model's admin_url
    belongs to, or 0 if it doesn't match any tracked section.
    """
    if not admin_url or not section_unread_counts:
        return 0
    for substring, section in _URL_SECTION_MAP:
        if substring in admin_url:
            return section_unread_counts.get(section, 0)
    return 0