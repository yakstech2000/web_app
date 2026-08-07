"""
Accounts App URLs - Complete Authentication Routes
13 URL patterns for all account management functionality
"""

from django.urls import path
from . import views

app_name = 'account'

urlpatterns = [
    # ===== Authentication Routes =====
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # ===== Email Verification Routes =====
    path('verify-email/<uidb64>/<token>/', views.verify_email, name='verify-email'),
    path('verification-pending/', views.verification_pending, name='verification-pending'),
    path('resend-verification/', views.resend_verification, name='resend-verification'),

    # ===== Password Reset Routes =====
    path('password-reset/', views.password_reset, name='password-reset'),
    path('password-reset-confirm/<uidb64>/<token>/', views.password_reset_confirm, name='reset-password-confirm'),

    # ===== Account Management Routes =====
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('password/change/', views.change_password, name='change_password'),
    path('account/delete/', views.delete_account, name='delete_account'),

    # ===== Security & Activity Routes =====
    path('security-log/', views.security_log, name='security_log'),
    path('activity-history/', views.activity_history, name='activity_history'),
]
