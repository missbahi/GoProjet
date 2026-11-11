(function () {
    'use strict';

    const dialog = document.getElementById('observerGuide');
    const backdrop = document.getElementById('observerGuideBackdrop');
    if (!dialog || !backdrop || window.__observerGuideInit) return;
    window.__observerGuideInit = true;

    const checkbox = document.getElementById('observerGuideHide');
    const focusable = 'a[href], button:not([disabled]), input:not([disabled])';
    let lastFocus = null;

    function isOpen() {
        return !dialog.hidden;
    }

    function open() {
        if (isOpen()) return;
        lastFocus = document.activeElement;
        dialog.hidden = false;
        backdrop.hidden = false;
        document.body.style.overflow = 'hidden';
        dialog.querySelector('[data-observer-guide-close].app-btn-primary')?.focus();
    }

    async function persist() {
        const body = new FormData();
        body.append('ne_plus_afficher', checkbox.checked ? '1' : '0');
        try {
            await fetch(dialog.dataset.markUrl, {
                method: 'POST',
                body,
                headers: {
                    'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '',
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });
        } catch (error) {
            console.warn("Enregistrement de la préférence du guide impossible :", error);
        }
    }

    function close() {
        if (!isOpen()) return;
        dialog.hidden = true;
        backdrop.hidden = true;
        document.body.style.overflow = '';
        persist();
        if (lastFocus && lastFocus.isConnected) lastFocus.focus();
    }

    dialog.addEventListener('click', event => {
        if (event.target === dialog || event.target.closest('[data-observer-guide-close]')) close();
    });

    document.addEventListener('keydown', event => {
        if (!isOpen()) return;
        if (event.key === 'Escape') {
            close();
        } else if (event.key === 'Tab') {
            const items = [...dialog.querySelectorAll(focusable)];
            const first = items[0];
            const last = items[items.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
    });

    // Le lien du menu vit hors du dialogue : délégation pour survivre aux échanges HTMX.
    document.addEventListener('click', event => {
        const trigger = event.target.closest('[data-observer-guide-open]');
        if (!trigger) return;
        event.preventDefault();
        open();
    });

    if (dialog.dataset.autoOpen === 'true') {
        const notice = document.getElementById('versionNotice');
        if (!notice) {
            open();
        } else {
            // Un seul dialogue à la fois : on attend la fermeture de la notice de version.
            const observer = new MutationObserver(() => {
                if (!notice.isConnected) {
                    observer.disconnect();
                    open();
                }
            });
            observer.observe(document.body, { childList: true, subtree: true });
        }
    }
}());
