/* static/projets/js/toast.js
 * Système de toasts global (utilisable sur toutes les pages)
 */
(function () {
    'use strict';

    function getOrCreateToastContainer() {
        let container = document.getElementById('toast-container');
        if (container) return container;

        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = `
            position: fixed;
            bottom: 1.5rem;
            right: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            z-index: 9999;
            pointer-events: none;
            max-width: calc(100vw - 3rem);
        `;
        document.body.appendChild(container);
        return container;
    }

    function showToast(message, type = 'info', duration = 3500) {
        const container = getOrCreateToastContainer();
        const icons = {
            success: 'fa-check-circle',
            error:   'fa-circle-exclamation',
            warning: 'fa-triangle-exclamation',
            info:    'fa-circle-info',
        };

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.style.pointerEvents = 'auto';
        toast.innerHTML = `
            <i class="fas ${icons[type] || icons.info}"></i>
            <span class="toast-message">${message}</span>
            <button type="button" class="toast-close" aria-label="Fermer">
                <i class="fas fa-times"></i>
            </button>
        `;

        toast.querySelector('.toast-close').addEventListener('click', () => hideToast(toast));
        container.appendChild(toast);
        toast._toastTimer = setTimeout(() => hideToast(toast), duration);
    }

    function hideToast(toast) {
        if (!toast || toast._hiding) return;
        toast._hiding = true;
        clearTimeout(toast._toastTimer);

        const remove = () => {
            if (toast.parentElement) toast.remove();
            const container = document.getElementById('toast-container');
            if (container && container.children.length === 0) container.remove();
        };

        toast.classList.add('toast-hiding');
        const fallback = setTimeout(remove, 350);
        toast.addEventListener('animationend', () => {
            clearTimeout(fallback);
            remove();
        }, { once: true });
    }

    /* ── API globale ── */
    window.showToast          = showToast;
    window.showSuccessMessage = (msg) => showToast(msg, 'success');
    window.showErrorMessage   = (msg) => showToast(msg, 'error', 5000);
    window.showWarningMessage = (msg) => showToast(msg, 'warning', 4500);
    window.showInfoMessage    = (msg) => showToast(msg, 'info');
})();