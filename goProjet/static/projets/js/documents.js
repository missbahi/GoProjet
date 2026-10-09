/* static/projets/js/documents.js */
(function () {
    'use strict';

    if (window.__documentsInitialized) return;
    window.__documentsInitialized = true;

    console.log('[documents.js] Initialized');

    // ═══════════════════════════════════════════════════════════
    // ⚡ DÉLÉGATION GLOBALE (attachée UNE SEULE FOIS)
    // ═══════════════════════════════════════════════════════════

    // --- 1. Fichier sélectionné : affichage nom + taille ---
    document.addEventListener('change', function (e) {
        if (e.target.id !== 'id_fichier') return;

        const file = e.target.files[0];
        const labelEl    = document.getElementById('doc-file-picker-label');
        const feedbackEl = document.getElementById('doc-file-feedback');
        const nameEl     = document.getElementById('doc-file-name');
        const sizeEl     = document.getElementById('doc-file-size');

        if (!file) {
            if (labelEl)    labelEl.textContent = 'Choisir un fichier…';
            if (feedbackEl) feedbackEl.classList.add('hidden');
            return;
        }

        if (labelEl) {
            labelEl.textContent = file.name.length > 35
                ? file.name.substring(0, 32) + '…'
                : file.name;
        }
        if (nameEl) nameEl.textContent = file.name;

        if (sizeEl) {
            const sizeKo = file.size / 1024;
            const sizeMo = sizeKo / 1024;
            sizeEl.textContent = sizeMo >= 1
                ? `(${sizeMo.toFixed(2)} Mo)`
                : `(${sizeKo.toFixed(0)} Ko)`;
        }
        if (feedbackEl) feedbackEl.classList.remove('hidden');
    });

    // --- 2. Toggle panneau d'ajout ---
    document.addEventListener('click', function (e) {
        if (e.target.closest('#doc-toggle-add')) {
            e.preventDefault();
            toggleAddPanel();
            return;
        }
        if (e.target.closest('#doc-close-add') || e.target.closest('#doc-cancel-add')) {
            e.preventDefault();
            closeAddPanel();
        }
    });

    // --- 3. Suppression AJAX ---
    document.addEventListener('click', async function (e) {
        const btn = e.target.closest('.doc-delete-btn');
        if (!btn) return;

        e.preventDefault();
        const docId = btn.dataset.documentId;
        const docNom = btn.dataset.documentNom || 'ce document';

        if (!confirm(`Supprimer « ${docNom} » ?`)) return;

        try {
            const projetId = window.location.pathname.match(/projet\/(\d+)/)?.[1];
            if (!projetId) throw new Error('Projet introuvable.');

            const res = await fetch(`/projet/${projetId}/documents/supprimer/${docId}/`, {
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
            if (!data.success) throw new Error(data.message);

            showSuccessMessage(data.message || 'Document supprimé.');
            reloadDocumentsContent();
        } catch (err) {
            console.error('[documents] delete:', err);
            showErrorMessage(err.message || 'Erreur lors de la suppression.');
        }
    });

    // --- 4. Soumission AJAX du formulaire d'ajout ---
    document.addEventListener('submit', async function (e) {
        const form = e.target.closest('#documentAddForm');
        if (!form) return;

        e.preventDefault();

        const submitBtn = form.querySelector('button[type="submit"]');
        const originalHtml = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Envoi...';

        try {
            const formData = new FormData(form);
            const res = await fetch(form.action, {
                method: 'POST',
                body: formData,
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

            showSuccessMessage(data.message || 'Document ajouté avec succès.');
            form.reset();

            // Reset du picker
            const labelEl = document.getElementById('doc-file-picker-label');
            const feedbackEl = document.getElementById('doc-file-feedback');
            if (labelEl) labelEl.textContent = 'Choisir un fichier…';
            if (feedbackEl) feedbackEl.classList.add('hidden');

            closeAddPanel();
            reloadDocumentsContent();
        } catch (err) {
            console.error('[documents] add:', err);
            showErrorMessage(err.message || 'Erreur lors de l\'ajout.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHtml;
        }
    });

    // ═══════════════════════════════════════════════════════════
    // HELPERS
    // ═══════════════════════════════════════════════════════════

    function toggleAddPanel() {
        const panel = document.getElementById('doc-add-panel');
        if (!panel) return;
        if (panel.classList.contains('open')) closeAddPanel();
        else openAddPanel();
    }

    function openAddPanel() {
        const panel = document.getElementById('doc-add-panel');
        const toggleBtn = document.getElementById('doc-toggle-add');
        if (!panel) return;

        panel.classList.add('open');
        toggleBtn?.setAttribute('aria-expanded', 'true');

        try { sessionStorage.setItem('doc-add-open', '1'); } catch (e) {}

        setTimeout(() => {
            document.getElementById('id_type_document')?.focus();
        }, 400);
    }

    function closeAddPanel() {
        const panel = document.getElementById('doc-add-panel');
        const toggleBtn = document.getElementById('doc-toggle-add');
        if (!panel) return;

        panel.classList.remove('open');
        toggleBtn?.setAttribute('aria-expanded', 'false');

        try { sessionStorage.removeItem('doc-add-open'); } catch (e) {}

        setTimeout(() => {
            toggleBtn?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 200);
    }

    function reloadDocumentsContent() {
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

    // ═══════════════════════════════════════════════════════════
    // INIT après swap : restaurer l'état du panneau
    // ═══════════════════════════════════════════════════════════
    function initAfterSwap() {
        try {
            if (sessionStorage.getItem('doc-add-open') === '1') {
                openAddPanel();
            }
        } catch (e) {}
    }

    document.addEventListener('DOMContentLoaded', initAfterSwap);

    document.body.addEventListener('htmx:afterSwap', function (e) {
        if (e.detail.target.id === 'main-content') {
            initAfterSwap();
        }
    });

})();