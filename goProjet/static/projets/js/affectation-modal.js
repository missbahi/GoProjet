/* static/projets/js/affectation-modal.js */
(function () {
    'use strict';

    if (window.AffectationModal) return;

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
        const el = document.getElementById('affectation-config');
        if (!el) return false;
        CONFIG.addUrl = document.getElementById('addAffectationForm')?.getAttribute('action')
            || el.dataset.addUrl || el.dataset.addTemplate || null;
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
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.content;
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        if (input) return input.value;
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : '';
    }

    // ------------------------------------------------------------
    // Modals
    // ------------------------------------------------------------
    function openAddAffectationModal(atelierId, url) {
        const modal = document.getElementById('addAffectationModal');
        const backdrop = document.getElementById('modalBackdrop');
        if (!modal || !backdrop) return;
        chargerConfig();
        if (!url && atelierId) {
            const template = document.getElementById('affectation-config')?.dataset.addTemplate;
            if (template) url = template.replace('/0/', `/${atelierId}/`);
        }
        if (url) {
            CONFIG.addUrl = url;
            document.getElementById('addAffectationForm').setAttribute('action', url);
        }
        if (!CONFIG.addUrl || CONFIG.addUrl.includes('/0/')) {
            showErrorMessage("URL d'ajout non configurée.");
            return;
        }
        modal.style.display = 'block';
        backdrop.style.display = 'block';
        const d = document.getElementById('addDateDebut');
        if (d && !d.value) d.value = new Date().toISOString().split('T')[0];
    }

    function openEditAffectationModal(id, materielId, materielLabel, dateDebut, dateFin, commentaire) {
        const modal = document.getElementById('editAffectationModal');
        const backdrop = document.getElementById('modalBackdrop');
        if (!modal || !backdrop) return;
        const setVal = (elId, val) => { const el = document.getElementById(elId); if (el) el.value = val || ''; };
        setVal('editAffectationId', id);
        const option = Array.from(document.getElementById('editMaterielList')?.options || [])
            .find(item => item.dataset.id === String(materielId));
        if (option) materielLabel = option.value;
        setVal('editMaterielInput', materielLabel);
        setVal('editMateriel', materielId);
        const input = document.getElementById('editMaterielInput');
        if (input) {
            input.dataset.initialLabel = materielLabel;
            input.dataset.initialId = String(materielId);
        }
        setVal('editDateDebut', dateDebut);
        setVal('editDateFin', dateFin);
        setVal('editCommentaire', commentaire);
        hideAllErrors('editAffectationForm');
        modal.style.display = 'block';
        backdrop.style.display = 'block';
    }

    function closeAddAffectationModal() {
        const m = document.getElementById('addAffectationModal');
        const b = document.getElementById('modalBackdrop');
        const f = document.getElementById('addAffectationForm');
        if (m) m.style.display = 'none';
        if (b) b.style.display = 'none';
        if (f) f.reset();
        const i = document.getElementById('addMaterielInput'); if (i) i.value = '';
        const h = document.getElementById('addMateriel'); if (h) h.value = '';
        hideAllErrors('addAffectationForm');
    }

    function closeEditAffectationModal() {
        const m = document.getElementById('editAffectationModal');
        const b = document.getElementById('modalBackdrop');
        if (m) m.style.display = 'none';
        if (b) b.style.display = 'none';
        const i = document.getElementById('editMaterielInput'); if (i) i.value = '';
        const h = document.getElementById('editMateriel'); if (h) h.value = '';
        hideAllErrors('editAffectationForm');
    }

    function closeAllModals() {
        closeAddAffectationModal();
        closeEditAffectationModal();
    }

    // ------------------------------------------------------------
    // Datalist → hidden
    // ------------------------------------------------------------
    function syncMaterielIdFromInput(inputId, hiddenId) {
        const input = document.getElementById(inputId);
        const hidden = document.getElementById(hiddenId);
        if (!input || !hidden) return '';
        const valeur = input.value.trim();
        if (!valeur) { hidden.value = ''; return ''; }
        const datalist = document.getElementById(input.getAttribute('list'));
        if (!datalist) return '';
        const option = Array.from(datalist.options).find(o => o.value === valeur);
        hidden.value = option ? option.dataset.id : '';
        return hidden.value;
    }

    // ------------------------------------------------------------
    // Erreurs / messages
    // ------------------------------------------------------------
    function hideAllErrors(formId) {
        const root = document.getElementById(formId);
        if (!root) return;
        root.querySelectorAll('.invalid-feedback').forEach(el => el.classList.add('hidden'));
        root.querySelectorAll('input, select, textarea').forEach(el => el.classList.remove('border-red-500'));
        const summary = root.querySelector('[data-affectation-errors]');
        if (summary) {
            summary.hidden = true;
            summary.replaceChildren();
        }
        const addInput = document.getElementById('addMaterielInput');
        const editInput = document.getElementById('editMaterielInput');
        if (addInput) addInput.classList.remove('border-red-500');
        if (editInput) editInput.classList.remove('border-red-500');
    }

    function showFieldError(formId, fieldName, message) {
        const selector = fieldName === 'materiel'
            ? `#${formId === 'addAffectationForm' ? 'addMaterielInput' : 'editMaterielInput'}`
            : `#${formId} [name="${fieldName}"]`;
        const input = document.querySelector(selector);
        const feedback = document.querySelector(`#${formId} [data-error-for="${fieldName}"]`);
        if (input) input.classList.add('border-red-500');
        if (feedback) {
            if (message) feedback.textContent = message;
            feedback.classList.remove('hidden');
        }
        if (message) showFormError(formId, message);
    }

    function showFormError(formId, message) {
        const form = document.getElementById(formId);
        const summary = form?.querySelector('[data-affectation-errors]');
        if (!summary) {
            showErrorMessage(message);
            return;
        }
        const line = document.createElement('p');
        line.textContent = message;
        summary.appendChild(line);
        summary.hidden = false;
        summary.scrollIntoView({ block: 'nearest' });
    }

    function showServerErrors(formId, errors) {
        hideAllErrors(formId);
        if (!errors || !Object.keys(errors).length) {
            showFormError(formId, 'Veuillez corriger les erreurs du formulaire.');
            return;
        }
        Object.keys(errors).forEach(field => {
            const messages = errors[field].map(e => e.message || e).join(' ');
            showFieldError(formId, field, messages);
        });
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
    function handleAddAffectation(form) {
        chargerConfig();
        syncMaterielIdFromInput('addMaterielInput', 'addMateriel');
        const materielInput = document.getElementById('addMateriel');
        const dateDebutInput = document.getElementById('addDateDebut');
        hideAllErrors('addAffectationForm');

        let isValid = true;
        if (!materielInput || !materielInput.value) {
            showFieldError('addAffectationForm', 'materiel', 'Veuillez choisir un matériel.');
            isValid = false;
        }
        if (!dateDebutInput || !dateDebutInput.value) {
            showFieldError('addAffectationForm', 'date_debut', 'Veuillez saisir une date de début.');
            isValid = false;
        }
        if (!isValid) return;
        if (!CONFIG.addUrl) { showErrorMessage("URL d'ajout non configurée."); return; }

        fetch(CONFIG.addUrl, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCsrfToken() },
        })
        .then(async r => {
            const ct = r.headers.get('content-type') || '';
            if (!ct.includes('application/json')) throw new Error(`HTTP ${r.status}`);
            const data = await r.json();
            if (!r.ok) { const e = new Error('Validation échouée'); e.data = data; throw e; }
            return data;
        })
        .then(data => {
            if (data.success) {
                closeAddAffectationModal();
                showSuccessMessage(data.message);
                setTimeout(() => refreshMainContent(), 1000);
            } else {
                showServerErrors('addAffectationForm', data.errors);
                showErrorMessage(data.message || 'Veuillez corriger les erreurs.');
            }
        })
        .catch(err => {
            console.error('Add affectation error:', err);
            if (err.data && err.data.errors) {
                showServerErrors('addAffectationForm', err.data.errors);
                showErrorMessage(err.data.message || 'Veuillez corriger les erreurs.');
            } else {
                showErrorMessage("Erreur lors de l'affectation.");
            }
        });
    }

    function handleEditAffectation(form) {
        chargerConfig();
        const materielInput = document.getElementById('editMateriel');
        const materielVisible = document.getElementById('editMaterielInput');
        const dateDebutInput = document.getElementById('editDateDebut');

        if (materielInput && materielVisible) {
            if (materielVisible.value.trim() === materielVisible.dataset.initialLabel) {
                materielInput.value = materielVisible.dataset.initialId;
            } else {
                syncMaterielIdFromInput('editMaterielInput', 'editMateriel');
            }
        }

        hideAllErrors('editAffectationForm');

        let isValid = true;
        if (!materielInput || !materielInput.value) {
            showFieldError('editAffectationForm', 'materiel', 'Veuillez choisir un matériel.');
            isValid = false;
        }
        if (!dateDebutInput || !dateDebutInput.value) {
            showFieldError('editAffectationForm', 'date_debut', 'Veuillez saisir une date de début.');
            isValid = false;
        }
        if (!isValid) return;

        const id = document.getElementById('editAffectationId').value;
        const url = construireEditUrl(id);
        if (!url) { showFormError('editAffectationForm', "URL d'édition non configurée."); return; }

        const formData = new FormData(form);
        formData.set('materiel', materielInput.value);

        fetch(url, {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCsrfToken() },
        })
        .then(async r => {
            const ct = r.headers.get('content-type') || '';
            if (!ct.includes('application/json')) throw new Error(`HTTP ${r.status}`);
            const data = await r.json();
            if (!r.ok) { const e = new Error('Validation échouée'); e.data = data; throw e; }
            return data;
        })
        .then(data => {
            if (data.success) {
                closeEditAffectationModal();
                showSuccessMessage(data.message);
                setTimeout(() => refreshMainContent(), 1000);
            } else {
                showServerErrors('editAffectationForm', data.errors);
                showFormError('editAffectationForm', data.message || 'Veuillez corriger les erreurs.');
            }
        })
        .catch(err => {
            console.error('Edit affectation error:', err);
            if (err.data && err.data.errors) {
                showServerErrors('editAffectationForm', err.data.errors);
                showFormError('editAffectationForm', err.data.message || 'Veuillez corriger les erreurs.');
            } else {
                showFormError('editAffectationForm', `Erreur lors de la modification (${err.message}).`);
            }
        });
    }

    function handleDeleteAffectation(id) {
        chargerConfig();
        const url = construireDeleteUrl(id);
        if (!url) { showErrorMessage("URL de suppression non configurée."); return; }
        if (!confirm("Retirer ce matériel de l'atelier ?")) return;

        fetch(url, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCsrfToken() },
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showSuccessMessage(data.message || 'Affectation retirée.');
                setTimeout(() => refreshMainContent(), 800);
            } else {
                showErrorMessage(data.message || 'Erreur lors de la suppression.');
            }
        })
        .catch(err => {
            console.error('Delete affectation error:', err);
            showErrorMessage('Une erreur est survenue lors de la suppression.');
        });
    }

    // ------------------------------------------------------------
    // Auto-open ?edit=<id> (rejoué après chaque swap)
    // ------------------------------------------------------------
    function autoOpenEditModal() {
        const params = new URLSearchParams(window.location.search);
        const editId = params.get('edit');
        if (!editId) return;
        const button = document.querySelector(`[data-edit-affectation-button][data-id="${editId}"]`);
        if (!button) return;
        openEditAffectationModal(
            button.getAttribute('data-id'),
            button.getAttribute('data-materiel-id'),
            button.getAttribute('data-materiel-label'),
            button.getAttribute('data-date-debut'),
            button.getAttribute('data-date-fin'),
            button.getAttribute('data-commentaire')
        );
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // ============================================================
    // ⚡ Délégation globale — attachée UNE fois, survit aux swaps
    // ============================================================
    document.addEventListener('click', function (e) {
        if (e.target.closest('[data-add-affectation-button]')) {
            e.preventDefault();
            openAddAffectationModal();
            return;
        }

        const editBtn = e.target.closest('[data-edit-affectation-button]');
        if (editBtn) {
            e.preventDefault();
            openEditAffectationModal(
                editBtn.getAttribute('data-id'),
                editBtn.getAttribute('data-materiel-id'),
                editBtn.getAttribute('data-materiel-label'),
                editBtn.getAttribute('data-date-debut'),
                editBtn.getAttribute('data-date-fin'),
                editBtn.getAttribute('data-commentaire')
            );
            return;
        }

        const delBtn = e.target.closest('[data-delete-affectation-button]');
        if (delBtn) {
            e.preventDefault();
            handleDeleteAffectation(delBtn.getAttribute('data-id'));
            return;
        }

        const closeBtn = e.target.closest('[data-close-modal]');
        if (closeBtn) {
            e.preventDefault();
            const cible = closeBtn.getAttribute('data-close-modal');
            if (cible === 'add') closeAddAffectationModal();
            else if (cible === 'edit') closeEditAffectationModal();
            else if (cible === 'all') closeAllModals();
            return;
        }
    });

    document.addEventListener('submit', function (e) {
        if (e.target.matches('form#addAffectationForm')) {
            e.preventDefault();
            handleAddAffectation(e.target);
        } else if (e.target.matches('form#editAffectationForm')) {
            e.preventDefault();
            handleEditAffectation(e.target);
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeAllModals();
    });

    // Auto-open au load + après chaque swap
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoOpenEditModal);
    } else {
        autoOpenEditModal();
    }
    document.body.addEventListener('htmx:afterSwap', function (e) {
        if (e.detail.target.id === 'main-content') autoOpenEditModal();
    });

    // API publique
    window.AffectationModal = {
        openAdd: openAddAffectationModal,
        openAddForAtelier: openAddAffectationModal,
        openEdit: openEditAffectationModal,
        deleteById: handleDeleteAffectation,
        closeAdd: closeAddAffectationModal,
        closeEdit: closeEditAffectationModal,
        closeAll: closeAllModals,
    };
})();