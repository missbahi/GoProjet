/* static/projets/js/common.js */
(function() {
    'use strict';

    if (window.__commonInitialized) return;
    window.__commonInitialized = true;
    let panelRefresh = null;
    let panelRefreshPending = false;

    function refreshNotificationPanel() {
        const panel = document.getElementById('notification-panel');
        if (!panel) return Promise.resolve();
        if (panelRefresh) {
            panelRefreshPending = true;
            return panelRefresh;
        }
        const url = new URL(panel.dataset.refreshUrl, window.location.origin);
        const token = document.querySelector('#main-content .app-breadcrumb')?.dataset.notificationOrigin;
        if (token) url.searchParams.set('breadcrumb', token);
        panelRefresh = fetch(url.pathname + url.search, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            cache: 'no-store',
        }).then(async response => {
            if (!response.ok || response.redirected) throw new Error(`HTTP ${response.status}`);
            const template = document.createElement('template');
            template.innerHTML = await response.text();
            const replacement = template.content.querySelector('#notification-panel');
            if (!replacement) throw new Error('Réponse notifications invalide');
            const current = document.getElementById('notification-panel');
            if (!current) return;
            const open = !getNotifDropdown()?.classList.contains('hidden');
            current.replaceWith(replacement);
            if (open) getNotifDropdown()?.classList.remove('hidden');
            window.htmx?.process(replacement);
        }).catch(error => {
            console.error('[notifications] Actualisation impossible', error);
            window.showErrorMessage?.("Impossible d'actualiser les notifications.");
        }).finally(() => {
            panelRefresh = null;
            if (panelRefreshPending) {
                panelRefreshPending = false;
                refreshNotificationPanel();
            }
        });
        return panelRefresh;
    }

    document.body.addEventListener('notifications:changed', refreshNotificationPanel);
    document.body.addEventListener('htmx:historyRestore', refreshNotificationPanel);

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
            if (notifDropdown && !notifDropdown.classList.contains('hidden')) refreshNotificationPanel();
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

        const url = markAllBtn.dataset.actionUrl;
        const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value
            || document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1];
        if (!url || !token) {
            window.showErrorMessage?.("Impossible de marquer les notifications : configuration manquante.");
            return;
        }
        if (markAllBtn.disabled) return;
        markAllBtn.disabled = true;

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': token,
            },
            credentials: 'same-origin',
        }).then(async response => {
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || `HTTP ${response.status}`);
            document.body.dispatchEvent(new CustomEvent('notifications:changed'));
            if (document.getElementById('notifications-container') && window.htmx) {
                await window.htmx.ajax('GET', window.location.href, {
                    target: '#main-content', swap: 'innerHTML',
                });
            }
            window.showNotification?.('Toutes les notifications ont été marquées comme lues', 'success');
        }).catch(error => {
            console.error('[notifications] Lecture impossible', error);
            window.showErrorMessage?.("Impossible de marquer les notifications comme lues.");
        }).finally(() => { markAllBtn.disabled = false; });
    });

    // ============================================================
    // Fermer les dropdowns après un swap HTMX
    // ============================================================
    document.body.addEventListener('htmx:afterSwap', function(e) {
        if (e.detail.target.id === 'main-content') {
            const notifDropdown = getNotifDropdown();
            const userDropdown = getUserDropdown();
            if (notifDropdown) notifDropdown.classList.add('hidden');
            if (userDropdown) userDropdown.classList.add('hidden');
            refreshNotificationPanel();
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
    document.body.addEventListener('htmx:historyRestore', updateTopbarTitle);

    /* ═══════════════════════════════════════════════════════════════
   Refresh du contenu principal (utilisé après succès modal)
   ═══════════════════════════════════════════════════════════════ */
    window.refreshMainContent = function () {
        if (!window.htmx) { window.location.reload(); return; }
        window.htmx.ajax('GET', window.location.pathname + window.location.search, {
            target: '#main-content',
            swap: 'innerHTML swap:150ms settle:150ms show:top',
            indicator: '#htmx-progress',
        });
    };
})();