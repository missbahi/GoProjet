/* static/projets/js/common.js */
(function() {
    'use strict';

    // ============================================================
    // Getters — résolvent l'élément à chaque appel
    // (survit aux swaps HTMX)
    // ============================================================
    function getUserDropdown() {
        return document.getElementById('userMenuDropdown');
    }
    function getNotifDropdown() {
        return document.getElementById('notificationDropdown');
    }

    // ============================================================
    // UN SEUL listener pour gérer tous les clics
    // ============================================================
    document.addEventListener('click', function(e) {
        const userBtn = document.getElementById('userMenuBtn');
        const notifBtn = document.getElementById('notificationBtn');
        const userDropdown = getUserDropdown();
        const notifDropdown = getNotifDropdown();

        // ⚡ Clic sur le bouton "menu utilisateur"
        if (userBtn && e.target.closest('#userMenuBtn')) {
            e.stopPropagation();
            if (userDropdown) userDropdown.classList.toggle('hidden');
            if (notifDropdown) notifDropdown.classList.add('hidden');
            return;
        }

        // ⚡ Clic sur le bouton "cloche notifications"
        if (notifBtn && e.target.closest('#notificationBtn')) {
            e.preventDefault();
            e.stopPropagation();
            if (notifDropdown) notifDropdown.classList.toggle('hidden');
            if (userDropdown) userDropdown.classList.add('hidden');
            return;
        }

        // ⚡ Clic en dehors OU sur un lien du dropdown utilisateur → fermer
        if (userDropdown && !userDropdown.classList.contains('hidden')) {
            const clickedOutside = !e.target.closest('#userMenuBtn')
                                && !e.target.closest('#userMenuDropdown');
            const clickedInsideLink = e.target.closest('#userMenuDropdown a');
            if (clickedOutside || clickedInsideLink) {
                userDropdown.classList.add('hidden');
            }
        }

        // ⚡ Clic en dehors OU sur un lien du dropdown notifications → fermer
        if (notifDropdown && !notifDropdown.classList.contains('hidden')) {
            const clickedOutside = !e.target.closest('#notificationBtn')
                                && !e.target.closest('#notificationDropdown');
            const clickedInsideLink = e.target.closest('#notificationDropdown a');
            if (clickedOutside || clickedInsideLink) {
                notifDropdown.classList.add('hidden');
            }
        }
    });

    // ============================================================
    // "Marquer tout comme lu" depuis le dropdown
    // ============================================================
    document.addEventListener('click', function(e) {
        const markAllBtn = e.target.closest('#markAllReadFromDropdown');
        if (!markAllBtn) return;

        e.preventDefault();
        e.stopPropagation();

        const url = window.NOTIFICATION_API_URL;
        const token = window.CSRF_TOKEN;
        if (!url || !token) return;

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': token,
            },
            credentials: 'same-origin',
        }).then(response => {
            if (response.ok) {
                const badge = document.querySelector('#notificationBtn span');
                if (badge) badge.remove();
                document.querySelectorAll('.notification-item').forEach(item => {
                    item.classList.remove('app-dropdown-item-unread');
                    const dot = item.querySelector('.flex-shrink-0 div');
                    if (dot) dot.classList.replace('bg-cyan-500', 'bg-gray-500');
                });
                if (typeof window.showNotification === 'function') {
                    window.showNotification(
                        'Toutes les notifications ont été marquées comme lues',
                        'success'
                    );
                }
            }
        });
    });

    // ============================================================
    // Fermer les dropdowns après un swap HTMX
    // ============================================================
    document.body.addEventListener('htmx:afterSwap', function(e) {
        if (e.target.id === 'main-content') {
            const notifDropdown = getNotifDropdown();
            const userDropdown = getUserDropdown();
            if (notifDropdown) notifDropdown.classList.add('hidden');
            if (userDropdown) userDropdown.classList.add('hidden');
        }
    });

    // ============================================================
    // Fallback avatar
    // ============================================================
    window.handleNavbarAvatarError = function(img) {
        img.onerror = null;
        const username = document.body.dataset.username || 'User';
        img.src = 'https://ui-avatars.com/api/?name='
                + encodeURIComponent(username)
                + '&background=10B981&color=fff&size=64';
    };

})();


/* ═══════════════════════════════════════════════════════════════
   TOPBAR — Titre dynamique selon le module courant
   ═══════════════════════════════════════════════════════════════ */
(function () {
    'use strict';

    // Garde anti-double-init
    if (window.__topbarTitleInitialized) return;
    window.__topbarTitleInitialized = true;

    function updateTopbarTitle() {
        const mainContent = document.getElementById('main-content');
        if (!mainContent) return;

        // Cherche le wrapper avec data-page-title
        const wrapper = mainContent.querySelector('[data-page-title]');
        if (!wrapper) return;

        const title = wrapper.dataset.pageTitle;
        const icon = wrapper.dataset.pageIcon || 'fa-home';

        const titleEl = document.getElementById('topbar-title');
        const textEl = document.getElementById('topbar-title-text');
        const iconEl = document.getElementById('topbar-title-icon');

        if (!textEl || !iconEl) return;

        // Ne rien faire si le titre n'a pas changé
        if (textEl.textContent.trim() === title) return;

        // Fade out
        titleEl?.classList.add('updating');

        setTimeout(() => {
            textEl.textContent = title;
            iconEl.className = `fas ${icon}`;
            document.title = `${title} – GoProjet`;

            // Fade in
            titleEl?.classList.remove('updating');
        }, 150);
    }

    // 1. Au chargement initial
    document.addEventListener('DOMContentLoaded', updateTopbarTitle);

    // 2. Après chaque swap HTMX
    document.body.addEventListener('htmx:afterSwap', function (e) {
        if (e.detail.target.id === 'main-content') {
            updateTopbarTitle();
        }
    });

    // 3. Après retour arrière navigateur
    window.addEventListener('popstate', updateTopbarTitle);

})();