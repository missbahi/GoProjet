/**
 * Gestion des tâches — version HTMX + projets pré-chargés côté serveur
 *
 * Les projets sont rendus par Django dans le <select name="projet">.
 * Ce fichier gère :
 *  - le chargement des responsables + priorités (via API)
 *  - l'ouverture/fermeture de la modal
 *  - la soumission (création + modification)
 *  - la suppression
 *  - le rafraîchissement HTMX après action
 */
(function() {
    'use strict';

    // ============================================================
    // CHARGEMENT DES DONNÉES (responsables + priorités)
    // ============================================================
    async function loadFormData() {
        try {
            const response = await fetch('/api/get-form-data/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('[taches] Erreur chargement form data:', error);
            return null;
        }
    }

    function populateFormOptions(data) {
        if (!data) return;

        // ⚡ NE PAS toucher au <select name="projet"> : il est rendu par Django

        // Responsables
        const responsableSelect = document.getElementById('responsable');
        if (responsableSelect) {
            const currentValue = responsableSelect.value;
            responsableSelect.innerHTML = '<option value="">Sélectionnez...</option>';
            (data.responsables || []).forEach(r => {
                responsableSelect.add(new Option(r.username, r.id));
            });
            if (currentValue) responsableSelect.value = currentValue;
        }

        // Priorités
        const prioriteSelect = document.getElementById('priorite');
        if (prioriteSelect) {
            const currentValue = prioriteSelect.value;
            prioriteSelect.innerHTML = '<option value="">Sélectionnez...</option>';
            (data.priorites || []).forEach(p => {
                prioriteSelect.add(new Option(p.label, p.value));
            });
            if (currentValue) {
                prioriteSelect.value = currentValue;
            } else {
                // Valeur par défaut
                prioriteSelect.value = 'NORMALE';
            }
        }
    }

    // ============================================================
    // OUVERTURE DE LA MODAL
    // ============================================================
    window.openTaskModal = async function(tacheId = null, projetId = null) {
        const modal = document.getElementById('taskModal');
        if (!modal) {
            console.error('[taches] #taskModal introuvable');
            return;
        }

        modal.classList.remove('hidden');

        const title = document.getElementById('modalTitle');
        if (title) title.textContent = tacheId ? 'Modifier Tâche' : 'Nouvelle Tâche';

        const tacheIdInput = document.getElementById('tacheId');
        if (tacheIdInput) tacheIdInput.value = tacheId || '';

        const form = document.getElementById('taskForm');
        const projetSelect = document.getElementById('projet');

        // ⚡ Gestion du projet
        if (projetId) {
            // Contexte projet : projet verrouillé
            if (form) form.dataset.projetId = projetId;
            if (projetSelect) {
                projetSelect.value = String(projetId);
                projetSelect.disabled = true;
            }
        } else {
            // Contexte global : l'utilisateur choisit
            if (form) delete form.dataset.projetId;
            if (projetSelect && !tacheId) {
                projetSelect.value = '';
                projetSelect.disabled = false;
            }
        }

        try {
            // Charger responsables + priorités
            const data = await loadFormData();
            populateFormOptions(data);

            // ⚡ Si modification : charger la tâche
            if (tacheId) {
                const url = `/projet/${projetId}/taches/${tacheId}/`;
                const response = await fetch(url, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    }
                });

                if (!response.ok) throw new Error(`Erreur ${response.status}`);

                const taskData = await response.json();
                if (!taskData?.success) {
                    throw new Error(taskData?.message || 'Réponse invalide');
                }

                fillTaskForm(taskData.data);
            }
        } catch (error) {
            console.error('[taches] Erreur ouverture modal:', error);
            showAlert('error', 'Erreur: ' + error.message);
            closeTaskModal();
        }
    };

    // ============================================================
    // REMPLISSAGE DU FORMULAIRE (pour modification)
    // ============================================================
    function fillTaskForm(tache) {
        const fields = {
            titre: tache.titre,
            responsable: tache.responsable?.id || '',
            priorite: tache.priorite || 'NORMALE',
            date_debut: tache.date_debut ? tache.date_debut.split('T')[0] : '',
            date_fin: tache.date_fin ? tache.date_fin.split('T')[0] : '',
            description: tache.description || '',
        };

        Object.entries(fields).forEach(([id, value]) => {
            const el = document.getElementById(id);
            if (!el) return;

            if (el.tagName === 'SELECT') {
                const exists = Array.from(el.options).some(o => o.value === String(value));
                el.value = exists ? String(value) : '';
            } else {
                el.value = value || '';
            }
        });

        // Checkbox terminee
        const terminee = document.getElementById('terminee');
        if (terminee) terminee.checked = !!tache.terminee;

        // Range avancement
        const avancement = document.getElementById('avancement');
        if (avancement) {
            avancement.value = tache.avancement || 0;
            const label = document.getElementById('avancementLabel');
            if (label) label.textContent = (tache.avancement || 0) + '%';
        }
    }

    // ============================================================
    // FERMETURE DE LA MODAL
    // ============================================================
    window.closeTaskModal = function() {
        const modal = document.getElementById('taskModal');
        if (modal) modal.classList.add('hidden');

        const form = document.getElementById('taskForm');
        if (form) {
            form.reset();
            delete form.dataset.projetId;
        }

        // Réactiver le select projet (au cas où il était désactivé)
        const projetSelect = document.getElementById('projet');
        if (projetSelect) projetSelect.disabled = false;
    };

    // ============================================================
    // SOUMISSION DU FORMULAIRE
    // ============================================================
    window.submitTacheForm = async function(event) {
        event.preventDefault();
        const form = event.target;
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalBtnText = submitBtn.innerHTML;

        const tacheId = document.getElementById('tacheId').value;

        // ⚡ Récupérer le projetId (dataset → select)
        let projetId = form.dataset.projetId
            || document.getElementById('projet')?.value;

        if (!projetId) {
            showAlert('error', 'Veuillez sélectionner un projet.');
            return;
        }

        try {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> En cours...';

            const url = tacheId
                ? `/projet/${projetId}/taches/${tacheId}/modifier/`
                : `/projet/${projetId}/taches/nouvelle/`;

            const formData = new FormData(form);

            // ⚡ Forcer le projet dans les données POST
            //    (le <select disabled> n'envoie pas sa valeur)
            formData.set('projet', projetId);

            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
            });

            const data = await response.json();

            if (!data.success) {
                if (data.errors) console.error('[taches] Erreurs:', data.errors);
                throw new Error(data.message || 'Erreur lors de la sauvegarde');
            }

            showAlert('success', data.message);
            closeTaskModal();
            refreshTachesListHTMX();

        } catch (error) {
            console.error('[taches] Erreur soumission:', error);
            showAlert('error', error.message);
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
        }
    };

    // ============================================================
    // SUPPRESSION
    // ============================================================
    window.deleteTask = async function(tacheId, projetId) {
        if (!confirm('Voulez-vous vraiment supprimer cette tâche ?')) return;

        try {
            const response = await fetch(`/projet/${projetId}/taches/${tacheId}/supprimer/`, {
                method: 'DELETE',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                credentials: 'include',
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => null);
                throw new Error(errorData?.message || 'Erreur lors de la suppression');
            }

            const data = await response.json();

            if (data.success) {
                showAlert('success', data.message || 'Tâche supprimée avec succès');
                refreshTachesListHTMX();
            } else {
                throw new Error(data.message || 'Erreur inconnue');
            }
        } catch (error) {
            console.error('[taches] Erreur suppression:', error);
            showAlert('error', `Échec suppression: ${error.message}`);
        }
    };

    // ============================================================
    // RAFRAÎCHISSEMENT VIA HTMX
    // ============================================================
    function refreshTachesListHTMX() {
        const container = document.getElementById('taches-container');
        if (!container) {
            window.location.reload();
            return;
        }

        if (window.htmx) {
            htmx.ajax('GET', window.location.href, {
                target: '#taches-container',
                swap: 'innerHTML',
            });
        } else {
            window.location.reload();
        }
    }

    // ============================================================
    // UTILITAIRES
    // ============================================================
    function showAlert(type, message) {
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type);
            return;
        }
        // Fallback : alerte simple
        const alert = document.createElement('div');
        alert.className = `fixed top-4 right-4 p-4 rounded-md text-white z-50 ${
            type === 'success' ? 'bg-green-500' : 'bg-red-500'
        }`;
        alert.textContent = message;
        document.body.appendChild(alert);
        setTimeout(() => alert.remove(), 3000);
    }

    function getCookie(name) {
        for (const c of document.cookie.split(';')) {
            const [k, v] = c.trim().split('=');
            if (k === name) return decodeURIComponent(v);
        }
        return null;
    }

    // ============================================================
    // DÉLÉGATION D'ÉVÉNEMENTS (survit aux swaps HTMX)
    // ============================================================

    // Input avancement (range) → mise à jour du label
    document.addEventListener('input', function(e) {
        if (e.target && e.target.id === 'avancement') {
            const label = document.getElementById('avancementLabel');
            if (label) label.textContent = e.target.value + '%';
        }
    });

    // Échap pour fermer la modal
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const modal = document.getElementById('taskModal');
            if (modal && !modal.classList.contains('hidden')) {
                closeTaskModal();
            }
        }
    });

    // Log après un swap HTMX (utile pour debug)
    document.body.addEventListener('htmx:afterSwap', function(e) {
        if (e.target.id === 'taches-container') {
            console.log('[taches] Liste rafraîchie');
        }
    });
})();