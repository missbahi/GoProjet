# projets/middleware/pwa_injector.py
import re
from django.conf import settings
from django.utils.html import format_html

class PWAInjectorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        response = self.get_response(request)
        
        # Vérifier si PWA est activé
        pwa_enabled = getattr(settings, 'PWA_CONFIG', {}).get('ENABLED', False)
        
        if not pwa_enabled:
            return response
            
        # Vérifier si c'est une réponse HTML
        content_type = response.get('Content-Type', '')
        if not ('text/html' in content_type and response.status_code == 200):
            return response
            
        # Ne pas injecter dans les réponses AJAX/JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return response
            
        try:
            content = response.content.decode('utf-8')
            
            # Vérifier si PWA n'est pas déjà injecté
            if '<!-- PWA Auto-injected -->' in content:
                return response
                
            # Injecter les tags PWA
            pwa_head = self.generate_pwa_head()
            pwa_scripts = self.generate_pwa_scripts()
            
            # Injecter dans le head si </head> existe
            if '</head>' in content:
                content = content.replace('</head>', f'{pwa_head}\n</head>')
            
            # Injecter les scripts avant </body>
            if '</body>' in content:
                content = content.replace('</body>', f'{pwa_scripts}\n</body>')
            
            response.content = content.encode('utf-8')
            
        except (UnicodeDecodeError, AttributeError):
            # Silencieux en cas d'erreur
            pass
            
        return response
    def generate_pwa_head(self):
        """Génère les tags PWA pour le head"""
        theme_color = getattr(settings, 'PWA_APP_THEME_COLOR', '#0A0302')
        app_name = getattr(settings, 'PWA_APP_NAME', 'GoProjet')
        
        # Utilisez VOS icônes (192x192 et 512x512)
        return f'''
        <!-- PWA Auto-injected -->
        <meta name="application-name" content="{app_name}">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <meta name="theme-color" content="{theme_color}">
        <meta name="mobile-web-app-capable" content="yes">
        <link rel="manifest" href="/manifest.json">
        <!-- Icône standard -->
        <link rel="icon" type="image/png" sizes="192x192" href="/static/icons/icon-192x192.png">
        <link rel="icon" type="image/png" sizes="512x512" href="/static/icons/icon-512x512.png">
        <!-- Icône Apple (iOS) -->
        <link rel="apple-touch-icon" sizes="192x192" href="/static/icons/icon-192x192.png">
        <link rel="apple-touch-icon" sizes="512x512" href="/static/icons/icon-512x512.png">
        '''
    
    def generate_pwa_scripts(self):
        """Génère les scripts PWA"""
        return '''
    <!-- PWA Installation Script -->
    <script>
    // Détection et installation PWA
    let deferredPrompt;
    let pwaInstallShown = false;
    
    window.addEventListener('beforeinstallprompt', (e) => {
        // Empêcher l'affichage automatique
        e.preventDefault();
        deferredPrompt = e;
        
        // Afficher un bouton personnalisé après 3 secondes
        if (!pwaInstallShown) {
            setTimeout(() => {
                showPWAInstallButton();
                pwaInstallShown = true;
            }, 3000);
        }
        
        // Log pour débogage
        console.log('📱 PWA prête à être installée');
    });
    
    function showPWAInstallButton() {
        // Vérifier si déjà installé
        if (window.matchMedia('(display-mode: standalone)').matches) {
            return; // Déjà installé
        }
        
        // Créer un bouton flottant
        const installBtn = document.createElement('button');
        installBtn.innerHTML = '📱 Installer GoProjet';
        installBtn.id = 'pwa-install-button';
        installBtn.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 12px 20px;
            background-color: #0A0302;
            color: white;
            border: none;
            border-radius: 30px;
            cursor: pointer;
            z-index: 10000;
            box-shadow: 0 4px 15px rgba(10, 3, 2, 0.3);
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
        `;
        
        // Effet hover
        installBtn.onmouseenter = () => {
            installBtn.style.transform = 'translateY(-2px)';
            installBtn.style.boxShadow = '0 6px 20px rgba(10, 3, 2, 0.4)';
        };
        installBtn.onmouseleave = () => {
            installBtn.style.transform = 'translateY(0)';
            installBtn.style.boxShadow = '0 4px 15px rgba(10, 3, 2, 0.3)';
        };
        
        // Installation
        installBtn.onclick = () => {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                deferredPrompt.userChoice.then((choiceResult) => {
                    if (choiceResult.outcome === 'accepted') {
                        console.log('✅ PWA installée avec succès');
                        installBtn.remove();
                    } else {
                        console.log('❌ Installation annulée');
                    }
                    deferredPrompt = null;
                });
            }
        };
        
        document.body.appendChild(installBtn);
        
        // Auto-suppression après 30 secondes
        setTimeout(() => {
            const btn = document.getElementById('pwa-install-button');
            if (btn && btn.parentNode) {
                btn.remove();
            }
        }, 30000);
    }
    
    // Cacher le bouton si déjà installé
    window.addEventListener('appinstalled', () => {
        console.log('🎉 GoProjet installée comme PWA!');
        const installBtn = document.getElementById('pwa-install-button');
        if (installBtn) {
            installBtn.remove();
        }
        
        // Rediriger vers la page d'accueil si sur une page d'installation
        if (window.location.pathname.includes('install')) {
            setTimeout(() => {
                window.location.href = '/';
            }, 1000);
        }
    });
    
    // Vérifier au chargement si déjà en mode PWA
    window.addEventListener('load', () => {
        if (window.matchMedia('(display-mode: standalone)').matches) {
            console.log('📱 GoProjet fonctionne en mode PWA');
            document.documentElement.classList.add('pwa-mode');
        }
    });
    </script>
    
    <!-- Styles pour le mode PWA -->
    <style>
    .pwa-mode body {
        -webkit-user-select: none;
        user-select: none;
    }
    </style>
        '''