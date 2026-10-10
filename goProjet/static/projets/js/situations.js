/* static/projets/js/situations.js */
(function () {
    'use strict';

    if (window.__situationsInitialized) return;
    window.__situationsInitialized = true;

    console.log('[situations.js] Initialized');

    // ═══════════════════════════════════════════════════════════
    // SUPPRESSION AJAX
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('click', async function (e) {
        const btn = e.target.closest('.situation-delete-btn');
        if (!btn) return;
        e.preventDefault();

        const situationId = btn.dataset.situationId;
        const periode = btn.dataset.situationPeriode || '';

        if (!confirm(`Supprimer la situation ${periode} ?\n\nToutes les dépenses, recettes, stocks et documents associés seront supprimés.`)) return;

        try {
            const projetId = window.location.pathname.match(/projet\/(\d+)/)?.[1];
            if (!projetId) throw new Error('Projet introuvable.');

            const res = await fetch(`/projet/${projetId}/situations-mensuelles/${situationId}/supprimer/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken(),
                },
            });

            const ct = res.headers.get('content-type') || '';
            if (!ct.includes('application/json')) {
                throw new Error(`Réponse inattendue (${res.status}).`);
            }

            const data = await res.json();
            if (!data.success) throw new Error(data.message || 'Erreur lors de la suppression.');

            showSuccessMessage(data.message || 'Situation supprimée.');
            reloadContent();
        } catch (err) {
            console.error('[situations] delete:', err);
            showErrorMessage(err.message || 'Erreur lors de la suppression.');
        }
    });

    // ═══════════════════════════════════════════════════════════
    // HELPERS
    // ═══════════════════════════════════════════════════════════
    function reloadContent() {
        if (window.htmx) {
            htmx.ajax('GET', window.location.href, {
                target: '#main-content',
                swap: 'innerHTML',
            });
        } else {
            window.location.reload();
        }
    }

    function getCsrfToken() {
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

})();