/* static/projets/js/sidebar.js */
(function () {
    'use strict';

    // ═══════════════════════════════════════════════════════════
    // MISE À JOUR DE L'ITEM ACTIF
    // ═══════════════════════════════════════════════════════════
    function updateSidebarActive() {
        const currentPath = window.location.pathname.replace(/\/$/, '') || '/';

        document.querySelectorAll('.sidebar-item').forEach(item => {
            item.classList.remove('active');

            const href = item.getAttribute('href');
            if (!href || href === '#' || href.startsWith('javascript:')) return;

            try {
                const linkPath = new URL(href, window.location.origin)
                    .pathname.replace(/\/$/, '') || '/';

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
    // OUVERTURE / FERMETURE DE LA SIDEBAR MOBILE
    // ═══════════════════════════════════════════════════════════
    function openMobileSidebar() {
        const sidebar = document.getElementById('mobileSidebar');
        const overlay = document.getElementById('sidebarOverlay');
        if (sidebar) sidebar.classList.add('open');
        if (overlay) overlay.classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function closeMobileSidebar() {
        const sidebar = document.getElementById('mobileSidebar');
        const overlay = document.getElementById('sidebarOverlay');
        if (sidebar) sidebar.classList.remove('open');
        if (overlay) overlay.classList.remove('open');
        document.body.style.overflow = '';
    }

    // ═══════════════════════════════════════════════════════════
    // DÉLÉGATION DES CLICS (capture phase, survit à tout)
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('click', function (e) {
        // 1. Ouverture : hamburger
        const toggle = e.target.closest('#sidebarToggle, #mobileMenuBtn');
        if (toggle) {
            e.preventDefault();
            openMobileSidebar();
            return;
        }

        // 2. Fermeture : croix ou overlay
        if (e.target.closest('#mobileSidebarClose') || e.target.closest('#sidebarOverlay')) {
            e.preventDefault();
            closeMobileSidebar();
            return;
        }

        // 3. Fermeture auto après clic sur un lien de la sidebar mobile
        if (e.target.closest('#mobileSidebar a')) {
            closeMobileSidebar();
        }
    }, true); // ← CAPTURE PHASE

    // Échap ferme la sidebar mobile
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeMobileSidebar();
    });

    // Reset au redimensionnement (retour desktop)
    window.addEventListener('resize', function () {
        if (window.innerWidth >= 768) closeMobileSidebar();
    });

    // ═══════════════════════════════════════════════════════════
    // ÉCOUTEURS POUR L'ITEM ACTIF
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('DOMContentLoaded', updateSidebarActive);
    document.body.addEventListener('htmx:afterSwap', updateSidebarActive);
    document.body.addEventListener('htmx:pushedIntoHistory', updateSidebarActive);
    window.addEventListener('popstate', updateSidebarActive);

    // ═══════════════════════════════════════════════════════════
    // API GLOBALE (pour debug ou appels externes)
    // ═══════════════════════════════════════════════════════════
    window.openMobileSidebar = openMobileSidebar;
    window.closeMobileSidebar = closeMobileSidebar;

})();