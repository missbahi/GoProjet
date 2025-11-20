"""
Django settings for goProjet project.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-local-only')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,.localhost').split(',')

# APPLICATIONS DE BASE
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'projets',
    'projets.templatetags'
]

# CONFIGURATION CLOUDINARY SIMPLIFIÉE
if os.environ.get('CLOUDINARY_CLOUD_NAME'):
    print("☁️  Cloudinary activé")
    try:
        INSTALLED_APPS = ['cloudinary_storage', 'cloudinary'] + INSTALLED_APPS
        
        CLOUDINARY_STORAGE = {
            'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
            'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
            'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
            'SECURE': True,
        }
        
        DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
        
    except ImportError as e:
        print(f"❌ Erreur import Cloudinary: {e}")
        # Fallback vers le stockage local
        DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
else:
    print("💻 Mode local")
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# MIDDLEWARE
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'projets.middleware.auth_required.AuthRequiredMiddleware',  
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
LOGIN_URL = '/admin/login/'  # Utilise l'interface d'admin Django
LOGIN_REDIRECT_URL = '/'     # Après connexion
LOGOUT_REDIRECT_URL = '/admin/login/'  # Après déconnexion
# SÉCURITÉ AUTHENTIFICATION
SESSION_COOKIE_AGE = 1209600  # 2 semaines en secondes
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Garder la session
# URLS & TEMPLATES
ROOT_URLCONF = 'goProjet.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'goProjet.wsgi.application'

# DATABASE
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# PASSWORD VALIDATION
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# INTERNATIONALIZATION
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# STATIC FILES
STATIC_URL = '/static/'
if DEBUG:
    STATICFILES_DIRS = [os.path.join(BASE_DIR, 'projets/static')]
else:
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# MEDIA FILES
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# DEFAULT AUTO FIELD
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# SECURITY FOR RAILWAY
# SECURITY SETTINGS - ONLY IN PRODUCTION
if not DEBUG:
    # ✅ Ces settings seulement en PRODUCTION
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    
    CSRF_TRUSTED_ORIGINS = [
        'https://goprojet-production.up.railway.app',
        'https://*.railway.app',
    ]
else:
    # ✅ En développement local - HTTP autorisé
    SECURE_SSL_REDIRECT = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False