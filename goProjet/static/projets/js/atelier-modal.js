/* static/projets/js/atelier-modal.js */
(function () {
    'use strict';

    if (window.AtelierModal) return;

    let CONFIG = { addUrl: null, editTemplate: null, deleteTemplate: null };

    // ------------------------------------------------------------
    // Utils
    // ------------------------------------------------------------
    function refreshMainContent() {
        if (typeof window.refreshMainContent === 'function') {
            window.refreshMainContent();
        } else {
            window.location.reload();
        }
    }

    function chargerConfig() {
        const el = document.getElementById('atelier-config');
        if (!el) return false;
        CONFIG.addUrl = el.dataset.addUrl || null;
        CONFIG.editTemplate = el.dataset.editTemplate || null;
        CONFIG.deleteTemplate = el.dataset.deleteTemplate || null;
        return true;
    }

    function construireEditUrl(id) {
        if (!CONFIG.editTemplate) return null;
        return CONFIG.editTemplate.replace('/0/', `/${id}/`);
    }

    function construireDeleteUrl(id) {
        if (!CONFIG.deleteTemplate) return null;
        return CONFIG.deleteTemplate.replace('/0/', `/${id}/`);
    }

    function getCsrfToken() {
        const input = document.querySelector('#addAtelierForm [name=csrfmiddlewaretoken]')
                   || document.querySelector('[name=csrfmiddlewaretoken]');
        if (input) return input.value;
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : '';
    }

    // ------------------------------------------------------------
    // Modals
    // ------------------------------------------------------------
    function openAddAtelierModal() {
        const m = document.getElementById('addAtelierModal');
        const b = document.getElementById('modalBackdrop');
        if (m) m.style.display = 'block';
        if (b) b.style.display = 'block';
    }

    function openEditAtelierModal(id, code, libelle, description, actif) {
        const setVal = (elId, v) => { const el = document.getElementById(elId); if (el) el.value = v; };
        setVal('editAtelierId', id);
        setVal('editAtelierCode', code);
        setVal('editAtelierLibelle', libelle);
        setVal('editAtelierDescription', description || '');
        const cb = document.getElementById('editAtelierActif');
        if (cb) cb.checked = actif === 'true';
        const m = document.getElementById('editAtelierModal');
        const b = document.getElementById('modalBackdrop');
        if (m) m.style.display = 'block';
        if (b) b.style.display = 'block';
    }

    function closeAddAtelierModal() {
        const m = document.getElementById('addAtelierModal');
        const b = document.getElementById('modalBackdrop');
        const f = document.getElementById('addAtelierForm');
        if (m) m.style.display = 'none';
        if (b) b.style.display = 'none';
        if (f) { f.classList.remove('was-validated'); f.reset(); }
        hideAllErrors('addAtelierForm');
    }

    function closeEditAtelierModal() {
        const m = document.getElementById('editAtelierModal');
        const b = document.getElementById('modalBackdrop');
        const f = document.getElementById('editAtelierForm');
        if (m) m.style.display = 'none';
        if (b) b.style.display = 'none';
        if (f) f.classList.remove('was-validated');
        hideAllErrors('editAtelierForm');
    }

    function closeAllAtelierModals() {
        closeAddAtelierModal();
        closeEditAtelierModal();
    }

    // ------------------------------------------------------------
    // Erreurs / messages
    // ------------------------------------------------------------
    function hideAllErrors(formId) {
        const root = document.getElementById(formId);
        if (!root) return;
        root.querySelectorAll('.invalid-feedback').forEach(el => el.classList.add('hidden'));
        root.querySelectorAll('input, textarea').forEach(el => el.classList.remove('border-red-500'));
    }

    function showFieldError(formId, fieldName) {
        const input = document.querySelector(`#${formId} [name="${fieldName}"]`);
        const feedback = document.querySelector(`#${formId} [data-error-for="${fieldName}"]`);
        if (input) input.classList.add('border-red-500');
        if (feedback) feedback.classList.remove('hidden');
    }

    function showServerErrors(formId, errors) {
        hideAllErrors(formId);
        if (!errors) return;
        Object.keys(errors).forEach(field => showFieldError(formId, field));
    }

    function showSuccessMessage(message) {
        if (typeof window.showSuccessMessage === 'function') return window.showSuccessMessage(message);
        const el = document.createElement('div');
        el.className = 'fixed top-4 left-1/2 transform -translate-x-1/2 z-50 p-4 bg-green-800 text-green-200 rounded-lg shadow-lg max-w-sm';
        el.innerHTML = `<i class="fa-solid fa-check mr-2"></i> ${message}`;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 3000);
    }

    function showErrorMessage(message) {
        if (typeof window.showErrorMessage === 'function') return window.showErrorMessage(message);
        const el = document.createElement('div');
        el.className = 'fixed top-4 left-1/2 transform -translate-x-1/2 z-50 p-4 bg-red-800 text-red-100 rounded-lg shadow-lg max-w-sm';
        el.innerHTML = `<i class="fa-solid fa-triangle-exclamation mr-2"></i> ${message}`;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 5000);
    }

    // ------------------------------------------------------------
    // Handlers métier
    // ------------------------------------------------------------
    function handleDeleteAtelier(id) {
        chargerConfig();
        const url = construireDeleteUrl(id);
        if (!url) { showErrorMessage("URL de suppression non configurée."); return; }
        if (!confirm('Supprimer cet atelier ? Cette action est irréversible.')) return;

        fetch(url, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCsrfToken() },
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showSuccessMessage(data.message || 'Atelier supprimé.');
                setTimeout(() => refreshMainContent(), 800);
            } else {
                showErrorMessage(data.message || 'Erreur lors de la suppression.');
            }
        })
        .catch(err => {
            console.error('Delete atelier error:', err);
            showErrorMessage('Une erreur est survenue lors de la suppression.');
        });
    }

    function handleAddAtelier(form) {
        chargerConfig();
        const codeInput = document.getElementById('addAtelierCode');
        const libelleInput = document.getElementById('addAtelierLibelle');
        hideAllErrors('addAtelierForm');

        let isValid = true;
        if (!codeInput.value.trim()) { showFieldError('addAtelierForm', 'code'); isValid = false; }
        if (!libelleInput.value.trim()) { showFieldError('addAtelierForm', 'libelle'); isValid = false; }
        if (!isValid) return;

        if (!CONFIG.addUrl) { showErrorMessage("URL d'ajout non configurée."); return; }

        fetch(CONFIG.addUrl, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCsrfToken() },
        })
        .then(async r => {
            const ct = r.headers.get('content-type') || '';
            if (!ct.includes('application/json')) {
                const t = await r.text();
                console.error('Server returned non-JSON:', r.status, t);
                throw new Error(`HTTP ${r.status}`);
            }
            const data = await r.json();
            if (!r.ok) { const e = new Error('Validation échouée'); e.data = data; throw e; }
            return data;
        })
        .then(data => {
            if (data.success) {
                closeAddAtelierModal();
                showSuccessMessage(data.message);
                setTimeout(() => refreshMainContent(), 1000);
            } else {
                showServerErrors('addAtelierForm', data.errors);
                showErrorMessage(data.message || 'Veuillez corriger les erreurs.');
            }
        })
        .catch(err => {
            console.error('Add atelier error:', err);
            if (err.data && err.data.errors) {
                showServerErrors('addAtelierForm', err.data.errors);
                showErrorMessage(err.data.message || 'Veuillez corriger les erreurs.');
            } else {
                showErrorMessage("Erreur lors de l'ajout.");
            }
        });
    }

    function handleEditAtelier(form) {
        chargerConfig();
        const codeInput = document.getElementById('editAtelierCode');
        const libelleInput = document.getElementById('editAtelierLibelle');
        hideAllErrors('editAtelierForm');

        let isValid = true;
        if (!codeInput.value.trim()) { showFieldError('editAtelierForm', 'code'); isValid = false; }
        if (!libelleInput.value.trim()) { showFieldError('editAtelierForm', 'libelle'); isValid = false; }
        if (!isValid) return;

        const id = document.getElementById('editAtelierId').value;
        const url = construireEditUrl(id);
        if (!url) { showErrorMessage("URL d'édition non configurée."); return; }

        fetch(url, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCsrfToken() },
        })
        .then(async r => {
            const ct = r.headers.get('content-type') || '';
            if (!ct.includes('application/json')) {
                const t = await r.text();
                console.error('Server returned non-JSON:', r.status, t);
                throw new Error(`HTTP ${r.status}`);
            }
            const data = await r.json();
            if (!r.ok) { const e = new Error('Validation échouée'); e.data = data; throw e; }
            return data;
        })
        .then(data => {
            if (data.success) {
                closeEditAtelierModal();
                showSuccessMessage(data.message);
                setTimeout(() => refreshMainContent(), 1000);
            } else {
                showServerErrors('editAtelierForm', data.errors);
                showErrorMessage(data.message || 'Veuillez corriger les erreurs.');
            }
        })
        .catch(err => {
            console.error('Edit atelier error:', err);
            if (err.data && err.data.errors) {
                showServerErrors('editAtelierForm', err.data.errors);
                showErrorMessage(err.data.message || 'Veuillez corriger les erreurs.');
            } else {
                showErrorMessage("Erreur lors de la modification.");
            }
        });
    }

    // ============================================================
    // ⚡ Délégation globale — attachée UNE fois, survit aux swaps
    // ============================================================
    document.addEventListener('click', function (e) {
        if (e.target.closest('[data-add-atelier-button]')) {
            e.preventDefault();
            openAddAtelierModal();
            return;
        }

        const editBtn = e.target.closest('[data-edit-atelier-button]');
        if (editBtn) {
            e.preventDefault();
            openEditAtelierModal(
                editBtn.getAttribute('data-id'),
                editBtn.getAttribute('data-code'),
                editBtn.getAttribute('data-libelle'),
                editBtn.getAttribute('data-description'),
                editBtn.getAttribute('data-actif'),
            );
            return;
        }

        const delLink = e.target.closest('[data-delete-atelier-link], a[href*="/ateliers/"][href*="/supprimer/"]');
        if (delLink) {
            e.preventDefault();
            let id = delLink.dataset && delLink.dataset.id ? delLink.dataset.id : null;
            if (!id) {
                const m = delLink.href.match(/\/ateliers\/(\d+)\/supprimer\//);
                if (m) id = m[1];
            }
            if (!id) { console.warn('[Atelier] ID suppression introuvable', delLink.href); return; }
            handleDeleteAtelier(id);
            return;
        }

        const closeBtn = e.target.closest('[data-close-modal]');
        if (closeBtn) {
            e.preventDefault();
            const cible = closeBtn.getAttribute('data-close-modal');
            if (cible === 'add-atelier') closeAddAtelierModal();
            else if (cible === 'edit-atelier') closeEditAtelierModal();
            else if (cible === 'all') closeAllAtelierModals();
            return;
        }
    });

    document.addEventListener('submit', function (e) {
        if (e.target.matches('form#addAtelierForm')) {
            e.preventDefault();
            handleAddAtelier(e.target);
        } else if (e.target.matches('form#editAtelierForm')) {
            e.preventDefault();
            handleEditAtelier(e.target);
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeAllAtelierModals();
    });

    // ------------------------------------------------------------
    // API publique
    // ------------------------------------------------------------
    window.AtelierModal = {
        openAdd: openAddAtelierModal,
        openEdit: openEditAtelierModal,
        closeAdd: closeAddAtelierModal,
        deleteById: handleDeleteAtelier,
        handleAdd: handleAddAtelier,
        handleEdit: handleEditAtelier,
        closeEdit: closeEditAtelierModal,
        closeAll: closeAllAtelierModals,
    };
})();