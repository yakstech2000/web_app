"""
Django settings for web_app project.
"""

from pathlib import Path
from decouple import config, Csv
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
# Set SECRET_KEY as an environment variable on Railway — never hardcode it.
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
# Set DEBUG=False as an environment variable on Railway.
# Locally, if you don't set DEBUG at all, it defaults to True.
DEBUG = config('DEBUG', default=True, cast=bool)

# Comma-separated list of allowed hosts, e.g.:
# ALLOWED_HOSTS=yourapp.up.railway.app,www.yourdomain.com
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv())

# Required by Django 4+ when serving over HTTPS behind a different domain —
# without this, POST requests (including admin logins/edits) will fail CSRF
# checks in production even with a valid token. Same comma-separated format,
# but each entry needs the scheme, e.g.:
# CSRF_TRUSTED_ORIGINS=https://yourapp.up.railway.app
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary_storage',
    'cloudinary',
    'django.contrib.humanize',
    'anymail',
    'product',
    'cart',
    'orders',
    'home',
    'account',
    'product_reviews',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # serves static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'web_app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates'
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'orders.context_processors.admin_dashboard_stats',
            ],
        },
    },
]

WSGI_APPLICATION = 'web_app.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases
#
# Locally (no DATABASE_URL set), falls back to sqlite3 as before.
# On Railway, set DATABASE_URL to the value Railway's Postgres plugin
# provides (Railway usually injects this automatically once you add the
# Postgres plugin to your project — check the Variables tab).

DATABASES = {
    'default': config(
        'DATABASE_URL',
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        cast=dj_database_url.parse,
    )
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Lagos'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static'
]

STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (product images, category images, payment receipts) are
# stored on Cloudinary rather than the local filesystem — Railway's disk
# is ephemeral, so anything saved locally would be wiped on every redeploy.
# Static files (CSS/JS/admin assets) still go through whitenoise as before;
# only MEDIA storage is routed to Cloudinary.
#
# NOTE: using the plain default StaticFilesStorage (no whitenoise storage
# class, no compression, no manifest hashing) here. Both
# CompressedManifestStaticFilesStorage and CompressedStaticFilesStorage
# were crashing collectstatic in production with intermittent
# FileNotFoundErrors during whitenoise's parallel (ThreadPoolExecutor)
# compression step — a known flakiness with that step in some container
# environments, hitting a different vendored admin asset file each run.
# WhiteNoiseMiddleware still serves static files directly and
# efficiently without any special storage backend or pre-compression —
# it simply reads files off STATIC_ROOT at request time.
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Some packages (e.g. django-cloudinary-storage's collectstatic override)
# still check the legacy STATICFILES_STORAGE setting name rather than the
# newer STORAGES dict. Keeping this defined avoids an AttributeError from
# those packages. Must match the "staticfiles" backend above.
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': config('CLOUDINARY_API_KEY'),
    'API_SECRET': config('CLOUDINARY_API_SECRET'),
}

MEDIA_URL = 'media/'
# MEDIA_ROOT is no longer used for storage (Cloudinary handles that), but
# some code/forms may still reference it, so it's left defined harmlessly.
MEDIA_ROOT = BASE_DIR / 'media'

# Email Configuration — via Resend HTTP API (Railway blocks outbound SMTP,
# so raw smtplib connections fail with "Network is unreachable" — this
# sends over HTTPS instead, which isn't blocked)
EMAIL_BACKEND = 'anymail.backends.resend.EmailBackend'

ANYMAIL = {
    'RESEND_API_KEY': config('RESEND_API_KEY', default=''),
}

DEFAULT_FROM_EMAIL = 'onboarding@resend.dev'  # switch to your own verified domain later

# Used to build absolute links (e.g. "View My Orders" buttons) inside
# order-status emails, which don't have access to an HttpRequest to call
# request.build_absolute_uri() the way account/emails.py does. Set this on
# Railway to your real deployed URL, e.g.:
# SITE_URL=https://drapple-production.up.railway.app
# and update it again once you're on a real domain.
SITE_URL = config('SITE_URL', default='http://127.0.0.1:8000')

# Security settings — Secure cookies only make sense over HTTPS. Forcing
# them on during local development (DEBUG=True, plain http://127.0.0.1)
# silently breaks login/CSRF locally, since browsers refuse to store
# Secure-flagged cookies over a non-HTTPS connection. Tying these to
# `not DEBUG` keeps production secure while keeping local dev working.
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 1800  # 30 minutes

CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Strict'

LOGIN_URL = 'account:login'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}