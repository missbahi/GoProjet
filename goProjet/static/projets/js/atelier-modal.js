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
        const el = document.getElementById('atelier-config');
        if (!el) {
            console.warn('[Atelier] #atelier-config introuvable');
            return false;
        }
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

    // ============================================================
    // CSRF
    // ============================================================
    function getCsrfToken() {
        const input = document.querySelector('#addAtelierForm [name=csrfmiddlewaretoken]')
                   || document.querySelector('[name=csrfmiddlewaretoken]');
        if (input) return input.value;
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : '';
    }

    // ============================================================
    // Ouverture / fermeture des modals
    // ============================================================
    function openAddAtelierModal() {
        document.getElementById('addAtelierModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function openEditAtelierModal(id, code, libelle, description, actif) {
        document.getElementById('editAtelierId').value = id;
        document.getElementById('editAtelierCode').value = code;
        document.getElementById('editAtelierLibelle').value = libelle;
        document.getElementById('editAtelierDescription').value = description || '';
        document.getElementById('editAtelierActif').checked = actif === 'true';
        document.getElementById('editAtelierModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function closeAddAtelierModal() {
        document.getElementById('addAtelierModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('addAtelierForm').classList.remove('was-validated');
        document.getElementById('addAtelierForm').reset();
        hideAllErrors('addAtelierForm');
    }

    function closeEditAtelierModal() {
        document.getElementById('editAtelierModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('editAtelierForm').classList.remove('was-validated');
        hideAllErrors('editAtelierForm');
    }

    function handleDeleteAtelier(id) {
        const url = construireDeleteUrl(id);
        if (!url) {
            showErrorMessage("URL de suppression non configurée.");
            return;
        }
        if (!confirm('Supprimer cet atelier ? Cette action est irréversible.')) return;

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
                showSuccessMessage(data.message || 'Atelier supprimé.');
                setTimeout(() => window.location.reload(), 800);
            } else {
                showErrorMessage(data.message || 'Erreur lors de la suppression.');
            }
        })
        .catch(error => {
            console.error('Delete atelier error:', error);
            showErrorMessage('Une erreur est survenue lors de la suppression.');
        });
    }

    function closeAllAtelierModals() {
        closeAddAtelierModal();
        closeEditAtelierModal();
    }

    // ============================================================
    // Gestion des erreurs de validation
    // ============================================================
    function hideAllErrors(formId) {
        document.querySelectorAll(`#${formId} .invalid-feedback`).forEach(el => el.classList.add('hidden'));
        document.querySelectorAll(`#${formId} input, #${formId} textarea`).forEach(el => el.classList.remove('border-red-500'));
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
        Object.keys(errors).forEach(field => {
            showFieldError(formId, field);
        });
    }

    // ============================================================
    // Notifications
    // ============================================================
    function showSuccessMessage(message) {
        const successMsg = document.createElement('div');
        successMsg.className = 'fixed top-4 left-1/2 transform -translate-x-1/2 z-50 p-4 bg-green-800 text-green-200 rounded-lg shadow-lg max-w-sm';
        successMsg.innerHTML = `<i class="fa-solid fa-check mr-2"></i> ${message}`;
        document.body.appendChild(successMsg);
        setTimeout(() => successMsg.remove(), 3000);
    }

    function showErrorMessage(message) {
        const errorMsg = document.createElement('div');
        errorMsg.className = 'fixed top-4 left-1/2 transform -translate-x-1/2 z-50 p-4 bg-red-800 text-red-100 rounded-lg shadow-lg max-w-sm';
        errorMsg.innerHTML = `<i class="fa-solid fa-triangle-exclamation mr-2"></i> ${message}`;
        document.body.appendChild(errorMsg);
        setTimeout(() => errorMsg.remove(), 5000);
    }

    // ============================================================
    // Handlers
    // ============================================================
    function attacherHandlers() {

        document.addEventListener('click', function(e) {
            // Bouton "Ajouter"
            if (e.target.matches('[data-add-atelier-button]') || e.target.closest('[data-add-atelier-button]')) {
                e.preventDefault();
                openAddAtelierModal();
                return;
            }

            // Bouton "Modifier"
            if (e.target.matches('[data-edit-atelier-button]') || e.target.closest('[data-edit-atelier-button]')) {
                const button = e.target.matches('[data-edit-atelier-button]') ? e.target : e.target.closest('[data-edit-atelier-button]');
                e.preventDefault();
                openEditAtelierModal(
                    button.getAttribute('data-id'),
                    button.getAttribute('data-code'),
                    button.getAttribute('data-libelle'),
                    button.getAttribute('data-description'),
                    button.getAttribute('data-actif'),
                );
                return;
            }

            // Suppression (lien)
            if (e.target.matches('a[href*="/supprimer/"]') || e.target.closest('a[href*="/supprimer/"]')) {
                const link = e.target.matches('a[href*="/supprimer/"]') ? e.target : e.target.closest('a[href*="/supprimer/"]');
                e.preventDefault();
                // Extraire l'ID depuis l'URL : .../ateliers/<id>/supprimer/
                const match = link.href.match(/\/ateliers\/(\d+)\/supprimer\//);
                if (!match) {
                    console.warn('[Atelier] ID introuvable dans l\'URL', link.href);
                    return;
                }
                const id = match[1];
                handleDeleteAtelier(id);
                return;
            }

            // Fermeture des modals
            if (e.target.matches('[data-close-modal]') || e.target.closest('[data-close-modal]')) {
                const btn = e.target.matches('[data-close-modal]') ? e.target : e.target.closest('[data-close-modal]');
                e.preventDefault();
                const cible = btn.getAttribute('data-close-modal');
                if (cible === 'add-atelier') closeAddAtelierModal();
                else if (cible === 'edit-atelier') closeEditAtelierModal();
                else if (cible === 'all') closeAllAtelierModals();
                return;
            }
        });

        // Soumission des formulaires
        const addForm = document.getElementById('addAtelierForm');
        if (addForm) {
            addForm.addEventListener('submit', function(e) {
                e.preventDefault();
                handleAddAtelier(e.target);
            });
        }

        const editForm = document.getElementById('editAtelierForm');
        if (editForm) {
            editForm.addEventListener('submit', function(e) {
                e.preventDefault();
                handleEditAtelier(e.target);
            });
        }

        // Échap pour fermer
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeAllAtelierModals();
        });
    }

    // ============================================================
    // Soumission : ajout
    // ============================================================
    function handleAddAtelier(form) {
        const codeInput = document.getElementById('addAtelierCode');
        const libelleInput = document.getElementById('addAtelierLibelle');
        hideAllErrors('addAtelierForm');

        let isValid = true;
        if (!codeInput.value.trim()) {
            showFieldError('addAtelierForm', 'code');
            isValid = false;
        }
        if (!libelleInput.value.trim()) {
            showFieldError('addAtelierForm', 'libelle');
            isValid = false;
        }
        if (!isValid) return;

        // ✅ URL lue depuis #atelier-config
        const url = CONFIG.addUrl;
        if (!url) {
            showErrorMessage("URL d'ajout non configurée.");
            return;
        }

        const formData = new FormData(form);

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
                closeAddAtelierModal();
                showSuccessMessage(data.message);
                setTimeout(() => window.location.reload(), 1000);
            } else {
                showServerErrors('addAtelierForm', data.errors);
                showErrorMessage(data.message || 'Veuillez corriger les erreurs.');
            }
        })
        .catch(error => {
            console.error('Add atelier error:', error);
            if (error.data && error.data.errors) {
                showServerErrors('addAtelierForm', error.data.errors);
                showErrorMessage(error.data.message || 'Veuillez corriger les erreurs.');
            } else {
                showErrorMessage("Erreur lors de l'ajout. Voir la console.");
            }
        });
    }

    // ============================================================
    // Soumission : édition
    // ============================================================
    function handleEditAtelier(form) {
        const codeInput = document.getElementById('editAtelierCode');
        const libelleInput = document.getElementById('editAtelierLibelle');
        hideAllErrors('editAtelierForm');

        let isValid = true;
        if (!codeInput.value.trim()) {
            showFieldError('editAtelierForm', 'code');
            isValid = false;
        }
        if (!libelleInput.value.trim()) {
            showFieldError('editAtelierForm', 'libelle');
            isValid = false;
        }
        if (!isValid) return;

        const id = document.getElementById('editAtelierId').value;

        // ✅ URL construite depuis le template
        const url = construireEditUrl(id);
        if (!url) {
            showErrorMessage("URL d'édition non configurée.");
            return;
        }

        const formData = new FormData(form);

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
                closeEditAtelierModal();
                showSuccessMessage(data.message);
                setTimeout(() => window.location.reload(), 1000);
            } else {
                showServerErrors('editAtelierForm', data.errors);
                showErrorMessage(data.message || 'Veuillez corriger les erreurs.');
            }
        })
        .catch(error => {
            console.error('Edit atelier error:', error);
            if (error.data && error.data.errors) {
                showServerErrors('editAtelierForm', error.data.errors);
                showErrorMessage(error.data.message || 'Veuillez corriger les erreurs.');
            } else {
                showErrorMessage("Erreur lors de la modification. Voir la console.");
            }
        });
    }

    // ============================================================
    // Point d'entrée
    // ============================================================
    function init() {
        if (!chargerConfig()) return;
        attacherHandlers();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // ============================================================
    // API publique
    // ============================================================
    window.AtelierModal = {
        openAdd: openAddAtelierModal,
        openEdit: openEditAtelierModal,
        closeAdd: closeAddAtelierModal,
        deleteById: handleDeleteAtelier,
        closeEdit: closeEditAtelierModal,
        closeAll: closeAllAtelierModals,
    };
})();