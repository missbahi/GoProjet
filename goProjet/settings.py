"""
Django settings for goProjet project.
"""

import os
from pathlib import Path
import re
import dj_database_url
from dotenv import load_dotenv  # Nouveau

# --- 1. CHARGEMENT DES VARIABLES D'ENVIRONNEMENT ---
load_dotenv()  # Charge les variables depuis .env

# --- 2. CHEMINS DE BASE ---
BASE_DIR = Path(__file__).resolve().parent.parent

# --- 3. SÉCURITÉ ET ENVIRONNEMENT ---
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-local-only')

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
LOGOUT_REDIRECT_URL = 'projets:apropos'

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
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'goProjet.wsgi.application'

# --- 7. DATABASE ---
# PostgreSQL pour Railway
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=True
    )
}

# Option: Pour garder SQLite en développement local
if 'DATABASE_URL' not in os.environ:
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
    print("⚠️  Mode développement: SQLite utilisé")
else:
    print("✅ Mode production: PostgreSQL utilisé")
    
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# --- 8. VALIDATION DES MOTS DE PASSE ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    # {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    # {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
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

def sanitize_cloudinary_credential(value):
    """
    Nettoie une credential Cloudinary.
    Supprime les espaces, signes =, guillemets au début.
    """
    if value is None:
        return ""
    
    value = str(value)
    
    # Étape 1: Supprimer les espaces
    value = value.strip()
    
    # Étape 2: Supprimer les guillemets
    value = value.strip('"\'')
    
    # Étape 3: Supprimer tout caractère non alphanumérique au début
    # Cela supprime =, espaces, etc.
    value = re.sub(r'^[^a-zA-Z0-9]+', '', value)
    
    return value
# Récupération des credentials Cloudinary
CLOUDINARY_CLOUD_NAME = sanitize_cloudinary_credential(os.environ.get('CLOUDINARY_CLOUD_NAME'))
CLOUDINARY_API_KEY = sanitize_cloudinary_credential(os.environ.get('CLOUDINARY_API_KEY'))
CLOUDINARY_API_SECRET = sanitize_cloudinary_credential(os.environ.get('CLOUDINARY_API_SECRET'))
# Vérification si Cloudinary est configuré
USE_CLOUDINARY = all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET])

if USE_CLOUDINARY:
    print("☁️  Mode Cloudinary activé pour le stockage des fichiers")
    
    # Configuration Cloudinary
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': CLOUDINARY_CLOUD_NAME,
        'API_KEY': CLOUDINARY_API_KEY,
        'API_SECRET': CLOUDINARY_API_SECRET,
        'SECURE': True,
        'STATIC_IMAGES': False,  # Important pour les fichiers non-images
        'STATIC_FILE_SUPPORT': True,  # Important pour les documents
    }
    print('cloudinary name :', CLOUDINARY_STORAGE['CLOUD_NAME'])
    # Stockage par défaut Cloudinary
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    
    # Configuration supplémentaire pour les fichiers raw (documents)
    CLOUDINARY = {
        'cloud_name': CLOUDINARY_CLOUD_NAME,
        'api_key': CLOUDINARY_API_KEY,
        'api_secret': CLOUDINARY_API_SECRET,
        'secure': True
    }
    
else:
    print("💻 Mode local activé - Stockage des fichiers sur le disque dur")
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    
    # Créer le dossier media s'il n'existe pas
    MEDIA_ROOT.mkdir(exist_ok=True)
SECURE_SSL_REDIRECT = False

# IMPORTANT: Railway fournit SSL, donc nous devons dire à Django qu'il est derrière un proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Cookies sécurisés - IMPORTANT: True en production
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# CSRF trusted origins - AJOUTER LES URLS HTTPS DE RAILWAY
CSRF_TRUSTED_ORIGINS = [
    'https://goprojet-production.up.railway.app',
    'https://*.railway.app', 
    'https://*.up.railway.app',
    # URLs de développement (HTTP)
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://0.0.0.0:8000',
]

# Autres paramètres CSRF
CSRF_USE_SESSIONS = False
CSRF_COOKIE_HTTPONLY = False

# --- 14. EMAIL (CONSOLE EN LOCAL) ---
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# --- 15. CONFIGURATIONS DIVERSES ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- 16. LOGGING POUR LE DÉBOGAGE CLOUDINARY ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'cloudinary': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

