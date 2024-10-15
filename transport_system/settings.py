"""
Django settings for transport_system project.

Generated by 'django-admin startproject' using Django 5.1.1.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""
import os
import environ
from pathlib import Path
from datetime import timedelta
import sys
from datetime import timedelta


if 'test' in sys.argv:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
# Initialise environ
env = environ.Env(
    # Définit les valeurs par défaut si elles ne sont pas présentes dans le fichier .env
    DEBUG=(bool, False)
)

# Lis les variables d'environnement depuis le fichier .env
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-twa6)y+5vhwmmm!$36l)yrl!2iun*z+72b_i+b3_oc1jp)d=!w"

# DEBUG
DEBUG = env('DEBUG')

# ALLOWED_HOSTS
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# OpenAI API configuration
OPENAI_API_KEY = env('OPENAI_API_KEY')

# Stripe API configuration
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = env('STRIPE_PUBLISHABLE_KEY')

# Twilio API configuration
TWILIO_ACCOUNT_SID = env('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = env('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = env('TWILIO_PHONE_NUMBER')

# WhatsApp Business API configuration
WHATSAPP_API_URL = env('WHATSAPP_API_URL')
WHATSAPP_PHONE_NUMBER = env('WHATSAPP_PHONE_NUMBER')
WHATSAPP_TOKEN = env('WHATSAPP_TOKEN')

# Trillo API configuration
TRILLO_API_KEY = env('TRILLO_API_KEY')


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "financial_management",
    "inventory_management",
    "transport_management",
    "security_management",
    "user_management",
    "membership_management",
    "rest_framework",
    "corsheaders",
    "rest_framework_simplejwt.token_blacklist",
    "django_celery_beat",
     
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
]

# Configuration de Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}
ROOT_URLCONF = "transport_system.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "transport_system.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

# Database configuration
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT', default='3306'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

# Paramètres pour les fichiers statiques
STATIC_URL = env('STATIC_URL')
STATICFILES_DIRS = [os.path.join(BASE_DIR, env('STATICFILES_DIR'))]
STATIC_ROOT = os.path.join(BASE_DIR, env('STATIC_ROOT'))

# Paramètres pour les fichiers médias (téléversés par les utilisateurs)
MEDIA_URL = env('MEDIA_URL')
MEDIA_ROOT = os.path.join(BASE_DIR, env('MEDIA_ROOT'))

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Configuration de CORS
CORS_ALLOW_ALL_ORIGINS = env.bool('CORS_ALLOW_ALL_ORIGINS', default=False)  # Par défaut, False pour la sécurité

# Configuration de Celery
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST')
EMAIL_PORT = env.int('EMAIL_PORT')
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS')

# Timezone
TIME_ZONE = env('TIME_ZONE')
 

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
}

AUTH_USER_MODEL = 'user_management.User'

CELERY_BEAT_SCHEDULE = {
    'check-upcoming-trips': {
        'task': 'transport_system.tasks.check_upcoming_trips',
        'schedule': 3600.0,  # Toutes les heures
    },
    'process-notifications': {
        'task': 'transport_system.tasks.process_notifications',
        'schedule': 300.0,  # Toutes les 5 minutes
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),  # Durée du token d'accès
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),  # Durée du token de rafraîchissement
    'ROTATE_REFRESH_TOKENS': True,  # Génére un nouveau refresh token à chaque rafraîchissement
    'BLACKLIST_AFTER_ROTATION': True,  # Liste noire après rotation pour plus de sécurité
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# settings.py
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# settings.py
if 'test' in sys.argv:
    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    
#MYSQL_PASSWORD = env('MYSQL_PASSWORD', default='')
