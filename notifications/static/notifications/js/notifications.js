document.addEventListener('DOMContentLoaded', function () {
    var toggle = document.getElementById('notifBellToggle');
    if (!toggle) return; // not a staff user — bell isn't rendered

    var list = document.getElementById('notifDropdownList');
    var markAllBtn = document.getElementById('notifMarkAllBtn');
    var badge = document.querySelector('.notif-bell-badge');

    function csrfToken() {
        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : '';
    }

    function renderNotifications(data) {
        if (!data.notifications.length) {
            list.innerHTML = '<div class="notif-empty">No notifications yet.</div>';
            return;
        }
        list.innerHTML = data.notifications.map(function (n) {
            return (
                '<a href="/notifications/' + n.id + '/open/" class="notif-item' + (n.is_read ? '' : ' notif-item-unread') + '">' +
                    '<span class="notif-item-icon">' + n.icon + '</span>' +
                    '<span class="notif-item-body">' +
                        '<span class="notif-item-title">' + n.title + '</span>' +
                        '<span class="notif-item-message">' + n.message + '</span>' +
                        '<span class="notif-item-time">' + n.time_ago + '</span>' +
                    '</span>' +
                '</a>'
            );
        }).join('');
    }

    function updateBadge(count) {
        if (!badge) return;
        badge.textContent = count;
        badge.style.display = count > 0 ? '' : 'none';
    }

    function loadDropdown() {
        fetch('/notifications/dropdown/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                renderNotifications(data);
                updateBadge(data.unread_count);
            });
    }

    toggle.addEventListener('click', loadDropdown);

    if (markAllBtn) {
        markAllBtn.addEventListener('click', function (e) {
            e.preventDefault();
            fetch('/notifications/mark-all-read/', {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken(),
                },
            }).then(loadDropdown);
        });
    }

    // Keeps the badge count fresh without a full page reload.
    setInterval(function () {
        fetch('/notifications/dropdown/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { return r.json(); })
            .then(function (data) { updateBadge(data.unread_count); });
    }, 60000);
});