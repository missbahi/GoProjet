(function() {
    'use strict';

    if (window.__utilisateursInitialized) return;
    window.__utilisateursInitialized = true;

    function closeUserModal() {
        const dialog = document.getElementById('user-management-dialog');
        if (dialog?.open) dialog.close();
    }

    document.addEventListener('click', function (e) {
        if (!e.target.closest('[data-user-modal-close]')) return;
        e.preventDefault();
        e.stopImmediatePropagation();
        closeUserModal();
    }, true);

    document.addEventListener('close', function (e) {
        if (e.target.id !== 'user-management-dialog') return;
        document.getElementById('user-modal-content')?.replaceChildren();
    }, true);

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && document.getElementById('user-management-dialog')?.open) {
            e.preventDefault();
            closeUserModal();
        }
    });

    document.addEventListener('click', function (e) {
        const dialog = document.getElementById('user-management-dialog');
        if (e.target !== dialog) return;
        const bounds = dialog.getBoundingClientRect();
        if (e.clientX < bounds.left || e.clientX > bounds.right
            || e.clientY < bounds.top || e.clientY > bounds.bottom) closeUserModal();
    });

    document.body.addEventListener('htmx:beforeSwap', function (e) {
        if (e.detail.target.id === 'user-modal-content' && e.detail.xhr.status === 400) {
            e.detail.shouldSwap = true;
            e.detail.isError = false;
        }
    });

    document.body.addEventListener('htmx:afterSwap', function (e) {
        if (e.detail.target.id !== 'user-modal-content') return;
        const dialog = document.getElementById('user-management-dialog');
        if (dialog && !dialog.open) dialog.showModal();
        dialog?.querySelector('input:not([type="hidden"]), select, textarea')?.focus();
    });

    document.body.addEventListener('htmx:beforeCleanupElement', function (e) {
        if (e.detail.elt.id === 'user-management-dialog') closeUserModal();
    });

    document.body.addEventListener('userModalSaved', function (e) {
        closeUserModal();
        window.showSuccessMessage?.(e.detail.message);
        document.body.dispatchEvent(new CustomEvent('refreshListeUtilisateurs'));
    });

    // ============================================================
    // Log après swap HTMX (utile pour debug)
    // ============================================================
    document.body.addEventListener('htmx:afterSwap', function(e) {
        if (e.target.id === 'liste-utilisateurs-container') {
            // console.log('[utilisateurs] Liste rafraîchie');
        }
    });

    // ============================================================
    // Réagir aux messages de succès (HX-Trigger)
    // ============================================================
    document.body.addEventListener('refreshListeUtilisateurs', function() {
        const container = document.getElementById('liste-utilisateurs-container');
        if (container && window.htmx) {
            const params = new URLSearchParams(window.location.search);
            const search = document.getElementById('search-utilisateurs');
            const role = document.querySelector('select[name="role"]');
            if (search) params.set('search', search.value);
            if (role) params.set('role', role.value);
            const page = container.querySelector('[data-user-list-page]')?.dataset.userListPage;
            if (page) params.set('page', page);
            const url = new URL(search.getAttribute('hx-get'), window.location.origin);
            url.search = params.toString();
            htmx.ajax('GET', url.pathname + url.search, {
                target: '#liste-utilisateurs-container',
                swap: 'innerHTML',
            }).catch(error => {
                console.error('[utilisateurs] Actualisation de la liste échouée', error);
                window.showErrorMessage?.("Impossible d'actualiser la liste des utilisateurs.");
            });
        }
    });
    document.addEventListener('click', function(e) {
        if (e.target.closest('#select-all-projets')) {
            e.target.closest('form').querySelectorAll('input[name="projets"]').forEach(cb => cb.checked = true);
        }
        if (e.target.closest('#deselect-all-projets')) {
            e.target.closest('form').querySelectorAll('input[name="projets"]').forEach(cb => cb.checked = false);
        }
    });
})();