from django.urls import path

from . import views

urlpatterns = [
    path('add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('', views.cart_detail, name='cart_detail'),
    path('update/<int:item_id>/', views.cart_update, name='cart_update'),
    path('remove/<int:item_id>/', views.cart_remove, name='cart_remove'),
]
