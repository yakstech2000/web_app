from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('<int:notification_id>/open/', views.notification_open, name='open'),
    path('<int:notification_id>/delete/', views.notification_delete, name='delete'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('dropdown/', views.notification_dropdown_partial, name='dropdown'),
]