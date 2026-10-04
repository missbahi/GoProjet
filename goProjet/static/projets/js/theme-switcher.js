/**
 * Theme Switcher — minimaliste
 * - Lit le thème depuis l'attribut data-theme (posé par Django)
 * - Toggle = change l'attribut + sauvegarde côté serveur
 */
(function() {
    'use strict';

    const SET_THEME_URL = '/api/user/set-theme/';

    function getCurrentTheme() {
        return document.documentElement.getAttribute('data-theme') || 'dark';
    }

    function applyTheme(theme) {
        if (theme !== 'dark' && theme !== 'light') theme = 'dark';

        document.documentElement.setAttribute('data-theme', theme);

        // Mise à jour des icônes
        document.querySelectorAll('[data-theme-toggle-icon]').forEach(el => {
            el.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        });
    }

    function saveTheme(theme) {
        const csrf = getCookie('csrftoken');
        if (!csrf) return;

        fetch(SET_THEME_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrf,
            },
            body: 'theme=' + encodeURIComponent(theme),
            credentials: 'same-origin',
        }).catch(err => console.warn('[Theme]', err));
    }

    function getCookie(name) {
        for (let c of document.cookie.split(';')) {
            c = c.trim();
            if (c.startsWith(name + '=')) {
                return decodeURIComponent(c.substring(name.length + 1));
            }
        }
        return null;
    }

    function toggleTheme() {
        const current = getCurrentTheme();
        const next = current === 'dark' ? 'light' : 'dark';
        applyTheme(next);
        saveTheme(next);
    }

    window.GoprojetTheme = {
        get: getCurrentTheme,
        toggle: toggleTheme,
        apply: applyTheme,
    };

    // Délégation : clic sur le bouton
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('[data-theme-toggle]');
        if (!btn) return;
        e.preventDefault();
        toggleTheme();
    }, true);

    // Init : mettre à jour les icônes au chargement (ne PAS changer le thème)
    document.addEventListener('DOMContentLoaded', function() {
        applyTheme(getCurrentTheme());
    });
})();