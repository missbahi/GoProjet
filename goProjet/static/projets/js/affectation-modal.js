/**
 * Gestion des modals d'affectation de matériel.
 *
 * Ce fichier est réutilisable par plusieurs templates :
 *   - projets/ateliers/materiels.html
 *   - projets/ateliers/planning.html
 *
 * Dépendances DOM (doivent exister dans le template) :
 *   - Modals : #addAffectationModal, #editAffectationModal
 *   - Formulaires : #addAffectationForm, #editAffectationForm
 *   - Champs : #addMaterielInput, #addMateriel, #editMaterielInput, #editMateriel, ...
 *   - Backdrop : #modalBackdrop
 *   - Meta CSRF : <meta name="csrf-token" content="...">
 *
 * URLs (passées via data-attributes sur #affectation-config) :
 *   - data-add-url : URL pour ajouter une affectation
 *   - data-edit-template : URL pour modifier, avec /0/ à remplacer par l'ID
 *   - data-delete-template : URL pour supprimer, avec /0/ à remplacer par l'ID
 *
 * @author [A. Missbahi]
 * @version 1.0
 */
(function() {
    'use strict';

    // ============================================================
    // Configuration
    // ============================================================
    let CONFIG = {
        addUrl: null,
        editTemplate: null,
        deleteTemplate: null,
    };

    function chargerConfig() {
        const el = document.getElementById('affectation-config');
        if (!el) {
            console.warn('[Affectation] #affectation-config introuvable');
            return false;
        }
        CONFIG.addUrl = el.dataset.addUrl || el.dataset.addTemplate || null;
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

    // ============================================================
    // CSRF
    // ============================================================
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.content;
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : '';
    }

    // ============================================================
    // Ouverture / fermeture des modals
    // ============================================================
    function openAddAffectationModal(atelierId, url) {
        const modal = document.getElementById('addAffectationModal');
        const backdrop = document.getElementById('modalBackdrop');
        if (!modal || !backdrop) return;

        // Mettre à jour l'URL d'ajout si fournie (appel depuis le planning)
        if (url) {
            CONFIG.addUrl = url;
        }

        modal.style.display = 'block';
        backdrop.style.display = 'block';

        // Pré-remplir la date du jour
        const dateDebut = document.getElementById('addDateDebut');
        if (dateDebut && !dateDebut.value) {
            dateDebut.value = new Date().toISOString().split('T')[0];
        }
    }

    function openEditAffectationModal(id, materielId, materielLabel, dateDebut, dateFin, commentaire) {
        const modal = document.getElementById('editAffectationModal');
        const backdrop = document.getElementById('modalBackdrop');
        if (!modal || !backdrop) return;

        const setVal = (elId, val) => {
            const el = document.getElementById(elId);
            if (el) el.value = val || '';
        };

        setVal('editAffectationId', id);
        setVal('editMaterielInput', materielLabel);
        setVal('editMateriel', materielId);   // injecté directement
        setVal('editDateDebut', dateDebut);
        setVal('editDateFin', dateFin);
        setVal('editCommentaire', commentaire);

        modal.style.display = 'block';
        backdrop.style.display = 'block';
    }

    function closeAddAffectationModal() {
        const modal = document.getElementById('addAffectationModal');
        const backdrop = document.getElementById('modalBackdrop');
        const form = document.getElementById('addAffectationForm');
        if (modal) modal.style.display = 'none';
        if (backdrop) backdrop.style.display = 'none';
        if (form) form.reset();
        const input = document.getElementById('addMaterielInput');
        const hidden = document.getElementById('addMateriel');
        if (input) input.value = '';
        if (hidden) hidden.value = '';
        hideAllErrors('addAffectationForm');
    }

    function closeEditAffectationModal() {
        const modal = document.getElementById('editAffectationModal');
        const backdrop = document.getElementById('modalBackdrop');
        const input = document.getElementById('editMaterielInput');
        const hidden = document.getElementById('editMateriel');
        if (modal) modal.style.display = 'none';
        if (backdrop) backdrop.style.display = 'none';
        if (input) input.value = '';
        if (hidden) hidden.value = '';
        hideAllErrors('editAffectationForm');
    }

    function closeAllModals() {
        closeAddAffectationModal();
        closeEditAffectationModal();
    }

    // ============================================================
    // Synchronisation input visible ↔ hidden
    // ============================================================
    function syncMaterielIdFromInput(inputId, hiddenId) {
        const input = document.getElementById(inputId);
        const hidden = document.getElementById(hiddenId);
        if (!input || !hidden) return '';

        const valeur = input.value.trim();
        if (!valeur) {
            hidden.value = '';
            return '';
        }

        const datalist = document.getElementById(input.getAttribute('list'));
        if (!datalist) return '';

        const option = Array.from(datalist.options).find(o => o.value === valeur);
        hidden.value = option ? option.dataset.id : '';
        return hidden.value;
    }

    // ============================================================
    // Gestion des erreurs
    // ============================================================
    function hideAllErrors(formId) {
        document.querySelectorAll(`#${formId} .invalid-feedback`).forEach(el => el.classList.add('hidden'));
        document.querySelectorAll(`#${formId} input, #${formId} select, #${formId} textarea`)
            .forEach(el => el.classList.remove('border-red-500'));
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
    }

    function showServerErrors(formId, errors) {
        hideAllErrors(formId);
        if (!errors) return;
        Object.keys(errors).forEach(field => {
            const messages = errors[field].map(e => e.message || e).join(' ');
            showFieldError(formId, field, messages);
        });
    }

    // ============================================================
    // Notifications
    // ============================================================
    function showSuccessMessage(message) {
        const el = document.createElement('div');
        el.className = 'fixed top-4 left-1/2 transform -translate-x-1/2 z-50 p-4 bg-green-800 text-green-200 rounded-lg shadow-lg max-w-sm';
        el.innerHTML = `<i class="fa-solid fa-check mr-2"></i> ${message}`;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 3000);
    }

    function showErrorMessage(message) {
        const el = document.createElement('div');
        el.className = 'fixed top-4 left-1/2 transform -translate-x-1/2 z-50 p-4 bg-red-800 text-red-100 rounded-lg shadow-lg max-w-sm';
        el.innerHTML = `<i class="fa-solid fa-triangle-exclamation mr-2"></i> ${message}`;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 5000);
    }

    // ============================================================
    // Soumission : ajout
    // ============================================================
    function handleAddAffectation(form) {
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

        const formData = new FormData(form);
        if (!CONFIG.addUrl) {
            showErrorMessage("URL d'ajout non configurée.");
            return;
        }

        fetch(CONFIG.addUrl, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken(),
            },
        })
        .then(async response => {
            const contentType = response.headers.get('content-type') || '';
            if (!contentType.includes('application/json')) {
                const text = await response.text();
                console.error('Server returned non-JSON:', response.status, text);
                throw new Error(`HTTP ${response.status} - réponse inattendue`);
            }
            const data = await response.json();
            if (!response.ok) {
                const err = new Error('Validation échouée');
                err.data = data;
                throw err;
            }
            return data;
        })
        .then(data => {
            if (data.success) {
                closeAddAffectationModal();
                showSuccessMessage(data.message);
                setTimeout(() => window.location.reload(), 1000);
            } else {
                showServerErrors('addAffectationForm', data.errors);
                showErrorMessage(data.message || 'Veuillez corriger les erreurs.');
            }
        })
        .catch(error => {
            console.error('Add affectation error:', error);
            if (error.data && error.data.errors) {
                showServerErrors('addAffectationForm', error.data.errors);
                showErrorMessage(error.data.message || 'Veuillez corriger les erreurs.');
            } else {
                showErrorMessage("Erreur lors de l'affectation. Voir la console.");
            }
        });
    }

    // ============================================================
    // Soumission : édition
    // ============================================================
    function handleEditAffectation(form) {
        const materielInput = document.getElementById('editMateriel');
        const materielVisible = document.getElementById('editMaterielInput');
        const dateDebutInput = document.getElementById('editDateDebut');

        // Sync intelligente : ne remplace l'ID que si l'utilisateur a choisi une option
        const datalist = document.getElementById('editMaterielList');
        if (datalist && materielVisible && materielVisible.value.trim()) {
            const option = Array.from(datalist.options).find(
                o => o.value === materielVisible.value.trim()
            );
            if (option) {
                materielInput.value = option.dataset.id;
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
        const formData = new FormData(form);
        formData.set('materiel', materielInput.value);

        const url = construireEditUrl(id);
        if (!url) {
            showErrorMessage("URL d'édition non configurée.");
            return;
        }

        fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken(),
            },
        })
        .then(async response => {
            const contentType = response.headers.get('content-type') || '';
            if (!contentType.includes('application/json')) {
                const text = await response.text();
                console.error('Server returned non-JSON:', response.status, text);
                throw new Error(`HTTP ${response.status} - réponse inattendue`);
            }
            const data = await response.json();
            if (!response.ok) {
                const err = new Error('Validation échouée');
                err.data = data;
                throw err;
            }
            return data;
        })
        .then(data => {
            if (data.success) {
                closeEditAffectationModal();
                showSuccessMessage(data.message);
                setTimeout(() => window.location.reload(), 1000);
            } else {
                showServerErrors('editAffectationForm', data.errors);
                showErrorMessage(data.message || 'Veuillez corriger les erreurs.');
            }
        })
        .catch(error => {
            console.error('Edit affectation error:', error);
            if (error.data && error.data.errors) {
                showServerErrors('editAffectationForm', error.data.errors);
                showErrorMessage(error.data.message || 'Veuillez corriger les erreurs.');
            } else {
                showErrorMessage("Erreur lors de la modification. Voir la console.");
            }
        });
    }

    // ============================================================
    // Suppression
    // ============================================================
    function handleDeleteAffectation(id) {
        const url = construireDeleteUrl(id);
        if (!url) {
            showErrorMessage("URL de suppression non configurée.");
            return;
        }
        if (!confirm('Retirer ce matériel de l\'atelier ?')) return;

        fetch(url, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken(),
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showSuccessMessage(data.message || 'Affectation retirée.');
                setTimeout(() => window.location.reload(), 800);
            } else {
                showErrorMessage(data.message || 'Erreur lors de la suppression.');
            }
        })
        .catch(error => {
            console.error('Delete affectation error:', error);
            showErrorMessage('Une erreur est survenue lors de la suppression.');
        });
    }

    // ============================================================
    // Ouverture automatique via ?edit=<id>
    // ============================================================
    function autoOpenEditModal() {
        const params = new URLSearchParams(window.location.search);
        const editId = params.get('edit');
        if (!editId) return;

        const button = document.querySelector(`[data-edit-affectation-button][data-id="${editId}"]`);
        if (!button) {
            console.warn(`[Affectation] Affectation ${editId} introuvable dans la page`);
            return;
        }

        openEditAffectationModal(
            button.getAttribute('data-id'),
            button.getAttribute('data-materiel-id'),
            button.getAttribute('data-materiel-label'),
            button.getAttribute('data-date-debut'),
            button.getAttribute('data-date-fin'),
            button.getAttribute('data-commentaire')
        );

        // Nettoyer l'URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // ============================================================
    // Délégation d'événements
    // ============================================================
    function attacherHandlers() {
        // Clic sur les boutons
        document.addEventListener('click', function(e) {
            // Bouton "Affecter"
            if (e.target.matches('[data-add-affectation-button]') || e.target.closest('[data-add-affectation-button]')) {
                e.preventDefault();
                openAddAffectationModal();
                return;
            }

            // Bouton "Modifier"
            if (e.target.matches('[data-edit-affectation-button]') || e.target.closest('[data-edit-affectation-button]')) {
                const button = e.target.matches('[data-edit-affectation-button]')
                    ? e.target
                    : e.target.closest('[data-edit-affectation-button]');
                e.preventDefault();
                openEditAffectationModal(
                    button.getAttribute('data-id'),
                    button.getAttribute('data-materiel-id'),
                    button.getAttribute('data-materiel-label'),
                    button.getAttribute('data-date-debut'),
                    button.getAttribute('data-date-fin'),
                    button.getAttribute('data-commentaire')
                );
                return;
            }

            // Suppression
            if (e.target.matches('[data-delete-affectation-button]') || e.target.closest('[data-delete-affectation-button]')) {
                const button = e.target.matches('[data-delete-affectation-button]')
                    ? e.target
                    : e.target.closest('[data-delete-affectation-button]');
                e.preventDefault();
                handleDeleteAffectation(button.getAttribute('data-id'));
                return;
            }
            // Fermeture des modals via les boutons "data-close-modal"
            if (e.target.matches('[data-close-modal]') || e.target.closest('[data-close-modal]')) {
                const btn = e.target.matches('[data-close-modal]') ? e.target : e.target.closest('[data-close-modal]');
                e.preventDefault();
                const cible = btn.getAttribute('data-close-modal');
                if (cible === 'add') closeAddAffectationModal();
                else if (cible === 'edit') closeEditAffectationModal();
                else if (cible === 'all') closeAllModals();
                return;
            }
        });

        // Soumission des formulaires
        const addForm = document.getElementById('addAffectationForm');
        if (addForm) {
            addForm.addEventListener('submit', function(e) {
                e.preventDefault();
                handleAddAffectation(e.target);
            });
        }

        const editForm = document.getElementById('editAffectationForm');
        if (editForm) {
            editForm.addEventListener('submit', function(e) {
                e.preventDefault();
                handleEditAffectation(e.target);
            });
        }

        // Échap pour fermer
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeAllModals();
        });
    }

    // ============================================================
    // Point d'entrée
    // ============================================================
    function init() {
        if (!chargerConfig()) return;
        attacherHandlers();
        autoOpenEditModal();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // ============================================================
    // API publique (pour debug ou usage externe)
    // ============================================================
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

