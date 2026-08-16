from django.urls import path

from . import views

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('order/<int:order_id>/review/', views.order_review, name='order_review'),
    path('order/<int:order_id>/process-payment/', views.process_payment, name='process_payment'),
    path('order/<int:order_id>/confirm-payment/', views.payment_confirmation, name='payment_confirmation'),
    path('order/<int:order_id>/receipt-success/', views.receipt_upload_success, name='receipt_upload_success'),
    path('my-orders/', views.order_history, name='order_history'),
    path('order/<int:order_id>/detail/', views.order_detail, name='order_detail'),
    path('order/<int:order_id>/confirm-received/', views.confirm_order_received, name='confirm_order_received'),
    path('order/<int:order_id>/create-account/', views.create_account, name='create_account'),
    path('buy-now/<int:product_id>/', views.buy_now, name='buy_now'),

]
