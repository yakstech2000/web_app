from django.urls import path
from . import views

urlpatterns = [
    # Product URLs
    path('base/', views.base, name='base'),
    path('products/', views.product_list, name='product_list'),
    path('products/<int:product_id>/', views.product_detail, name='product_detail'),

]