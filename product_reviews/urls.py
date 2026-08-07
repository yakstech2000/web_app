from django.urls import path
from . import views

urlpatterns = [
    path('write/<int:order_id>/<int:product_id>/', views.review_form, name='write_review'),
    path('submit/<int:order_id>/<int:product_id>/', views.submit_review, name='submit_review'),
    path('my_review/', views.my_reviews, name='my_reviews'),
    path('<int:review_id>/edit/', views.edit_review, name='edit_review'),
    path('<int:review_id>/delete/', views.delete_review, name='delete_review'),
]