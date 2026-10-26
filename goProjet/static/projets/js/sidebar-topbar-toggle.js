/**
 * GoProjet — Gestion des toggles UI
 *
 * Ctrl + B         → Sidebar
 * Ctrl + Shift + B → Topbar
 */
(function () {
    'use strict';

    function setupToggle({
        buttonId,
        bodyClass,
        storageKey
    }) {
        const button = document.getElementById(buttonId);

        if (!button) return;

        function applyState(active) {
            document.body.classList.toggle(bodyClass, active);
            button.setAttribute('aria-expanded', String(!active));
        }

        // Restauration de l'état
        try {
            applyState(localStorage.getItem(storageKey) === 'true');
        } catch (_) {}

        // Clic
        button.addEventListener('click', () => {
            const active = document.body.classList.toggle(bodyClass);

            button.setAttribute('aria-expanded', String(!active));

            try {
                localStorage.setItem(storageKey, String(active));
            } catch (_) {}
        });

        return button;
    }

    const sidebarBtn = setupToggle({
        buttonId: 'sidebar-toggle-btn',
        bodyClass: 'sidebar-is-collapsed',
        storageKey: 'goprojet:sidebar-collapsed'
    });

    const topbarBtn = setupToggle({
        buttonId: 'topbar-toggle-btn',
        bodyClass: 'app-topbar-is-hidden',
        storageKey: 'goprojet:topbar-hidden'
    });

    // Raccourcis clavier
    document.addEventListener('keydown', (e) => {
        const target = e.target;
        const tag = target?.tagName?.toLowerCase();

        if (
            tag === 'input' ||
            tag === 'textarea' ||
            target?.isContentEditable
        ) {
            return;
        }

        if (!(e.ctrlKey || e.metaKey)) {
            return;
        }

        if (e.key.toLowerCase() !== 'b') {
            return;
        }

        e.preventDefault();

        // Ctrl+Shift+B => Topbar
        if (e.shiftKey) {
            topbarBtn?.click();
            return;
        }

        // Ctrl+B => Sidebar
        sidebarBtn?.click();
    });
})();