document.addEventListener('DOMContentLoaded', function () {
    var wrap = document.getElementById('drNotifBellWrap');
    var btn = document.getElementById('drNotifBellBtn');
    var dropdown = document.getElementById('drNotifDropdown');
    if (!wrap || !btn || !dropdown) {
        return;
    }

    function closeDropdown() {
        dropdown.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
    }

    function toggleDropdown() {
        var isOpen = !dropdown.hidden;
        if (isOpen) {
            closeDropdown();
        } else {
            dropdown.hidden = false;
            btn.setAttribute('aria-expanded', 'true');
        }
    }

    btn.addEventListener('click', function (e) {
        e.stopPropagation();
        toggleDropdown();
    });

    // Click outside the bell/dropdown closes it.
    document.addEventListener('click', function (e) {
        if (!wrap.contains(e.target)) {
            closeDropdown();
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeDropdown();
        }
    });
});
