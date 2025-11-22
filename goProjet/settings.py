"""
Django settings for goProjet project.
"""

import os
from pathlib import Path

# --- 1. CHEMINS DE BASE ---
# La définition de BASE_DIR est correcte et utilise pathlib
BASE_DIR = Path(__file__).resolve().parent.parent
print(f"DEBUG - BASE_DIR (Racine du Projet) : {BASE_DIR}")
# --- 2. SÉCURITÉ ET ENVIRONNEMENT ---
# Récupération de la clé secrète
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-local-only')

# Gestion du mode DEBUG via une variable d'environnement (DEBUG=False pour la prod)
# S'assure que DEBUG est un booléen
DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 't') 

# Configuration des hôtes autorisés
# En production (Railway), vous devez injecter l'URL via ALLOWED_HOSTS
if not DEBUG:
    # Pour Railway, on autorise l'URL du service et tout ce qui est .railway.app
    ALLOWED_HOSTS = [
        os.environ.get('RAILWAY_STATIC_URL', 'goprojet.up.railway.app'),
        '.railway.app' 
    ]
else:
    # En développement local
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.localhost']

# --- 3. APPLICATIONS DE BASE ---
INSTALLED_APPS = [
    # Les applications Cloudinary DOIVENT être ajoutées APRÈS la vérification
    # et la logique de nettoyage est à revoir (voir section Cloudinary)
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Vos applications
    'projets',
    # CORRECTION : 'projets.templatetags' n'est PAS une application. 
    # Les template tags sont chargés automatiquement par l'app parente ('projets').
]

# --- 4. MIDDLEWARE ---
# L'ordre est très important. whitenoise.middleware doit être proche du haut.
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Conserver ici
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

# URLs publiques (sans authentification requise)
# Note : C'est une configuration pour le middleware, la logique est correcte.
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

# SÉCURITÉ AUTHENTIFICATION
SESSION_COOKIE_AGE = 1209600 
SESSION_EXPIRE_AT_BROWSER_CLOSE = False 

# --- 5. URLS & TEMPLATES ---
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

# --- 6. DATABASE ---
# Utilisation de db.sqlite3 pour le développement et Railway (par défaut)
# Si Railway fournit une base de données PostgreSQL/MySQL, vous devrez 
# utiliser django-environ ou dj-database-url pour la remplacer.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# PASSWORD VALIDATION (Les réglages par défaut sont corrects)
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# INTERNATIONALIZATION
LANGUAGE_CODE = 'fr-fr' # Changé de 'en-us' à 'fr-fr' pour la cohérence
TIME_ZONE = 'Europe/Paris' # Un fuseau horaire plus précis
USE_I18N = True
USE_TZ = True

# --- 7. STATIC FILES ---
# Pour une meilleure compatibilité, utilisons Pathlib pour STATIC_ROOT
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles' # Utilisation de pathlib
STATICFILES_DIRS = [
    # CORRECTION : Utiliser BASE_DIR / 'projets/static' uniquement si 
    # vous avez des fichiers statiques globaux à la racine de 'projets'.
    # Si les fichiers statiques sont dans votre dossier principal 'static/' à la racine du projet,
    # changez-le en BASE_DIR / 'static'. 
    # Laisser 'projets/static' si c'est la structure voulue.
    BASE_DIR / 'goProjet' / 'static',
]
# --- DEBUG 2 : Afficher le chemin complet calculé ---
if BASE_DIR / 'static' in STATICFILES_DIRS:
    print(f"DEBUG - STATICFILES_DIRS (Chemin Cherché) : {BASE_DIR / 'static'}")
else:
    # Si vous avez plusieurs entrées, affichez toute la liste
    print(f"DEBUG - STATICFILES_DIRS (Liste Complète) : {STATICFILES_DIRS}")
# Whitenoise seulement en production
if not DEBUG:
    # Pour la production : Whitenoise pour le service statique
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    # Retrait de la ligne 'else' pour STATICFILES_STORAGE, car le défaut de Django est suffisant 
    # en mode développement et est implicitement défini.

# --- 8. MEDIA FILES ---
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- 9. DEFAULT AUTO FIELD ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- 10. CONFIGURATION CLOUDINARY & STOCKAGE ---
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')

if CLOUDINARY_CLOUD_NAME:
    print("☁️  Cloudinary activé pour le stockage de fichiers.")
    
    # 1. Ajout des applications Cloudinary
    # CORRECTION MAJEURE : On ajoute les apps APRES la définition initiale
    INSTALLED_APPS.extend(['cloudinary_storage', 'cloudinary'])
    
    # 2. Configuration des clés
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': CLOUDINARY_CLOUD_NAME,
        'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
        'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
        'SECURE': True,
    }
    
    # 3. Définition du stockage par défaut
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
else:
    print("💻 Mode local (Stockage de fichiers sur disque)")
    # Si pas de Cloudinary, utiliser le stockage local
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'


# --- 11. SÉCURITÉ EN PRODUCTION (RAILWAY) ---
# La logique est correcte : basculer les sécurités basées sur DEBUG
if not DEBUG:
    print("🔒 Mode PRODUCTION activé. Sécurité renforcée.")
    # Paramètres de sécurité pour le proxy Railway
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    
    # Autoriser l'origine des requêtes
    CSRF_TRUSTED_ORIGINS = [
        'https://*.railway.app', # Wildcard pour tous les sous-domaines Railway
    ]
else:
    print("🔓 Mode DÉVELOPPEMENT activé. HTTP autorisé.")
    SECURE_SSL_REDIRECT = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    # Autoriser HTTP en développement
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ]
    
# --- 12. EMAIL EN PRODUCTION ---
if not DEBUG:
    # Utilisation d'un backend SMTP si on est en production
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'contact@votresite.com') # Meilleur que missbahi
else:
    # En développement : Console pour ne pas envoyer de vrais emails
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'