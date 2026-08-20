from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Notification


def _is_staff(user):
    return user.is_authenticated and user.is_staff


def _time_ago(dt):
    seconds = (timezone.now() - dt).total_seconds()
    if seconds < 60:
        return 'Just now'
    if seconds < 3600:
        mins = int(seconds // 60)
        return f'{mins} minute{"s" if mins != 1 else ""} ago'
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    if seconds < 172800:
        return 'Yesterday'
    return dt.strftime('%b %d, %Y')


@user_passes_test(_is_staff, login_url='account:login')
def notification_list(request):
    """Full notification page — /notifications/ — staff only."""
    filter_type = request.GET.get('filter', 'all')  # 'all' or 'unread'
    qs = Notification.objects.filter(recipient=request.user).select_related('content_type')

    if filter_type == 'unread':
        qs = qs.filter(is_read=False)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'filter_type': filter_type,
        'unread_count': Notification.objects.filter(recipient=request.user, is_read=False).count(),
    }
    return render(request, 'notifications/notification_list.html', context)


@user_passes_test(_is_staff, login_url='account:login')
def notification_open(request, notification_id):
    """Mark one notification read, then send the admin to whatever it's about."""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    if notification.link:
        return redirect(notification.link)
    return redirect('notifications:list')


@user_passes_test(_is_staff, login_url='account:login')
@require_POST
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect('notifications:list')


@user_passes_test(_is_staff, login_url='account:login')
@require_POST
def notification_delete(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect('notifications:list')


@user_passes_test(_is_staff, login_url='account:login')
def notification_dropdown_partial(request):
    """
    JSON endpoint the bell polls — recent notifications + unread count,
    used to populate/refresh the dropdown without a full page reload.
    """
    recent = Notification.objects.filter(recipient=request.user)[:8]
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    data = {
        'unread_count': unread_count,
        'notifications': [
            {
                'id': n.id,
                'icon': n.icon,
                'title': n.title,
                'message': n.message,
                'link': n.link or '',
                'is_read': n.is_read,
                'time_ago': _time_ago(n.created_at),
            }
            for n in recent
        ],
    }
    return JsonResponse(data)