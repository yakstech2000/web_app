document.addEventListener('DOMContentLoaded', function () {
    var dataEl = document.getElementById('admin-badge-data');
    if (!dataEl) return;

    var counts;
    try {
        counts = JSON.parse(dataEl.textContent);
    } catch (e) {
        return;
    }

    // Maps each section's count to the admin changelist link(s) it
    // decorates. UPDATE THESE PATHS if your app_label/model registration
    // differs — these match this project's orders/admin.py exactly
    // (DeliveryOrder + PickupOrder proxy models), but Product/ProductReview
    // paths assume Django's default app_label/model_name URL pattern.
    //
    // "payments" has no dedicated admin section in this project (payment
    // status lives on Order itself, not a separate Payment model) — its
    // count is still computed correctly and available in the bell/
    // notifications page, it's just not attached to a sidebar link here
    // since there's nowhere honest to put it. Add an entry below if you
    // create a dedicated payments view later.
    var sectionLinks = {
        pickup_orders: ['/admin/orders/pickuporder/'],
        delivery_orders: ['/admin/orders/deliveryorder/'],
        reviews: ['/admin/product_reviews/productreview/'],
        customers: ['/admin/auth/user/'],
        products: ['/admin/product/product/'],
    };

    Object.keys(sectionLinks).forEach(function (section) {
        var count = counts[section];
        if (!count) return;
        sectionLinks[section].forEach(function (href) {
            var link = document.querySelector('#nav-sidebar a[href="' + href + '"]');
            if (!link || link.querySelector('.admin-unread-badge')) return;
            var badge = document.createElement('span');
            badge.className = 'admin-unread-badge';
            badge.textContent = count;
            link.appendChild(badge);
        });
    });
});