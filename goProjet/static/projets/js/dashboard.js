/* static/projets/js/dashboard.js */
(function () {
    'use strict';

    const container = () => document.getElementById('dashboard-modal-container');

    /* ═══════════════════════════════════════════════════════════
       OUVERTURE / FERMETURE DE LA MODAL
       ═══════════════════════════════════════════════════════════ */

    window.dashboardOpenModal = async function (url) {
        const el = container();
        if (!el) return console.warn('[dashboard] modal container absent');

        try {
            const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const html = await res.text();
            el.innerHTML = html;
            el.classList.remove('hidden');
        } catch (err) {
            console.error('[dashboard] open modal:', err);
            window.showErrorMessage?.('Impossible d\'ouvrir la modal.');
        }
    };

    window.dashboardCloseModal = function () {
        const el = container();
        if (!el) return;
        el.classList.add('hidden');
        el.innerHTML = '';
    };

    /* ═══════════════════════════════════════════════════════════
       SOUMISSION DU FORMULAIRE PROJET
       ═══════════════════════════════════════════════════════════ */

    window.dashboardSaveProjet = async function () {
        const form = document.getElementById('projetForm');
        const submitBtn = document.getElementById('submitProjetBtn');
        if (!form) return;

        submitBtn?.setAttribute('disabled', 'disabled');
        submitBtn?.classList.add('opacity-50', 'cursor-not-allowed');

        try {
            const res = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });

            if (!res.ok) {
                const txt = await res.text();
                throw new Error(txt || `HTTP ${res.status}`);
            }

            window.dashboardCloseModal();
            window.showSuccessMessage?.('Projet mis à jour avec succès');
            setTimeout(() => window.location.reload(), 1200);
        } catch (err) {
            console.error('[dashboard] save projet:', err);
            window.showErrorMessage?.('Erreur : ' + err.message);
        } finally {
            submitBtn?.removeAttribute('disabled');
            submitBtn?.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    };

    /* ═══════════════════════════════════════════════════════════
       DELEGATION GLOBALE (une seule fois)
       ═══════════════════════════════════════════════════════════ */

    document.body.addEventListener('click', (e) => {
        const el = container();
        if (!el) return;

        // Clic sur le fond ou sur le modal-backdrop → fermeture
        if (e.target === el || e.target.id === 'projetModal') {
            window.dashboardCloseModal();
            return;
        }

        // Clic sur le bouton "Enregistrer" (dans la modal)
        if (e.target.closest('#submitProjetBtn')) {
            e.preventDefault();
            window.dashboardSaveProjet();
            return;
        }
    });

    // Échap ferme la modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !container()?.classList.contains('hidden')) {
            window.dashboardCloseModal();
        }
    });

})();