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