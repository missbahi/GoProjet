"""
Django settings for goProjet project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# --- 1. CHARGEMENT DES VARIABLES D'ENVIRONNEMENT ---
load_dotenv()  # Charge les variables depuis .env

# --- 2. CHEMINS DE BASE ---
BASE_DIR = Path(__file__).resolve().parent.parent

# --- 3. SÉCURITÉ ET ENVIRONNEMENT ---
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-local-only')

# 🔧 CORRECTION : DEBUG basé sur l'environnement
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

# 🔧 CORRECTION : Configuration ALLOWED_HOSTS améliorée
if DEBUG:
    # Hosts pour le développement
    ALLOWED_HOSTS = [
        'localhost', 
        '127.0.0.1', 
        '0.0.0.0',
        'localhost:8000',
        '127.0.0.1:8000',
    ]
    print("🚀 Mode DEBUG activé - Développement local")
else:
    # Hosts pour la production
    ALLOWED_HOSTS = [
        'goprojet-production.up.railway.app',
        '.railway.app',
        '.up.railway.app',
        '127.0.0.1',
        'localhost'
    ]
    print("🌐 Mode PRODUCTION - Hosts configurés pour Railway")

# --- 4. APPLICATIONS ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Cloudinary - TOUJOURS ajoutées
    'cloudinary_storage',
    'cloudinary',
    
    # Vos applications
    'projets.apps.ProjetsConfig',
]

# --- 5. MIDDLEWARE ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'projets.middleware.admin_redirect.AdminRedirectMiddleware',
]

# Configuration d'authentification
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

# URLs publiques
PUBLIC_URLS = [
    '/', 
    '/apropos/',
    '/accounts/login/',
    '/accounts/password_reset/',
    '/accounts/password_reset/done/',
    '/accounts/reset/', 
    '/accounts/reset/done/',
    '/static/',
    '/media/',
]

# --- 6. URLS & TEMPLATES ---
ROOT_URLCONF = 'goProjet.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',  # 🔧 AJOUT IMPORTANT
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'goProjet.wsgi.application'

# --- 7. DATABASE ---
# 🔧 CORRECTION : Configuration base de données pour Railway
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

if DATABASE_URL:
    # Utiliser PostgreSQL sur Railway
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
    print("🗄️  Base de données PostgreSQL configurée")
else:
    # SQLite en développement
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    print("🗄️  Base de données SQLite configurée")

# --- 8. VALIDATION DES MOTS DE PASSE ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# --- 9. INTERNATIONALISATION ---
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Europe/Paris'
USE_I18N = True
USE_TZ = True

# --- 10. FICHIERS STATIQUES ---
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'goProjet' / 'static',
]

# Whitenoise pour les statiques
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- 11. FICHIERS MÉDIA ---
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- 12. CONFIGURATION CLOUDINARY ---
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')

USE_CLOUDINARY = all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET])

if USE_CLOUDINARY:
    print("☁️  Mode Cloudinary activé pour le stockage des fichiers")
    
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': CLOUDINARY_CLOUD_NAME,
        'API_KEY': CLOUDINARY_API_KEY,
        'API_SECRET': CLOUDINARY_API_SECRET,
        'SECURE': True,
        'STATIC_IMAGES': False,
        'STATIC_FILE_SUPPORT': True,
    }
    
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    
else:
    print("💻 Mode local activé - Stockage des fichiers sur le disque dur")
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    MEDIA_ROOT.mkdir(exist_ok=True)

# --- 13. SÉCURITÉ ---
# 🔧 CORRECTION : Sécurité basée sur l'environnement
if not DEBUG:
    # En production
    SECURE_SSL_REDIRECT = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    
    # CSRF trusted origins pour Railway
    CSRF_TRUSTED_ORIGINS = [
        'https://goprojet-production.up.railway.app',
        'https://*.railway.app',
        'https://*.up.railway.app',
    ]
    print("🔒 Sécurité renforcée activée (Production)")
else:
    # En développement
    SECURE_SSL_REDIRECT = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'http://0.0.0.0:8000',
    ]
    print("🔓 Mode développement - Sécurité réduite")

# --- 14. EMAIL ---
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    # Configurer les paramètres SMTP pour la production

# --- 15. CONFIGURATIONS DIVERSES ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- 16. LOGGING ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'cloudinary': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'projets': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# 🔧 CORRECTION : Affichage des informations de configuration
# print(f"📋 DEBUG: {DEBUG}")
# print(f"🌐 ALLOWED_HOSTS: {ALLOWED_HOSTS}")
# print(f"🔑 USE_CLOUDINARY: {USE_CLOUDINARY}")