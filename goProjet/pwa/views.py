# goProjet/pwa/views.py - VERSION CORRIGÉE
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET
import os
import json
from django.conf import settings

@require_GET
def manifest_view(request):
    """Vue pour manifest.json - retourne du JSON directement"""

    # Vérifier si PWA est activé
    pwa_enabled = getattr(settings, 'PWA_CONFIG', {}).get('ENABLED', False)
    if not pwa_enabled:
        return JsonResponse({'error': 'PWA disabled'}, status=404)
    
    # Construire le manifest depuis la configuration
    manifest = {
        "name": getattr(settings, 'PWA_APP_NAME', 'GoProjet'),
        "short_name": getattr(settings, 'PWA_APP_NAME', 'GoProjet'),
        "description": getattr(settings, 'PWA_APP_DESCRIPTION', ''),
        "start_url": getattr(settings, 'PWA_APP_START_URL', '/'),
        "display": getattr(settings, 'PWA_APP_DISPLAY', 'standalone'),
        "theme_color": getattr(settings, 'PWA_APP_THEME_COLOR', '#0A0302'),
        "background_color": getattr(settings, 'PWA_APP_BACKGROUND_COLOR', '#ffffff'),
        "icons": getattr(settings, 'PWA_APP_ICONS', []),
        "scope": getattr(settings, 'PWA_APP_SCOPE', '/'),
        "orientation": getattr(settings, 'PWA_APP_ORIENTATION', 'any'),
    }
    
    return JsonResponse(
        manifest, 
        json_dumps_params={'indent': 2, 'ensure_ascii': False}
    )

@require_GET
def serviceworker_view(request):
    """Vue pour serviceworker.js - retourne le fichier directement"""
    
    # Vérifier si PWA est activé
    pwa_enabled = getattr(settings, 'PWA_CONFIG', {}).get('ENABLED', False)
    if not pwa_enabled:
        return HttpResponse("// PWA disabled", 
                          content_type='application/javascript', 
                          status=404)
    
    try:
        # Utiliser le chemin défini dans settings.py
        sw_path = getattr(settings, 'PWA_SERVICE_WORKER_PATH', None)
        
        if sw_path and os.path.exists(sw_path):
            filepath = sw_path
        else:
            # Fallback au chemin par défaut
            filepath = os.path.join(
                settings.BASE_DIR,
                'goProjet',
                'static',
                'projets',
                'js',
                'serviceworker.js'
            )
        
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            # Service worker minimal
            content = """// Service Worker minimal
                const CACHE_NAME = 'goprojet-v1';
                self.addEventListener('install', e => {
                    console.log('[SW] Install');
                    e.waitUntil(caches.open(CACHE_NAME)
                        .then(cache => cache.add('/'))
                        .then(() => self.skipWaiting()));
                });
                self.addEventListener('fetch', e => {
                    e.respondWith(caches.match(e.request)
                        .then(res => res || fetch(e.request)));
                });"""
                        
        # ⭐⭐ IMPORTANT : HttpResponse avec bon Content-Type ⭐⭐
        response = HttpResponse(content, content_type='application/javascript')
        response['Service-Worker-Allowed'] = '/'
        return response
        
    except Exception as e:
        content = f"console.error('Service Worker error: {str(e)}');"
        response = HttpResponse(content, content_type='application/javascript')
        response['Service-Worker-Allowed'] = '/'
        return response