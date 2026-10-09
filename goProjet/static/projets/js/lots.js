/* static/projets/js/lots.js */
(function () {
    'use strict';

    if (window.__lotsInitialized) return;
    window.__lotsInitialized = true;

    console.log('[lots.js] Initialized');

    // ═══════════════════════════════════════════════════════════
    // TOGGLE PANNEAU AJOUT
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('click', function (e) {
        if (e.target.closest('#lot-toggle-add')) {
            e.preventDefault();
            toggleAddPanel();
            return;
        }
        if (e.target.closest('#lot-close-add') || e.target.closest('#lot-cancel-add')) {
            e.preventDefault();
            closeAddPanel();
        }
    });

    // ═══════════════════════════════════════════════════════════
    // APERÇU BORDEREAU
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('#lot-apercu-btn');
        if (!btn) return;
        e.preventDefault();
        const url = btn.dataset.url;
        if (url) window.open(url, '_blank', 'noopener');
    });

    // ═══════════════════════════════════════════════════════════
    // AJOUT LOT (AJAX)
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('submit', async function (e) {
        const form = e.target.closest('#lotAddForm');
        if (!form) return;
        e.preventDefault();

        const submitBtn = form.querySelector('button[type="submit"]');
        const originalHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Envoi...';

        try {
            const res = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
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
            if (!data.success) throw new Error(data.message || 'Erreur lors de l\'ajout.');

            showSuccessMessage(data.message || 'Lot ajouté.');
            form.reset();
            closeAddPanel();
            reloadContent();
        } catch (err) {
            console.error('[lots] add:', err);
            showErrorMessage(err.message || 'Erreur lors de l\'ajout.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        }
    });

    // ═══════════════════════════════════════════════════════════
    // MODIFIER LOT (modal + AJAX)
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.lot-edit-btn');
        if (!btn) return;
        e.preventDefault();

        document.getElementById('edit_lot_id').value = btn.dataset.lotId;
        document.getElementById('edit_lot_nom').value = btn.dataset.lotNom || '';
        document.getElementById('edit_lot_description').value = btn.dataset.lotDescription || '';
        document.getElementById('edit_lot_taux_tva').value = btn.dataset.lotTauxTva || '';

        document.getElementById('lot-edit-modal').style.display = 'block';
        document.getElementById('modalBackdrop')?.style.setProperty('display', 'block');
    });

    document.addEventListener('submit', async function (e) {
        const form = e.target.closest('#lotEditForm');
        if (!form) return;
        e.preventDefault();

        const lotId = document.getElementById('edit_lot_id').value;
        const projetId = window.location.pathname.match(/projet\/(\d+)/)?.[1];

        const submitBtn = form.querySelector('button[type="submit"]');
        const originalHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Envoi...';

        try {
            const res = await fetch(`/projet/${projetId}/lot/${lotId}/modifier/`, {
                method: 'POST',
                body: new FormData(form),
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
            if (!data.success) throw new Error(data.message || 'Erreur lors de la modification.');

            showSuccessMessage(data.message || 'Lot modifié.');
            closeEditModal();
            reloadContent();
        } catch (err) {
            console.error('[lots] edit:', err);
            showErrorMessage(err.message || 'Erreur lors de la modification.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        }
    });

    // ═══════════════════════════════════════════════════════════
    // APERÇU BORDEREAU — avec overlay de chargement
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('#lot-apercu-btn');
        if (!btn) return;
        e.preventDefault();

        const url = btn.dataset.url;
        if (!url) return;

        // 1. Afficher l'overlay
        const overlay = document.getElementById('lot-loading-overlay');
        if (overlay) overlay.classList.add('visible');

        // 2. Ouvrir le nouvel onglet
        const newTab = window.open(url, '_blank', 'noopener');

        // 3. Fermer l'overlay après un délai OU au retour de focus
        let closed = false;
        const hide = () => {
            if (closed) return;
            closed = true;
            if (overlay) overlay.classList.remove('visible');
        };

        // Fallback : fermer après 4 secondes max
        setTimeout(hide, 4000);

        // Fermer dès que l'utilisateur revient sur l'onglet (nouvel onglet en avant)
        const onFocus = () => {
            window.removeEventListener('focus', onFocus);
            setTimeout(hide, 800); // petit délai pour laisser la transition finir
        };
        window.addEventListener('focus', onFocus);

        // Si window.open est bloqué par le navigateur → alerte
        if (!newTab) {
            hide();
            showWarningMessage("Veuillez autoriser les pop-ups pour voir l'aperçu.");
        }
    });

    // ═══════════════════════════════════════════════════════════
    // FERMETURE DU MODAL — Croix, Annuler, Échap, Backdrop
    // ═══════════════════════════════════════════════════════════

    // 1. Clic sur croix / Annuler / backdrop
    document.addEventListener('click', function (e) {
        // Bouton fermeture
        if (e.target.closest('#lot-edit-modal [data-modal-close]')) {
            e.preventDefault();
            closeEditModal();
            return;
        }
        // Clic hors du modal (backdrop)
        const modal = document.getElementById('lot-edit-modal');
        if (modal && modal.style.display === 'block' && e.target === modal) {
            closeEditModal();
        }
    });

    // 2. Échap
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            const modal = document.getElementById('lot-edit-modal');
            if (modal && modal.style.display === 'block') {
                closeEditModal();
            }
        }
    });

    // ═══════════════════════════════════════════════════════════
    // SUPPRIMER LOT (AJAX)
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('click', async function (e) {
        const btn = e.target.closest('.lot-delete-btn');
        if (!btn) return;
        e.preventDefault();

        const lotId = btn.dataset.lotId;
        const lotNom = btn.dataset.lotNom || 'ce lot';
        const nbLignes = btn.dataset.lotLignes || '0';

        const msg = `⚠️ Attention : la suppression du lot « ${lotNom} » supprimera également ${nbLignes} ligne(s) de bordereau.\n\nVoulez-vous continuer ?`;
        if (!confirm(msg)) return;

        try {
            const projetId = window.location.pathname.match(/projet\/(\d+)/)?.[1];
            const res = await fetch(`/projet/${projetId}/lot/${lotId}/supprimer/`, {
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

            showSuccessMessage(data.message || 'Lot supprimé.');
            reloadContent();
        } catch (err) {
            console.error('[lots] delete:', err);
            showErrorMessage(err.message || 'Erreur lors de la suppression.');
        }
    });

    // ═══════════════════════════════════════════════════════════
    // HELPERS
    // ═══════════════════════════════════════════════════════════
    function toggleAddPanel() {
        const panel = document.getElementById('lot-add-panel');
        if (!panel) return;
        if (panel.classList.contains('open')) closeAddPanel();
        else openAddPanel();
    }

    function openAddPanel() {
        const panel = document.getElementById('lot-add-panel');
        const toggleBtn = document.getElementById('lot-toggle-add');
        if (!panel) return;
        panel.classList.add('open');
        toggleBtn?.setAttribute('aria-expanded', 'true');
        setTimeout(() => document.getElementById('id_lot_nom')?.focus(), 400);
    }

    function closeAddPanel() {
        const panel = document.getElementById('lot-add-panel');
        const toggleBtn = document.getElementById('lot-toggle-add');
        if (!panel) return;
        panel.classList.remove('open');
        toggleBtn?.setAttribute('aria-expanded', 'false');
        setTimeout(() => {
            toggleBtn?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 200);
    }

    function closeEditModal() {
        const modal = document.getElementById('lot-edit-modal');
        if (modal) modal.style.display = 'none';
        const backdrop = document.getElementById('modalBackdrop');
        if (backdrop) backdrop.style.display = 'none';

        // Reset du formulaire
        const form = document.getElementById('lotEditForm');
        if (form) form.reset();
    }
    
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