/**
 * GoProjet — Bouton toggle sidebar (desktop)
 * - Slide la sidebar via .sidebar-is-collapsed sur <body>
 * - Persiste l'état dans localStorage
 * - Raccourci Ctrl/Cmd + B
 */
(function () {
    'use strict';

    const STORAGE_KEY = 'goprojet:sidebar-collapsed';
    const btn = document.getElementById('sidebar-toggle-btn');
    if (!btn) return;

    // ══════════════════════════════════════════════════════════
    // Restauration de l'état au chargement
    // ══════════════════════════════════════════════════════════
    function applyState(collapsed) {
        document.body.classList.toggle('sidebar-is-collapsed', collapsed);
        btn.setAttribute('aria-expanded', String(!collapsed));
    }

    try {
        if (localStorage.getItem(STORAGE_KEY) === 'true') {
            applyState(true);
        }
    } catch (_) { /* localStorage indisponible */ }

    // ══════════════════════════════════════════════════════════
    // Toggle au clic
    // ══════════════════════════════════════════════════════════
    btn.addEventListener('click', () => {
        const collapsed = document.body.classList.toggle('sidebar-is-collapsed');
        btn.setAttribute('aria-expanded', String(!collapsed));
        try {
            localStorage.setItem(STORAGE_KEY, collapsed ? 'true' : 'false');
        } catch (_) { /* noop */ }
    });

    // ══════════════════════════════════════════════════════════
    // Raccourci clavier Ctrl+B / Cmd+B
    // ══════════════════════════════════════════════════════════
    document.addEventListener('keydown', (e) => {
        if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== 'b') return;

        // Ne pas intercepter si focus dans un champ texte
        const t = e.target;
        const tag = t?.tagName?.toLowerCase();
        if (tag === 'input' || tag === 'textarea' || t?.isContentEditable) {
            return;
        }

        e.preventDefault();
        btn.click();
    });
})();