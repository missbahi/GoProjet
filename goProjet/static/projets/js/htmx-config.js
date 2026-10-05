(function() {
    'use strict';

    // ============================================================
    // Configuration globale HTMX
    // ============================================================
    document.addEventListener('DOMContentLoaded', function() {

        // Barre de progression globale
        const progressBar = document.getElementById('htmx-progress');

        document.body.addEventListener('htmx:beforeRequest', function(e) {
            if (progressBar) progressBar.classList.add('active');
        });

        document.body.addEventListener('htmx:afterRequest', function(e) {
            if (progressBar) progressBar.classList.remove('active');
        });

        // Gestion des erreurs
        document.body.addEventListener('htmx:responseError', function(e) {
            console.error('[HTMX] Erreur de réponse:', e.detail.xhr.status, e.detail.xhr.responseText);
            if (typeof window.showNotification === 'function') {
                window.showNotification('Erreur de chargement. Rechargez la page.', 'error');
            }
        });

        // ============================================================
        // Après swap : ré-exécuter les scripts et ré-initialiser
        // ============================================================
        document.body.addEventListener('htmx:afterSwap', function(e) {
            if (e.target.id !== 'main-content') return;

            e.target.querySelectorAll('script').forEach(oldScript => {
                // ⚡ Ignorer les scripts PWA (déjà chargés)
                const content = oldScript.textContent || '';
                if (content.includes('deferredPrompt') ||
                    content.includes('beforeinstallprompt') ||
                    content.includes('serviceWorker')) {
                    return;
                }

                const newScript = document.createElement('script');
                Array.from(oldScript.attributes).forEach(attr => {
                    newScript.setAttribute(attr.name, attr.value);
                });
                newScript.textContent = oldScript.textContent;
                oldScript.parentNode.replaceChild(newScript, oldScript);
            });
        });

        // ============================================================
        // Gestion de l'historique (bouton retour)
        // ============================================================
        document.body.addEventListener('htmx:afterSettle', function(e) {
            // Mettre en surbrillance le menu actif
            const currentPath = window.location.pathname;
            document.querySelectorAll('.sidebar-item').forEach(item => {
                const href = item.getAttribute('href');
                if (href && currentPath.startsWith(href) && href !== '/') {
                    item.classList.add('active');
                } else if (href === currentPath) {
                    item.classList.add('active');
                } else {
                    item.classList.remove('active');
                }
            });
        });
    });
})();