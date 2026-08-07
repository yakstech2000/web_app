from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('api/reviews/', views.get_featured_reviews, name='get_featured_reviews'),
    path('api/product/<int:product_id>/reviews/', views.get_product_reviews, name='get_product_reviews'),

]