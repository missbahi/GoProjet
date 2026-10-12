/* static/projets/js/htmx-config.js */
(function () {
    'use strict';

    if (window.__htmxConfigInitialized) {
        console.warn('[htmx-config] déjà initialisé, skip');
        return;
    }
    window.__htmxConfigInitialized = true;

    function syncNotificationLinks() {
        const breadcrumb = document.querySelector('#main-content .app-breadcrumb');
        const token = breadcrumb?.dataset.notificationOrigin;
        document.querySelectorAll('a[data-notifications-url]').forEach(link => {
            const url = new URL(link.dataset.notificationsUrl, window.location.origin);
            if (token) url.searchParams.set('breadcrumb', token);
            const target = url.pathname + url.search;
            link.setAttribute('href', target);
            if (link.hasAttribute('hx-get')) link.setAttribute('hx-get', target);
        });
    }

    document.addEventListener('click', function (e) {
        if (e.target.closest('a[data-notifications-url]')) syncNotificationLinks();
    }, true);
    document.body.addEventListener('htmx:historyRestore', syncNotificationLinks);

    // ═══════════════════════════════════════════════════════════
    // CONFIGURATION GLOBALE HTMX
    // ═══════════════════════════════════════════════════════════
    document.body.addEventListener('htmx:configRequest', function (e) {
        e.detail.headers['X-Requested-With'] = 'XMLHttpRequest';
    });

    // ═══════════════════════════════════════════════════════════
    // ASSETS PAR FAMILLE
    // ═══════════════════════════════════════════════════════════
    const FAMILY_ASSETS = {
        app: {
            css: [
                '/static/projets/css/home.css',
                '/static/projets/css/dossiers.css',
                '/static/projets/css/liste_projets.css',
                '/static/projets/css/taches.css',
                '/static/projets/css/notifications.css',
                '/static/projets/css/utilisateurs.css',
                '/static/projets/css/ordres_service.css'
            ],
            js: [
                '/static/projets/js/dossiers.js',
                '/static/projets/js/liste_projets.js',
                '/static/projets/js/taches.js',
                '/static/projets/js/home.js',
                '/static/projets/js/notifications.js',
                '/static/projets/js/utilisateurs.js',
                '/static/projets/js/ordres_service.js',
            ],
        },
        project: {
            css: [
                '/static/projets/css/dashboard.css',
                '/static/projets/css/documents.css',
                '/static/projets/css/lots.css',  
                '/static/projets/css/situations.css',
                '/static/projets/css/attachements.css',
                '/static/projets/css/ateliers.css',
            ],
            js: [
                '/static/projets/js/dashboard.js',
                '/static/projets/js/taches.js',
                '/static/projets/js/documents.js',
                '/static/projets/js/lots.js', 
                '/static/projets/js/situations.js',
                '/static/projets/js/attachements.js',
                '/static/projets/js/atelier-modal.js',
                '/static/projets/js/affectation-modal.js',
                '/static/projets/js/ateliers-planning.js',
            ],
        },
    };

    // Track des assets déjà chargés (par famille)
    const loaded = new Set();

    function injectCss(url) {
        // Vérifier par src, pas par id
        const existing = [...document.querySelectorAll('link[rel="stylesheet"]')]
            .some(link => link.href === new URL(url, window.location.origin).href);
        if (existing) return;

        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = url;
        link.dataset.dynamic = 'true';
        document.head.appendChild(link);
    }

    function injectJs(url) {
        // Vérifier par src
        const existing = [...document.querySelectorAll('script')]
            .some(s => s.src === new URL(url, window.location.origin).href);
        if (existing) return;

        const script = document.createElement('script');
        script.src = url;
        script.defer = true;
        script.dataset.dynamic = 'true';
        document.body.appendChild(script);
    }

    function loadFamilyAssets(family) {
        if (!family || loaded.has(family)) return;
        const config = FAMILY_ASSETS[family];
        if (!config) return;

        config.css.forEach(injectCss);
        config.js.forEach(injectJs);
        loaded.add(family);
        console.log(`[HTMX] Assets Famille "${family}" chargés`);
    }

    // ═══════════════════════════════════════════════════════════
    // DÉTECTION DE FAMILLE APRÈS SWAP
    // ═══════════════════════════════════════════════════════════
    document.body.addEventListener('htmx:afterSwap', function (e) {
        if (e.detail.target.id !== 'main-content') return;
        syncNotificationLinks();

        // 1. Cherche data-family dans le nouveau contenu
        const wrapper = e.detail.target.querySelector('[data-family]');
        const family = wrapper?.dataset.family
            || e.detail.target.dataset.family;

        if (family) {
            loadFamilyAssets(family);
        }
    });

    // ═══════════════════════════════════════════════════════════
    // INITIALISATION — Famille courante (rendu serveur)
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('DOMContentLoaded', function () {
        syncNotificationLinks();
        const family = document.getElementById('main-content')?.dataset.family;
        if (family) {
            loadFamilyAssets(family); 
        }
    });

    // ═══════════════════════════════════════════════════════════
    // GESTION D'ERREURS
    // ═══════════════════════════════════════════════════════════
    document.body.addEventListener('htmx:responseError', function (e) {
        console.error('[HTMX] Erreur', e.detail.xhr.status);
        if (typeof window.showErrorMessage === 'function') {
            window.showErrorMessage(`Erreur ${e.detail.xhr.status}`);
        }
    });
})();