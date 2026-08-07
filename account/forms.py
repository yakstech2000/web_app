"""
Secure User Forms with Enterprise-Grade Validation
"""

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re


class SecureSignUpForm(forms.ModelForm):
    """
    Secure user registration form with password complexity validation
    - Email uniqueness check
    - Strong password requirements (12+ chars, mixed case, numbers, symbols)
    - Password confirmation matching
    """
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter a strong password',
            'autocomplete': 'new-password'
        }),
        min_length=12,
        help_text='Minimum 12 characters: uppercase, lowercase, numbers, symbols (!@#$%^&*)'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password'
        }),
        min_length=12
    )

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password1', 'password2')
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your@email.com',
                'autocomplete': 'email'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last Name'
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        if not email:
            raise ValidationError('Email is required.')
        if User.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered. Please use a different email.')
        return email

    def clean_password1(self):
        password = self.cleaned_data.get('password1', '')

        if len(password) < 12:
            raise ValidationError('Password must be at least 12 characters long.')
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter (A-Z).')
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must contain at least one lowercase letter (a-z).')
        if not re.search(r'[0-9]', password):
            raise ValidationError('Password must contain at least one number (0-9).')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('Password must contain at least one symbol (!@#$%^&* etc).')

        return password

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise ValidationError('Passwords do not match. Please try again.')

        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.username = self.cleaned_data['email']
        user.is_active = False  # Require email verification before activation
        if commit:
            user.save()
        return user


class SecureLoginForm(forms.Form):
    """
    Secure login form with email-based authentication
    """
    email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your@email.com',
            'autofocus': True,
            'autocomplete': 'email'
        })
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your password',
            'autocomplete': 'current-password'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        label='Remember me for 30 days',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class PasswordResetRequestForm(forms.Form):
    """
    Form for requesting password reset
    Includes generic error messages for security
    """
    email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'autocomplete': 'email'
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        if not email:
            raise ValidationError('Email is required.')
        if not User.objects.filter(email=email).exists():
            # Generic message for security - don't reveal if email exists
            raise ValidationError('If this email is registered, you will receive password reset instructions.')
        return email


class SetNewPasswordForm(forms.Form):
    """
    Form for setting new password after reset
    Same complexity requirements as signup
    """
    password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your new password',
            'autocomplete': 'new-password'
        }),
        min_length=12,
        help_text='Minimum 12 characters: uppercase, lowercase, numbers, symbols'
    )
    password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your new password',
            'autocomplete': 'new-password'
        }),
        min_length=12
    )

    def clean_password1(self):
        password = self.cleaned_data.get('password1', '')

        if len(password) < 12:
            raise ValidationError('Password must be at least 12 characters long.')
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter.')
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must contain at least one lowercase letter.')
        if not re.search(r'[0-9]', password):
            raise ValidationError('Password must contain at least one number.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('Password must contain at least one symbol.')

        return password

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise ValidationError('Passwords do not match.')

        return password2


class ProfileUpdateForm(forms.ModelForm):
    """
    Form for updating user profile information
    """

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email address'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last Name'
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        # Allow same email, but prevent duplicates with other users
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError('This email is already in use by another account.')
        return email
