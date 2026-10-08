/* static/projets/js/sidebar.js */
(function () {
    'use strict';

    // ═══════════════════════════════════════════════════════════
    // MISE À JOUR DE L'ITEM ACTIF DANS LA SIDEBAR
    // ═══════════════════════════════════════════════════════════
    function updateSidebarActive() {
        const currentPath = window.location.pathname.replace(/\/$/, '') || '/';

        // Parcourt tous les liens de la sidebar (desktop + mobile)
        document.querySelectorAll('.sidebar-item').forEach(item => {
            item.classList.remove('active');

            const href = item.getAttribute('href');
            if (!href || href === '#' || href.startsWith('javascript:')) return;

            try {
                const linkPath = new URL(href, window.location.origin)
                    .pathname.replace(/\/$/, '') || '/';

                // Match exact OU current path commence par linkPath + '/'
                const isExact = linkPath === currentPath;
                const isPrefix = linkPath !== '/' && currentPath.startsWith(linkPath + '/');

                if (isExact || isPrefix) {
                    item.classList.add('active');
                }
            } catch (e) {
                console.warn('[sidebar] Invalid href:', href);
            }
        });
    }

    // ═══════════════════════════════════════════════════════════
    // ÉCOUTEURS D'ÉVÉNEMENTS
    // ═══════════════════════════════════════════════════════════

    // 1. Au chargement initial
    document.addEventListener('DOMContentLoaded', updateSidebarActive);

    // 2. Après chaque swap HTMX
    document.body.addEventListener('htmx:afterSwap', updateSidebarActive);

    // 3. Après que l'URL a changé (navigation HTMX)
    document.body.addEventListener('htmx:pushedIntoHistory', updateSidebarActive);

    // 4. Fallback : après navigation classique
    window.addEventListener('popstate', updateSidebarActive);

})();