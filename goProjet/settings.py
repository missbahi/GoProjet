"""
Django settings for goProjet project.
"""

import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv  # Nouveau


# --- 1. CHEMINS DE BASE ---
BASE_DIR = Path(__file__).resolve().parent.parent

# --- 2. CHARGEMENT DES VARIABLES D'ENVIRONNEMENT ---

# 2.1. D'ABORD .env.local (développement local) - PRIORITAIRE
env_local = BASE_DIR / '.env.local'

if env_local.exists():
    load_dotenv(env_local, override=True)  # override=True pour écraser
    print(f"✅ .env.local chargé: {env_local}")

# 2.2. ENSUITE .env (si existe, pour compatibilité)
env_file = BASE_DIR / '.env'
if env_file.exists():
    load_dotenv(env_file, override=False)  # override=False: .env.local reste prioritaire
    print(f"📄 .env chargé: {env_file}")


# --- 3. SÉCURITÉ ET ENVIRONNEMENT ---
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-local-only')

DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

if DEBUG:
    # Hosts pour le développement
    ALLOWED_HOSTS = [
        'localhost', 
        '127.0.0.1', 
        '0.0.0.0',
        'localhost:8000',
        '127.0.0.1:8000',
    ]
    print("Mode DEBUG activé - Développement local")
else:
    # Hosts pour la production
    ALLOWED_HOSTS = [
        'goprojet.onrender.com',
        '.onrender.com',
        'goprojet-production.up.railway.app',
        '.railway.app',
        '.up.railway.app',
        '127.0.0.1',
        'localhost'
    ]
    print("Mode PRODUCTION - Hosts configurés pour Railway")

# --- 4. APPLICATIONS ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
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
    # Optionnel: middleware pour détecter les visites PWA
    'projets.middleware.pwa_injector.PWAInjectorMiddleware',
]

# Configuration d'authentification
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'projets:landing'
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

if os.environ.get('DATABASE_URL') and not DEBUG:
    # PRODUCTION : PostgreSQL Railway
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True
        )
    }
    print("⚡ Mode production: PostgreSQL Railway")
else:
    # DÉVELOPPEMENT LOCAL : SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    print("💻 Mode développement: SQLite local")
    

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

# --- 11.b STOCKAGE DOCUMENTS R2 (V2) ---
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID') or os.environ.get('AWS_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')
R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME') or os.environ.get('AWS_STORAGE_BUCKET_NAME')
R2_REGION = os.environ.get('R2_REGION', 'auto')
R2_ENDPOINT_URL = os.environ.get('R2_ENDPOINT_URL') or os.environ.get('AWS_S3_ENDPOINT_URL')
USE_R2_DOCUMENTS = os.environ.get('USE_R2_DOCUMENTS', 'true').lower() == 'true'

# --- 12. CONFIGURATION PWA ---
PWA_CONFIG = {
    'ENABLED': os.environ.get('PWA_ENABLED', 'True').lower() == 'true',
    'DEBUG': DEBUG,  # Suit le mode DEBUG de Django
}

if PWA_CONFIG['ENABLED']:
    print("✅ PWA activée")
    
    # Configuration PWA
    PWA_APP_NAME = 'goProjet'
    PWA_APP_DESCRIPTION = 'Gestion de projets collaboratifs'
    PWA_APP_THEME_COLOR = '#0A0302'
    PWA_APP_BACKGROUND_COLOR = '#ffffff'
    PWA_APP_DISPLAY = 'standalone'
    PWA_APP_SCOPE = '/'
    PWA_APP_ORIENTATION = 'any'
    PWA_APP_START_URL = '/'
    PWA_APP_STATUS_BAR_COLOR = 'default'
    PWA_APP_DEBUG_MODE = DEBUG  # Debug en fonction du mode Django
    
    # Icons - Vous devez créer ces fichiers dans static/icons/
    PWA_APP_ICONS = [
        {
            'src': '/static/icons/icon-192x192.png',
            'sizes': '192x192',
            'type': 'image/png',
            'purpose': 'any maskable'  # Important pour PWA
        },
        {
            'src': '/static/icons/icon-512x512.png', 
            'sizes': '512x512',
            'type': 'image/png',
            'purpose': 'any maskable'
        }
    ]
    PWA_SETTINGS = {
        'name': PWA_APP_NAME,
        'short_name': PWA_APP_NAME,
        'description': PWA_APP_DESCRIPTION,
        'theme_color': PWA_APP_THEME_COLOR,
        'background_color': PWA_APP_BACKGROUND_COLOR,
        'display': PWA_APP_DISPLAY,
        'scope': PWA_APP_SCOPE,
        'orientation': PWA_APP_ORIENTATION,
        'start_url': PWA_APP_START_URL,
        'icons': PWA_APP_ICONS,
    }
    # Splash screens optionnels
    PWA_APP_SPLASH_SCREEN = [
        {
            'src': '/static/icons/splash-640x1136.png',
            'media': '(device-width: 320px) and (device-height: 568px) and (-webkit-device-pixel-ratio: 2)'
        }
    ]
    
    # Fichiers à mettre en cache hors ligne
    PWA_APP_FILES_OFFLINE = [
        '/static/projets/css/style.css',
        '/static/projets/js/main.js',
        '/static/icons/icon-192x192.png',
    ]
    
    # Service Worker personnalisé
    PWA_SERVICE_WORKER_PATH = os.path.join(BASE_DIR, 'goProjet', 'static', 'projets', 'js', 'serviceworker.js')
    
    # URLs supplémentaires pour PWA
    PWA_APP_OFFLINE_URL = '/offline/'
    
else:
    print("ℹ️ PWA désactivée")
    
# --- 13. CONFIGURATION DU STOCKAGE ---

DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
MEDIA_ROOT.mkdir(exist_ok=True)

# Priorité V2: si R2 est activé et correctement configuré,
# on force le backend par défaut pour les FileField documents.
R2_IS_CONFIGURED = all([
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME,
    R2_ENDPOINT_URL,
])

if USE_R2_DOCUMENTS and R2_IS_CONFIGURED:
    AWS_ACCESS_KEY_ID = R2_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = R2_SECRET_ACCESS_KEY
    AWS_STORAGE_BUCKET_NAME = R2_BUCKET_NAME
    AWS_S3_REGION_NAME = R2_REGION
    AWS_S3_ENDPOINT_URL = R2_ENDPOINT_URL
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_S3_ADDRESSING_STYLE = 'virtual'

    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3.S3Storage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
    print("✅ Stockage R2 activé pour les documents FileField")
elif USE_R2_DOCUMENTS:
    print("⚠️ USE_R2_DOCUMENTS=true mais configuration R2 incomplète: fallback stockage existant")
    
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
    # Pour PWA en HTTPS
    'https://localhost:8000',
    'https://127.0.0.1:8000',
]

# Autres paramètres CSRF
CSRF_USE_SESSIONS = False
CSRF_COOKIE_HTTPONLY = False

# --- 14. EMAIL (CONSOLE EN LOCAL) ---
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# --- 15. CONFIGURATIONS DIVERSES ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- 16. LOGGING ---
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
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

