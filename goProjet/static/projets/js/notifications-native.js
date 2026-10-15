/**
 * projets/js/notifications-native.js
 *
 * Notifications navigateur (à la Gmail / WhatsApp Web).
 * V1 : polling toutes les 60s tant que l'app est ouverte.
 */
(function () {
    'use strict';
    if (window.__nativeNotifInitialized) return;
    window.__nativeNotifInitialized = true;

    const POLL_INTERVAL = 60000;           // 60 secondes
    const PERMISSION_KEY = 'goprojet-native-notif-asked';
    const SEEN_IDS_KEY = 'goprojet-native-notif-seen';
    const BASE_TITLE = document.title.replace(/^\(\d+\)\s*/, '');

    // ------------------------------------------------------------
    // 1. Demande de permission (une seule fois)
    // ------------------------------------------------------------
    async function requestPermission() {
        if (!('Notification' in window)) {
            console.info('[native-notif] API Notification non supportée par ce navigateur.');
            return false;
        }
        if (Notification.permission === 'granted') return true;
        if (Notification.permission === 'denied') return false;
        if (localStorage.getItem(PERMISSION_KEY)) return false;

        localStorage.setItem(PERMISSION_KEY, '1');

        try {
            const permission = await Notification.requestPermission();
            return permission === 'granted';
        } catch (e) {
            console.warn('[native-notif] Erreur demande permission:', e);
            return false;
        }
    }

    // ------------------------------------------------------------
    // 2. Affichage d'une notification navigateur
    // ------------------------------------------------------------
    function showNative(title, body, url = null) {
        if (Notification.permission !== 'granted') return null;

        try {
            const notif = new Notification(title, {
                body: body,
                icon: '/static/icons/icon-192x192.png',      // ⚡ icône principale
                badge: '/static/icons/icon-192x192.png',     // ⚡ badge OS (Android)
                image: '/static/icons/icon-512x512.png',     // ⚡ (optionnel) grande image
                tag: 'goprojet-' + Date.now(),
                requireInteraction: false,
                silent: false,
            });

            if (url) {
                notif.onclick = () => {
                    window.focus();
                    window.location.href = url;
                    notif.close();
                };
            }

            setTimeout(() => notif.close(), 10000);
            return notif;
        } catch (e) {
            console.warn('[native-notif] Erreur affichage:', e);
            return null;
        }
    }

    // ------------------------------------------------------------
    // 3. Polling des notifications non-lues
    // ------------------------------------------------------------
    async function pollUnreadNotifications() {
        if (Notification.permission !== 'granted') return;

        // Skip si l'utilisateur regarde déjà l'onglet
        if (document.visibilityState === 'visible') {
            await updateTabTitleFromAPI();
            return;
        }

        try {
            const res = await fetch('/api/notifications/non-lues/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!res.ok) return;
            const data = await res.json();

            const unread = data.notifications || [];
            const seen = new Set(JSON.parse(localStorage.getItem(SEEN_IDS_KEY) || '[]'));
            const nouvelles = unread.filter(n => !seen.has(n.id));

            nouvelles.slice(0, 3).forEach(n => {
                const url = n.action_url || (n.projet ? `/projet/${n.projet.id}/dashboard/` : null);
                showNative(n.titre, n.message, url);
                seen.add(n.id);
            });

            localStorage.setItem(
                SEEN_IDS_KEY,
                JSON.stringify([...seen].slice(-200))
            );

            updateTabTitle(unread.length);
        } catch (e) {
            // Silencieux : best-effort
        }
    }

    // ------------------------------------------------------------
    // 4. Titre de l'onglet
    // ------------------------------------------------------------
    function updateTabTitle(count) {
        document.title = count > 0 ? `(${count}) ${BASE_TITLE}` : BASE_TITLE;
    }

    async function updateTabTitleFromAPI() {
        try {
            const res = await fetch('/api/notifications/non-lues/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!res.ok) return;
            const data = await res.json();
            updateTabTitle((data.notifications || []).length);
        } catch (e) {}
    }

    // ------------------------------------------------------------
    // 5. Réactions aux événements de l'app
    // ------------------------------------------------------------
    document.addEventListener('notifications:changed', updateTabTitleFromAPI);
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') updateTabTitleFromAPI();
    });

    // ------------------------------------------------------------
    // 6. Démarrage
    // ------------------------------------------------------------
    document.addEventListener('DOMContentLoaded', async () => {
        await updateTabTitleFromAPI();

        const granted = await requestPermission();
        if (!granted) return;

        pollUnreadNotifications();
        setInterval(pollUnreadNotifications, POLL_INTERVAL);
    });

    // ------------------------------------------------------------
    // 7. API publique
    // ------------------------------------------------------------
    window.NativeNotif = {
        show: showNative,
        poll: pollUnreadNotifications,
        requestPermission: requestPermission,
    };
})();