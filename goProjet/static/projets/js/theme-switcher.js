(function() {
    'use strict';

    const STORAGE_KEY = 'goprojet-theme';
    const DEFAULT_THEME = 'dark';
    const VALID_THEMES = ['dark', 'light'];

    // ============================================================
    // Lecture / écriture de la préférence
    // ============================================================
    function getStoredTheme() {
        try {
            const t = localStorage.getItem(STORAGE_KEY);
            return VALID_THEMES.includes(t) ? t : DEFAULT_THEME;
        } catch {
            return DEFAULT_THEME;
        }
    }

    function setStoredTheme(theme) {
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch {}
    }

    // ============================================================
    // Application du thème au DOM
    // ============================================================
    function applyTheme(theme) {
        if (!VALID_THEMES.includes(theme)) theme = DEFAULT_THEME;

        document.documentElement.setAttribute('data-theme', theme);
        setStoredTheme(theme);

        // Mise à jour de l'icône du bouton toggle (si présent)
        document.querySelectorAll('[data-theme-toggle-icon]').forEach(el => {
            el.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        });

        // Mise à jour du label (accessibilité)
        document.querySelectorAll('[data-theme-toggle]').forEach(btn => {
            btn.setAttribute('aria-label',
                theme === 'dark' ? 'Activer le thème clair' : 'Activer le thème sombre');
            btn.setAttribute('title',
                theme === 'dark' ? 'Thème clair' : 'Thème sombre');
        });
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme') || DEFAULT_THEME;
        applyTheme(current === 'dark' ? 'light' : 'dark');
    }

    // ============================================================
    // Exposition globale
    // ============================================================
    window.GoprojetTheme = {
        apply: applyTheme,
        toggle: toggleTheme,
        get: () => document.documentElement.getAttribute('data-theme') || DEFAULT_THEME,
    };

    // ============================================================
    // Init : appliquer le thème stocké IMMÉDIATEMENT
    // ============================================================
    applyTheme(getStoredTheme());

    // ============================================================
    // Délégation d'événements pour les boutons de bascule
    // (survit aux swaps HTMX)
    // ============================================================
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('[data-theme-toggle]');
        if (!btn) return;
        e.preventDefault();
        e.stopPropagation();
        toggleTheme();
    }, true);
})();