/* static/projets/js/data.js */
(function () {
    'use strict';

    const U = window.DATA_URLS;
    const $ = (id) => document.getElementById(id);

    // ============================================================
    // ÉTAT GLOBAL
    // ============================================================
    let activeMenuItemId = null;
    let currentIngenieurId = null;
    let currentClientId = null;
    let currentEntrepriseId = null;
    let currentPersonnelId = null;
    let currentMaterielId = null;
    let currentTransportId = null;
    let currentLocationId = null;
    let currentSousTraitanceId = null;
    let currentConsommableId = null;
    let currentFournitureId = null;
    let currentTypeMaterielId = null;

    // ============================================================
    // SIDEBAR MOBILE
    // ============================================================
    $('mobileMenuBtn')?.addEventListener('click', () => {
        $('mobileSidebar')?.classList.add('open');
        $('sidebarOverlay')?.classList.add('open');
    });
    $('mobileSidebarClose')?.addEventListener('click', closeMobileSidebar);
    $('sidebarOverlay')?.addEventListener('click', closeMobileSidebar);

    function closeMobileSidebar() {
        $('mobileSidebar')?.classList.remove('open');
        $('sidebarOverlay')?.classList.remove('open');
    }

    // ============================================================
    // CHARGEMENT DE MODULE
    // ============================================================
    window.loadModule = function (url, menuItemId) {
        return loadModuleInternal(url, menuItemId);
    };
    window.loadModuleMobile = function (url, menuItemId) {
        closeMobileSidebar();
        return loadModuleInternal(url, menuItemId);
    };

    function loadModuleInternal(url, menuItemId) {
        if (activeMenuItemId) {
            $(activeMenuItemId)?.classList.remove('active-menu-item');
            $(activeMenuItemId + '-mobile')?.classList.remove('active-menu-item');
        }
        $(menuItemId)?.classList.add('active-menu-item');
        activeMenuItemId = menuItemId;

        const area = $('content-area');
        if (!area) return;

        area.innerHTML = `
            <div class="app-card p-8 text-center">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 mx-auto mb-4"
                     style="border-color: var(--accent-green);"></div>
                <p style="color: var(--accent-green);">Chargement...</p>
            </div>`;

        return fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => r.text())
            .then(html => { area.innerHTML = html; })
            .catch(err => {
                console.error('loadModule:', err);
                area.innerHTML = `
                    <div class="app-card p-6 text-center">
                        <p style="color: var(--accent-danger);">Erreur de chargement</p>
                    </div>`;
            });
    }

    // ============================================================
    // SIDEBAR DATA — Navigation déclarative
    // ============================================================
    document.body.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-config-menu]');
        if (!btn) return;
        e.preventDefault();

        const url = btn.dataset.configUrl;
        const menuId = btn.dataset.configTarget;
        if (!url) return;

        // Marqueur "actif" (desktop + mobile)
        document.querySelectorAll('[data-config-menu]').forEach(b => {
            b.classList.toggle('active-menu-item', b === btn);
        });

        // Chargement
        loadModule(url, menuId);

        // Fermer la sidebar mobile si ouverte
        closeMobileSidebar();
    });

    // ============================================================
    // CHARGEMENT PAR DÉFAUT
    // ============================================================
    document.addEventListener('DOMContentLoaded', () => {
        loadModule(U.partialIngenieurs, 'menu-ingenieurs');
    });

    // Fonctions d'ouverture/fermeture des modals
    function openEditIngenieurModal(id, nom) {
        currentIngenieurId = id;
        document.getElementById('editId').value = id;
        document.getElementById('editNom').value = nom;
        document.getElementById('editIngenieurModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function openAddIngenieurModal() {
        document.getElementById('addIngenieurModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function closeEditIngenieurModal() {
        document.getElementById('editIngenieurModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('editIngenieurForm').classList.remove('was-validated');
        document.getElementById('editNom').classList.remove('border-red-500');
        document.querySelector('#editIngenieurForm .invalid-feedback').classList.add('hidden');
    }

    function closeAddIngenieurModal() {
        document.getElementById('addIngenieurModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('addIngenieurForm').classList.remove('was-validated');
        document.getElementById('addNom').classList.remove('border-red-500');
        document.querySelector('#addIngenieurForm .invalid-feedback').classList.add('hidden');
        document.getElementById('addNom').value = '';
    }

    // Fonctions pour les clients
    function openEditClientModal(id, nom, contact, email, telephone, adresse) {
        currentClientId = id;
        document.getElementById('editClientId').value = id;
        document.getElementById('editClientNom').value = nom;
        document.getElementById('editClientContact').value = contact || '';
        document.getElementById('editClientEmail').value = email || '';
        document.getElementById('editClientTelephone').value = telephone || '';
        document.getElementById('editClientAdresse').value = adresse || '';
        document.getElementById('editClientModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function openAddClientModal() {
        document.getElementById('addClientModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function closeEditClientModal() {
        document.getElementById('editClientModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('editClientForm').classList.remove('was-validated');
        document.getElementById('editClientNom').classList.remove('border-red-500');
        document.querySelectorAll('#editClientForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
    }

    function closeAddClientModal() {
        document.getElementById('addClientModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('addClientForm').classList.remove('was-validated');
        document.getElementById('addClientNom').classList.remove('border-red-500');
        document.querySelectorAll('#addClientForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
        document.getElementById('addClientNom').value = '';
        document.getElementById('addClientContact').value = '';
        document.getElementById('addClientEmail').value = '';
        document.getElementById('addClientTelephone').value = '';
        document.getElementById('addClientAdresse').value = '';
    }

    // Fonctions pour les entreprises
    function openEditEntrepriseModal(id, nom, contact, email, telephone, adresse) {
        currentEntrepriseId = id;
        document.getElementById('editEntrepriseId').value = id;
        document.getElementById('editEntrepriseNom').value = nom;
        document.getElementById('editEntrepriseContact').value = contact || '';
        document.getElementById('editEntrepriseEmail').value = email || '';
        document.getElementById('editEntrepriseTelephone').value = telephone || '';
        document.getElementById('editEntrepriseAdresse').value = adresse || '';
        document.getElementById('editEntrepriseModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function openAddEntrepriseModal() {
        document.getElementById('addEntrepriseModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function closeEditEntrepriseModal() {
        document.getElementById('editEntrepriseModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('editEntrepriseForm').classList.remove('was-validated');
        document.getElementById('editEntrepriseNom').classList.remove('border-red-500');
        document.querySelectorAll('#editEntrepriseForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
    }

    function closeAddEntrepriseModal() {
        document.getElementById('addEntrepriseModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('addEntrepriseForm').classList.remove('was-validated');
        document.getElementById('addEntrepriseNom').classList.remove('border-red-500');
        document.querySelectorAll('#addEntrepriseForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
        document.getElementById('addEntrepriseNom').value = '';
        document.getElementById('addEntrepriseContact').value = '';
        document.getElementById('addEntrepriseEmail').value = '';
        document.getElementById('addEntrepriseTelephone').value = '';
        document.getElementById('addEntrepriseAdresse').value = '';
    }

    // Fonctions pour le personnel
    function openEditPersonnelModal(id, nom, fonction, telephone, unite, tarif, actif) {
        currentPersonnelId = id;
        document.getElementById('editPersonnelId').value = id;
        document.getElementById('editPersonnelNom').value = nom;
        document.getElementById('editPersonnelFonction').value = fonction || '';
        document.getElementById('editPersonnelTelephone').value = telephone || '';
        document.getElementById('editPersonnelUnite').value = unite || '';
        document.getElementById('editPersonnelTarif').value = tarif
            ? String(tarif).replace(',', '.')
            : '';
        document.getElementById('editPersonnelActif').checked = actif === 'true';
        document.getElementById('editPersonnelModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function openAddPersonnelModal() {
        document.getElementById('addPersonnelModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function closeEditPersonnelModal() {
        document.getElementById('editPersonnelModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('editPersonnelForm').classList.remove('was-validated');
        document.getElementById('editPersonnelNom').classList.remove('border-red-500');
        document.querySelectorAll('#editPersonnelForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
    }

    function closeAddPersonnelModal() {
        document.getElementById('addPersonnelModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('addPersonnelForm').classList.remove('was-validated');
        document.getElementById('addPersonnelNom').classList.remove('border-red-500');
        document.querySelectorAll('#addPersonnelForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
        document.getElementById('addPersonnelForm').reset();
    }

    // Fonctions pour le matériel
    function formatPrixPourChamp(prix) {
        return prix ? String(prix).replace(',', '.') : '';
    }

    function rebuildTypeMaterielSelect(selectId, selectedId, inactiveType) {
        const select = document.getElementById(selectId);
        if (!select) return;

        // Option vide
        select.innerHTML = '<option value="">— Non défini —</option>';

        // Types actifs depuis la variable globale (remplie par le partial)
        (window.MATERIEL_TYPES || []).forEach(type => {
            const opt = document.createElement('option');
            opt.value = type.id;
            opt.textContent = type.nom;
            select.appendChild(opt);
        });

        // Cas particulier : type inactif déjà rattaché → ne pas le perdre
        if (inactiveType && inactiveType.id) {
            const opt = document.createElement('option');
            opt.value = inactiveType.id;
            opt.textContent = `${inactiveType.nom} (inactif)`;
            select.appendChild(opt);
        }

        select.value = selectedId || '';
    }

    function openEditMaterielModal(id, designation, typeId, typeNom, typeActif,
                                   immatriculation, unite, prixUnitaire, actif) {
        currentMaterielId = id;

        document.getElementById('editMaterielId').value = id;
        document.getElementById('editMaterielDesignation').value = designation;
        document.getElementById('editMaterielImmatriculation').value = immatriculation || '';
        document.getElementById('editMaterielUnite').value = unite || '';
        document.getElementById('editMaterielPrixUnitaire').value = formatPrixPourChamp(prixUnitaire);
        document.getElementById('editMaterielActif').checked = actif === 'true';

        // Reconstruction du <select> type_materiel (gère tout : options, actif, inactif, sélection)
        rebuildTypeMaterielSelect(
            'editMaterielTypeMateriel',
            typeId,
            typeActif === 'false' ? { id: typeId, nom: typeNom } : null
        );

        document.getElementById('editMaterielModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function openAddMaterielModal() {
        document.getElementById('addMaterielModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function closeEditMaterielModal() {
        document.getElementById('editMaterielModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('editMaterielForm').classList.remove('was-validated');
        document.getElementById('editMaterielDesignation').classList.remove('border-red-500');
        document.querySelectorAll('#editMaterielForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
    }

    function closeAddMaterielModal() {
        document.getElementById('addMaterielModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('addMaterielForm').classList.remove('was-validated');
        document.getElementById('addMaterielDesignation').classList.remove('border-red-500');
        document.querySelectorAll('#addMaterielForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
        document.getElementById('addMaterielForm').reset();
    }

    // Fonctions pour les types de matériel
    function openAddTypeMaterielModal() {
        document.getElementById('addTypeMaterielModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function openEditTypeMaterielModal(id, nom, icone, actif) {
        currentTypeMaterielId = id;
        document.getElementById('editTypeMaterielId').value = id;
        document.getElementById('editTypeMaterielNom').value = nom;
        document.getElementById('editTypeMaterielIcone').value = icone || '';
        document.getElementById('editTypeMaterielActif').checked = actif === 'true';
        updateIconePreview('editTypeMaterielIcone', 'editTypeMaterielIconePreview');
        document.getElementById('editTypeMaterielModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function closeAddTypeMaterielModal() {
        document.getElementById('addTypeMaterielModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('addTypeMaterielForm').classList.remove('was-validated');
        document.getElementById('addTypeMaterielNom').classList.remove('border-red-500');
        document.querySelectorAll('#addTypeMaterielForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
        document.getElementById('addTypeMaterielForm').reset();
        document.getElementById('addTypeMaterielIconePreview').classList.add('hidden');
    }

    function closeEditTypeMaterielModal() {
        document.getElementById('editTypeMaterielModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('editTypeMaterielForm').classList.remove('was-validated');
        document.getElementById('editTypeMaterielNom').classList.remove('border-red-500');
        document.querySelectorAll('#editTypeMaterielForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
    }

    // Aperçu de l'icône sélectionnée
    function updateIconePreview(selectId, previewId) {
        const select = document.getElementById(selectId);
        const preview = document.getElementById(previewId);
        if (!select || !preview) return;
        const img = preview.querySelector('img');
        const valeur = select.value;
        if (valeur) {
            img.src = `/static/images/materiels/${encodeURIComponent(valeur)}`;
            preview.classList.remove('hidden');
        } else {
            preview.classList.add('hidden');
        }
    }

    // Fonctions pour le transport
    function openEditTransportModal(id, designation, type, transporteur, prixUnitaire, actif) {
        currentTransportId = id;
        document.getElementById('editTransportId').value = id;
        document.getElementById('editTransportDesignation').value = designation;
        document.getElementById('editTransportType').value = type || '';
        document.getElementById('editTransportTransporteur').value = transporteur || '';
        document.getElementById('editTransportPrixUnitaire').value = formatPrixPourChamp(prixUnitaire);
        document.getElementById('editTransportActif').checked = actif === 'true';
        document.getElementById('editTransportModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function openAddTransportModal() {
        document.getElementById('addTransportModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function closeEditTransportModal() {
        document.getElementById('editTransportModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('editTransportForm').classList.remove('was-validated');
        document.getElementById('editTransportDesignation').classList.remove('border-red-500');
        document.querySelectorAll('#editTransportForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
    }

    function closeAddTransportModal() {
        document.getElementById('addTransportModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('addTransportForm').classList.remove('was-validated');
        document.getElementById('addTransportDesignation').classList.remove('border-red-500');
        document.querySelectorAll('#addTransportForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
        document.getElementById('addTransportForm').reset();
    }

    // Fonctions pour les locations
    function openEditLocationModal(id, designation, type, locataire, unite, prixUnitaire, actif) {
        currentLocationId = id;
        document.getElementById('editLocationId').value = id;
        document.getElementById('editLocationDesignation').value = designation;
        document.getElementById('editLocationType').value = type || '';
        document.getElementById('editLocationLocataire').value = locataire || '';
        document.getElementById('editLocationUnite').value = unite || '';
        document.getElementById('editLocationPrixUnitaire').value = formatPrixPourChamp(prixUnitaire);
        document.getElementById('editLocationActif').checked = actif === 'true';
        document.getElementById('editLocationModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function openAddLocationModal() {
        document.getElementById('addLocationModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function closeEditLocationModal() {
        document.getElementById('editLocationModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('editLocationForm').classList.remove('was-validated');
        document.getElementById('editLocationDesignation').classList.remove('border-red-500');
        document.querySelectorAll('#editLocationForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
    }

    function closeAddLocationModal() {
        document.getElementById('addLocationModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('addLocationForm').classList.remove('was-validated');
        document.getElementById('addLocationDesignation').classList.remove('border-red-500');
        document.querySelectorAll('#addLocationForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
        document.getElementById('addLocationForm').reset();
    }

    // Fonctions pour les sous-traitances
    function openEditSousTraitanceModal(id, designation, type, prestataire, unite, prixUnitaire, actif) {
        currentSousTraitanceId = id;
        document.getElementById('editSousTraitanceId').value = id;
        document.getElementById('editSousTraitanceDesignation').value = designation;
        document.getElementById('editSousTraitanceType').value = type || '';
        document.getElementById('editSousTraitancePrestataire').value = prestataire || '';
        document.getElementById('editSousTraitanceUnite').value = unite || '';
        document.getElementById('editSousTraitancePrixUnitaire').value = formatPrixPourChamp(prixUnitaire);
        document.getElementById('editSousTraitanceActif').checked = actif === 'true';
        document.getElementById('editSousTraitanceModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function openAddSousTraitanceModal() {
        document.getElementById('addSousTraitanceModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function closeEditSousTraitanceModal() {
        document.getElementById('editSousTraitanceModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('editSousTraitanceForm').classList.remove('was-validated');
        document.getElementById('editSousTraitanceDesignation').classList.remove('border-red-500');
        document.querySelectorAll('#editSousTraitanceForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
    }

    function closeAddSousTraitanceModal() {
        document.getElementById('addSousTraitanceModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('addSousTraitanceForm').classList.remove('was-validated');
        document.getElementById('addSousTraitanceDesignation').classList.remove('border-red-500');
        document.querySelectorAll('#addSousTraitanceForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
        document.getElementById('addSousTraitanceForm').reset();
    }

    // Fonctions pour les consommables
    function openEditConsommableModal(id, designation, type, fournisseur, unite, prixUnitaire, actif) {
        currentConsommableId = id;
        document.getElementById('editConsommableId').value = id;
        document.getElementById('editConsommableDesignation').value = designation;
        document.getElementById('editConsommableType').value = type || '';
        document.getElementById('editConsommableFournisseur').value = fournisseur || '';
        document.getElementById('editConsommableUnite').value = unite || '';
        document.getElementById('editConsommablePrixUnitaire').value = formatPrixPourChamp(prixUnitaire);
        document.getElementById('editConsommableActif').checked = actif === 'true';
        document.getElementById('editConsommableModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function openAddConsommableModal() {
        document.getElementById('addConsommableModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function closeEditConsommableModal() {
        document.getElementById('editConsommableModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('editConsommableForm').classList.remove('was-validated');
        document.getElementById('editConsommableDesignation').classList.remove('border-red-500');
        document.querySelectorAll('#editConsommableForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
    }

    function closeAddConsommableModal() {
        document.getElementById('addConsommableModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('addConsommableForm').classList.remove('was-validated');
        document.getElementById('addConsommableDesignation').classList.remove('border-red-500');
        document.querySelectorAll('#addConsommableForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
        document.getElementById('addConsommableForm').reset();
    }

    // Fonctions pour les fournitures
    function openEditFournitureModal(id, designation, type, fournisseur, unite, prixUnitaire, actif) {
        currentFournitureId = id;
        document.getElementById('editFournitureId').value = id;
        document.getElementById('editFournitureDesignation').value = designation;
        document.getElementById('editFournitureType').value = type || '';
        document.getElementById('editFournitureFournisseur').value = fournisseur || '';
        document.getElementById('editFournitureUnite').value = unite || '';
        document.getElementById('editFournitureUniPrixUnitaire').value = formatPrixPourChamp(prixUnitaire);
        document.getElementById('editFournitureActif').checked = actif === 'true';
        document.getElementById('editFournitureModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function openAddFournitureModal() {
        document.getElementById('addFournitureModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    }

    function closeEditFournitureModal() {
        document.getElementById('editFournitureModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('editFournitureForm').classList.remove('was-validated');
        document.getElementById('editFournitureDesignation').classList.remove('border-red-500');
        document.querySelectorAll('#editFournitureForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
    }

    function closeAddFournitureModal() {
        document.getElementById('addFournitureModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
        document.getElementById('addFournitureForm').classList.remove('was-validated');
        document.getElementById('addFournitureDesignation').classList.remove('border-red-500');
        document.querySelectorAll('#addFournitureForm .invalid-feedback').forEach(el => el.classList.add('hidden'));
        document.getElementById('addFournitureForm').reset();
    }

    function closeAllModals() {
        closeEditIngenieurModal();
        closeAddIngenieurModal();

        closeEditClientModal();
        closeAddClientModal();

        closeEditEntrepriseModal();
        closeAddEntrepriseModal();

        closeEditPersonnelModal();
        closeAddPersonnelModal();

        closeEditMaterielModal();
        closeAddMaterielModal();

        closeEditTypeMaterielModal();
        closeAddTypeMaterielModal();

        closeEditTransportModal();
        closeAddTransportModal();

        closeEditLocationModal();
        closeAddLocationModal();

        closeEditSousTraitanceModal();
        closeAddSousTraitanceModal();

        closeEditConsommableModal();
        closeAddConsommableModal();

        closeEditFournitureModal();
        closeAddFournitureModal();
    }

    // === DELEGATION D'EVENEMENTS : GESTION CENTRALISÉE ===
    document.addEventListener('click', function(e) {
        const nestedDelete = e.target.closest('[data-category-resource] a[href*="supprimer"]');
        if (nestedDelete) {
            e.preventDefault();

            // Confirmer la suppression
            if (!confirm('Supprimer cet élément ?')) return;

            // Envoyer la requête AJAX avec CSRF
            fetch(nestedDelete.href, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken(),
                }
            })
            .then(async response => {
                const data = await response.json();
                if (!response.ok || !data.success) {
                    throw data;
                }
                return data;
            })
            .then(data => {
                showSuccessMessage(data.message || 'Supprimé avec succès.');
                // Recharger uniquement le conteneur concerné
                const container = nestedDelete.closest('[data-category-resource]');
                if (container) {
                    const match = container.id.match(/category-resource-(\d+)/);
                    if (match) reloadCategoryResource(match[1]);
                }
            })
            .catch(error => {
                console.error('Delete error:', error);
                showErrorMessage(error.message || 'Erreur lors de la suppression.');
            });

            return;
        }
        
        const resourceToggle = e.target.closest('[data-resource-url]');
        if (resourceToggle) {
            e.preventDefault();
            const target = document.getElementById(resourceToggle.dataset.resourceTarget);
            if (!target) return;

            const chevron = resourceToggle.querySelector('.fa-chevron-down, .fa-chevron-up');
            const isOpen = !target.classList.contains('hidden');

            // --- CAS 1 : on referme ---
            if (isOpen) {
                target.classList.add('hidden');
                chevron?.classList.remove('rotate-180');
                return;
            }

            // --- CAS 2 : on ouvre ---
            target.classList.remove('hidden');
            chevron?.classList.add('rotate-180');

            // Si déjà chargé une fois, ne pas re-fetcher (évite le clignotement)
            if (target.dataset.loaded === 'true') {
                return;
            }

            // Premier chargement uniquement
            target.dataset.loaded = 'loading';
            target.innerHTML = '<p class="py-3 text-sm text-gray-400">Chargement...</p>';

            fetch(resourceToggle.dataset.resourceUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
                .then(response => {
                    if (!response.ok) throw new Error('Chargement impossible');
                    return response.text();
                })
                .then(html => {
                    // Si entre-temps l'utilisateur a fermé, on ne remplace pas
                    if (target.dataset.loaded === 'loading') {
                        target.innerHTML = html;
                        target.dataset.loaded = 'true';
                    }
                })
                .catch(() => {
                    target.dataset.loaded = '';
                    target.innerHTML = '<p class="py-3 text-sm text-red-300">Impossible de charger le référentiel.</p>';
                });
            return;
        }
        
        // Boutons d'ajout 
        if (e.target.matches('[data-add-ingenieur-button]')) {
            e.preventDefault();
            openAddIngenieurModal();
        } else if (e.target.matches('[data-add-client-button]')) {
            e.preventDefault();
            openAddClientModal();
        } else if (e.target.matches('[data-add-entreprise-button]')) {
            e.preventDefault();
            openAddEntrepriseModal();
        } else if (e.target.matches('[data-add-personnel-button]')) {
            e.preventDefault();
            openAddPersonnelModal();
        } else if (e.target.matches('[data-add-materiel-button]')) {
            e.preventDefault();
            openAddMaterielModal();
        } else if (e.target.matches('[data-add-transport-button]')) {
            e.preventDefault();
            openAddTransportModal();
        } else if (e.target.matches('[data-add-location-button]')) {
            e.preventDefault();
            openAddLocationModal();
        } else if (e.target.matches('[data-add-sous-traitance-button]')) {
            e.preventDefault();
            openAddSousTraitanceModal();
        } else if (e.target.matches('[data-add-consommable-button]')) {
            e.preventDefault();
            openAddConsommableModal();
        } else if (e.target.matches('[data-add-fourniture-button]')) {
            e.preventDefault();
            openAddFournitureModal();
        } else if (e.target.matches('[data-add-type-materiel-button]')) {
            e.preventDefault();
            openAddTypeMaterielModal();
        }
        // Bouton "Importer depuis un tableur"
        if (e.target.matches('[data-import-materiel-button]') || e.target.closest('[data-import-materiel-button]')) {
            e.preventDefault();
            openImportMaterielModal();
            return;
        }
        // Boutons d'édition Ingénieurs
        if (e.target.matches('[data-edit-ingenieur-button]') || e.target.closest('[data-edit-ingenieur-button]')) {
            const button = e.target.matches('[data-edit-ingenieur-button]') ? e.target : e.target.closest('[data-edit-ingenieur-button]');
            const id = button.getAttribute('data-id');
            const nom = button.getAttribute('data-nom');
            openEditIngenieurModal(id, nom);
        }
        
        // Boutons d'édition Clients
        if (e.target.matches('[data-edit-client-button]') || e.target.closest('[data-edit-client-button]')) {
            const button = e.target.matches('[data-edit-client-button]') ? e.target : e.target.closest('[data-edit-client-button]');
            const id = button.getAttribute('data-id');
            const nom = button.getAttribute('data-nom');
            const contact = button.getAttribute('data-contact');
            const email = button.getAttribute('data-email');
            const telephone = button.getAttribute('data-telephone');
            const adresse = button.getAttribute('data-adresse');
            openEditClientModal(id, nom, contact, email, telephone, adresse);
        }
        
        // Boutons d'édition Entreprises
        if (e.target.matches('[data-edit-entreprise-button]') || e.target.closest('[data-edit-entreprise-button]')) {
            const button = e.target.matches('[data-edit-entreprise-button]') ? e.target : e.target.closest('[data-edit-entreprise-button]');
            const id = button.getAttribute('data-id');
            const nom = button.getAttribute('data-nom');
            const contact = button.getAttribute('data-contact');
            const email = button.getAttribute('data-email');
            const telephone = button.getAttribute('data-telephone');
            const adresse = button.getAttribute('data-adresse');
            openEditEntrepriseModal(id, nom, contact, email, telephone, adresse);
        }
        
        // Boutons d'édition Personnel
        if (e.target.matches('[data-edit-personnel-button]') || e.target.closest('[data-edit-personnel-button]')) {
            const button = e.target.matches('[data-edit-personnel-button]') ? e.target : e.target.closest('[data-edit-personnel-button]');
            const id = button.getAttribute('data-id');
            const nom = button.getAttribute('data-nom');
            const fonction = button.getAttribute('data-fonction');
            const telephone = button.getAttribute('data-telephone');
            const unite = button.getAttribute('data-unite');
            const tarif = button.getAttribute('data-tarif');
            const actif = button.getAttribute('data-actif');
            openEditPersonnelModal(id, nom, fonction, telephone, unite, tarif, actif);
        }
        
        // Boutons d'édition Matériel
        if (e.target.matches('[data-edit-materiel-button]') || e.target.closest('[data-edit-materiel-button]')) {
            const button = e.target.matches('[data-edit-materiel-button]') ? e.target : e.target.closest('[data-edit-materiel-button]');
            const id = button.getAttribute('data-id');
            const designation = button.getAttribute('data-designation');
            const typeId = button.getAttribute('data-type-id');
            const typeNom = button.getAttribute('data-type-nom');
            const typeActif = button.getAttribute('data-type-actif');
            const immatriculation = button.getAttribute('data-immatriculation');
            const unite = button.getAttribute('data-unite');
            const prixUnitaire = button.getAttribute('data-prix-unitaire');
            const actif = button.getAttribute('data-actif');
            openEditMaterielModal(id, designation, typeId, typeNom, typeActif, immatriculation, unite, prixUnitaire, actif);
        }

        // Boutons d'édition Transport
        if (e.target.matches('[data-edit-transport-button]') || e.target.closest('[data-edit-transport-button]')) {
            const button = e.target.matches('[data-edit-transport-button]') ? e.target : e.target.closest('[data-edit-transport-button]');
            const id = button.getAttribute('data-id');
            const designation = button.getAttribute('data-designation');
            const type = button.getAttribute('data-type');
            const transporteur = button.getAttribute('data-transporteur');
            const prixUnitaire = button.getAttribute('data-prix-unitaire');
            const actif = button.getAttribute('data-actif');
            openEditTransportModal(id, designation, type, transporteur, prixUnitaire, actif);
        }
        
        // Boutons d'édition Locations
        if (e.target.matches('[data-edit-location-button]') || e.target.closest('[data-edit-location-button]')) {
            const button = e.target.matches('[data-edit-location-button]') ? e.target : e.target.closest('[data-edit-location-button]');
            const id = button.getAttribute('data-id');
            const designation = button.getAttribute('data-designation');
            const type = button.getAttribute('data-type');
            const locataire = button.getAttribute('data-locataire');
            const unite = button.getAttribute('data-unite');
            const prixUnitaire = button.getAttribute('data-prix-unitaire');
            const actif = button.getAttribute('data-actif');
            openEditLocationModal(id, designation, type, locataire, unite, prixUnitaire, actif);
        }
        
        // Boutons d'édition Sous-traitances
        if (e.target.matches('[data-edit-sous-traitance-button]') || e.target.closest('[data-edit-sous-traitance-button]')) {
            const button = e.target.matches('[data-edit-sous-traitance-button]') ? e.target : e.target.closest('[data-edit-sous-traitance-button]');
            const id = button.getAttribute('data-id');
            const designation = button.getAttribute('data-designation');
            const type = button.getAttribute('data-type');
            const prestataire = button.getAttribute('data-prestataire');
            const unite = button.getAttribute('data-unite');
            const prixUnitaire = button.getAttribute('data-prix-unitaire');
            const actif = button.getAttribute('data-actif');
            openEditSousTraitanceModal(id, designation, type, prestataire, unite, prixUnitaire, actif);
        }
        
        // Boutons d'édition Consommables
        if (e.target.matches('[data-edit-consommable-button]') || e.target.closest('[data-edit-consommable-button]')) {
            const button = e.target.matches('[data-edit-consommable-button]') ? e.target : e.target.closest('[data-edit-consommable-button]');
            const id = button.getAttribute('data-id');
            const designation = button.getAttribute('data-designation');
            const type = button.getAttribute('data-type');
            const fournisseur = button.getAttribute('data-fournisseur');
            const unite = button.getAttribute('data-unite');
            const prixUnitaire = button.getAttribute('data-prix-unitaire');
            const actif = button.getAttribute('data-actif');
            openEditConsommableModal(id, designation, type, fournisseur, unite, prixUnitaire, actif);
        }
        
        // Boutons d'édition Fournitures
        if (e.target.matches('[data-edit-fourniture-button]') || e.target.closest('[data-edit-fourniture-button]')) {
            const button = e.target.matches('[data-edit-fourniture-button]') ? e.target : e.target.closest('[data-edit-fourniture-button]');
            const id = button.getAttribute('data-id');
            const designation = button.getAttribute('data-designation');
            const type = button.getAttribute('data-type');
            const fournisseur = button.getAttribute('data-fournisseur');
            const unite = button.getAttribute('data-unite');
            const prixUnitaire = button.getAttribute('data-prix-unitaire');
            const actif = button.getAttribute('data-actif');
            openEditFournitureModal(id, designation, type, fournisseur, unite, prixUnitaire, actif);
        }
        
        // Boutons d'édition Types de matériel
                // Boutons d'édition TypeMateriel
        if (e.target.matches('[data-edit-type-materiel-button]') || e.target.closest('[data-edit-type-materiel-button]')) {
            const button = e.target.matches('[data-edit-type-materiel-button]') ? e.target : e.target.closest('[data-edit-type-materiel-button]');
            const id = button.getAttribute('data-id');
            const nom = button.getAttribute('data-nom');
            const icone = button.getAttribute('data-icone');
            const actif = button.getAttribute('data-actif');
            openEditTypeMaterielModal(id, nom, icone, actif);
        }

        // Boutons de suppression
        if (e.target.matches('a[href*="supprimer"]') || e.target.closest('a[href*="supprimer"]')) {
            const link = e.target.matches('a[href*="supprimer"]') ? e.target : e.target.closest('a[href*="supprimer"]');
            e.preventDefault();

            const entityType = link.href.includes('type_materiel') ? 'type de matériel' :
                            link.href.includes('ingenieur') ? 'ingénieur' :
                            link.href.includes('client') ? 'client' :
                            link.href.includes('entreprise') ? 'entreprise' :
                            link.href.includes('personnel') ? 'membre du personnel' :
                            link.href.includes('materiel') ? 'matériel' :
                            link.href.includes('location') ? 'location' :
                            link.href.includes('sous_traitance') ? 'sous-traitance' :
                            link.href.includes('consommable') ? 'consommable' : 'fourniture';

            if (!confirm(`Supprimer ce ${entityType} ?`)) return;

            fetch(link.href, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken(),
                }
            })
            .then(async response => {
                const data = await response.json();
                if (!response.ok || !data.success) {
                    throw data;
                }
                return data;
            })
            .then(data => {
                // 1. Afficher le message de succès (reste affiché, conteneur stable)
                showSuccessMessage(data.message || 'Suppression effectuée.');

                // 2. Recharger uniquement le partial concerné, pas tout le module
                if (link.href.includes('type_materiel')) {
                    loadModule(U.partialTypesMateriel, 'menu-types-materiel');
                } else if (link.href.includes('ingenieur')) {
                    loadModule(U.partialIngenieurs, 'menu-ingenieurs');
                } else if (link.href.includes('client')) {
                    loadModule(U.partialClients, 'menu-clients');
                } else if (link.href.includes('entreprise')) {
                    loadModule(U.partialEntreprises, 'menu-entreprises');
                } else if (link.href.includes('personnel')) {
                    // Les ressources sont dans des sous-conteneurs de catégories
                    reloadCategoryResource(getCategoryIdForLink(link));
                } else if (link.href.includes('materiel')) {
                    reloadCategoryResource(getCategoryIdForLink(link));
                } else if (link.href.includes('location')) {
                    reloadCategoryResource(getCategoryIdForLink(link));
                } else if (link.href.includes('sous_traitance')) {
                    reloadCategoryResource(getCategoryIdForLink(link));
                } else if (link.href.includes('consommable')) {
                    reloadCategoryResource(getCategoryIdForLink(link));
                } else if (link.href.includes('fourniture')) {
                    reloadCategoryResource(getCategoryIdForLink(link));
                }
            })
            .catch(error => {
                console.error('Delete error:', error);
                showErrorMessage(
                    error.message || 'Une erreur est survenue lors de la suppression.'
                );
            });
        }
        
        // Boutons de fermeture des modals
        if (e.target.matches('.modal button i.fa-times') || e.target.closest('.modal button i.fa-times')) {
            closeAllModals();
        }
    });

    function getCategoryIdForLink(link) {
        // Le lien est dans le partial materiel.html, qui est dans category-resource-XXX
        const container = link.closest('[data-category-resource]');
        if (!container) {
            console.warn('Conteneur data-category-resource introuvable');
            return null;
        }
        // L'ID est "category-resource-123"
        const match = container.id.match(/category-resource-(\d+)/);
        return match ? match[1] : null;
    }

    // Gérer toutes les soumissions de formulaires
    document.addEventListener('submit', function(e) {
        if (e.target.matches('.category-charge-form')) {
            e.preventDefault();
            const form = e.target;
            const feedback = document.querySelector('[data-categories-module] .category-charge-feedback');
            const csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]')?.value;
            fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    ...(csrfToken ? {'X-CSRFToken': csrfToken} : {}),
                }
            }).then(async response => {
                const contentType = response.headers.get('content-type') || '';
                const responseText = await response.text();
                let data;
                try {
                    data = contentType.includes('application/json') ? JSON.parse(responseText) : null;
                } catch (parseError) {
                    data = null;
                }
                if (!data) {
                    throw new Error(response.status === 401
                        ? 'Votre session a expiré. Veuillez vous reconnecter.'
                        : response.status === 403
                            ? 'La requête a été refusée par le serveur (CSRF ou permission). Actualisez la page puis réessayez.'
                            : 'Le serveur a renvoyé une réponse inattendue.');
                }
                if (!response.ok || !data.success) {
                    const errors = Object.values(data.errors || {}).flat().map(error => error.message || error).join(' ');
                    throw new Error(errors || data.message || 'Impossible d’enregistrer la catégorie.');
                }
                return loadModule(form.dataset.reloadUrl, 'menu-personnel').then(() => {
                    const reloadedFeedback = document.querySelector('[data-categories-module] .category-charge-feedback');
                    if (reloadedFeedback) {
                        reloadedFeedback.textContent = data.message;
                        reloadedFeedback.className = 'category-charge-feedback rounded border border-emerald-700/60 bg-emerald-950/50 px-3 py-2 text-sm text-emerald-200';
                    }
                });
            }).catch(error => {
                if (feedback) {
                    feedback.textContent = error.message;
                    feedback.className = 'category-charge-feedback rounded border border-red-700/60 bg-red-950/40 px-3 py-2 text-sm text-red-200';
                }
            });
        } else if (e.target.matches('#addIngenieurForm')) {
            e.preventDefault();
            handleAddIngenieur(e.target);
        } else if (e.target.matches('#editIngenieurForm')) {
            e.preventDefault();
            handleEditIngenieur(e.target);
        } else if (e.target.matches('#addClientForm')) {
            e.preventDefault();
            handleAddClient(e.target);
        } else if (e.target.matches('#editClientForm')) {
            e.preventDefault();
            handleEditClient(e.target);
        } else if (e.target.matches('#addEntrepriseForm')) {
            e.preventDefault();
            handleAddEntreprise(e.target);
        } else if (e.target.matches('#editEntrepriseForm')) {
            e.preventDefault();
            handleEditEntreprise(e.target);
        } else if (e.target.matches('#addPersonnelForm')) {
            e.preventDefault();
            handleAddPersonnel(e.target);
        } else if (e.target.matches('#editPersonnelForm')) {
            e.preventDefault();
            handleEditPersonnel(e.target);
        } else if (e.target.matches('#addMaterielForm')) {
            e.preventDefault();
            handleAddMateriel(e.target);
        } else if (e.target.matches('#addTypeMaterielForm')) {
            e.preventDefault();
            handleAddTypeMateriel(e.target);
        } else if (e.target.matches('#editTypeMaterielForm')) {
            e.preventDefault();
            handleEditTypeMateriel(e.target);
        } else if (e.target.matches('#editMaterielForm')) {
            e.preventDefault();
            handleEditMateriel(e.target);
        } else if (e.target.matches('#addTransportForm')) {
            e.preventDefault();
            handleAddTransport(e.target);
        } else if (e.target.matches('#editTransportForm')) {
            e.preventDefault();
            handleEditTransport(e.target);
        } else if (e.target.matches('#addLocationForm')) {
            e.preventDefault();
            handleAddLocation(e.target);
        } else if (e.target.matches('#editLocationForm')) {
            e.preventDefault();
            handleEditLocation(e.target);
        } else if (e.target.matches('#addSousTraitanceForm')) {
            e.preventDefault();
            handleAddSousTraitance(e.target);
        } else if (e.target.matches('#editSousTraitanceForm')) {
            e.preventDefault();
            handleEditSousTraitance(e.target);
        } else if (e.target.matches('#addConsommableForm')) {
            e.preventDefault();
            handleAddConsommable(e.target);
        } else if (e.target.matches('#editConsommableForm')) {
            e.preventDefault();
            handleEditConsommable(e.target);
        } else if (e.target.matches('#addFournitureForm')) {
            e.preventDefault();
            handleAddFourniture(e.target);
        } else if (e.target.matches('#editFournitureForm')) {
            e.preventDefault();
            handleEditFourniture(e.target);
        }
    });

    // === FONCTIONS DE GESTION DES FORMULAIRES ===

    // Ingénieurs
    function handleAddIngenieur(form) {
        const nomInput = document.getElementById('addNom');
        let isValid = true;

        if (!nomInput.value.trim()) {
            nomInput.classList.add('border-red-500');
            document.querySelector('#addIngenieurForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            nomInput.classList.remove('border-red-500');
            document.querySelector('#addIngenieurForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        fetch(`${U.ajouterIngenieur}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeAddIngenieurModal();
                showSuccessMessage('Ingénieur ajouté avec succès!');
                loadModule(U.partialIngenieurs, 'menu-ingenieurs')
                    .then(() => {
                        showSuccessMessage(data.message);
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Une erreur est survenue lors de l\'ajout.');
                    });
            } else {
                alert('Erreur: ' + JSON.stringify(data.errors));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de l\'ajout.');
        });
    }

    function handleEditIngenieur(form) {
        const nomInput = document.getElementById('editNom');
        let isValid = true;

        if (!nomInput.value.trim()) {
            nomInput.classList.add('border-red-500');
            document.querySelector('#editIngenieurForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            nomInput.classList.remove('border-red-500');
            document.querySelector('#editIngenieurForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        const id = document.getElementById('editId').value;

        fetch(`${U.modifierIngenieur.replace('0', id)}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeEditIngenieurModal();
                loadModule(U.partialIngenieurs, 'menu-ingenieurs')
                    .then(() => {
                        showSuccessMessage(data.message);
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Une erreur est survenue lors de la modification.');
                    });
            } else {
                alert('Erreur lors de la modification.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de la modification.');
        });
    }

    // Clients
    function handleAddClient(form) {
        const nomInput = document.getElementById('addClientNom');
        let isValid = true;

        if (!nomInput.value.trim()) {
            nomInput.classList.add('border-red-500');
            document.querySelector('#addClientForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            nomInput.classList.remove('border-red-500');
            document.querySelector('#addClientForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);

        fetch(`${U.ajouterClient}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeAddClientModal();
                loadModule(U.partialClients, 'menu-clients')
                    .then(() => {
                        showSuccessMessage(data.message);
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Une erreur est survenue lors de l\'ajout.');
                    });
            } else {
                alert('Erreur: ' + JSON.stringify(data.errors));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de l\'ajout.');
        });
    }

    function handleEditClient(form) {
        const nomInput = document.getElementById('editClientNom');
        let isValid = true;

        if (!nomInput.value.trim()) {
            nomInput.classList.add('border-red-500');
            document.querySelector('#editClientForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            nomInput.classList.remove('border-red-500');
            document.querySelector('#editClientForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        const id = document.getElementById('editClientId').value;

        fetch(`${U.modifierClient.replace('0', id)}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeEditClientModal();
                loadModule(U.partialClients, 'menu-clients')
                    .then(() => {
                        showSuccessMessage(data.message);
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Une erreur est survenue lors de la modification.');
                    });
            } else {
                alert('Erreur lors de la modification.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de la modification.');
        });
    }

    // Entreprises
    function handleAddEntreprise(form) {
        const nomInput = document.getElementById('addEntrepriseNom');
        let isValid = true;

        if (!nomInput.value.trim()) {
            nomInput.classList.add('border-red-500');
            document.querySelector('#addEntrepriseForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            nomInput.classList.remove('border-red-500');
            document.querySelector('#addEntrepriseForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);

        fetch(`${U.ajouterEntreprise}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeAddEntrepriseModal();
                loadModule(U.partialEntreprises, 'menu-entreprises')
                    .then(() => {
                        showSuccessMessage(data.message);
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Une erreur est survenue lors de l\'ajout.');
                    });
            } else {
                alert('Erreur: ' + JSON.stringify(data.errors));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de l\'ajout.');
        });
    }

    function handleEditEntreprise(form) {
        const nomInput = document.getElementById('editEntrepriseNom');
        let isValid = true;

        if (!nomInput.value.trim()) {
            nomInput.classList.add('border-red-500');
            document.querySelector('#editEntrepriseForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            nomInput.classList.remove('border-red-500');
            document.querySelector('#editEntrepriseForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        const id = document.getElementById('editEntrepriseId').value;

        fetch(`${U.modifierEntreprise.replace('0', id)}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeEditEntrepriseModal();
                loadModule(U.partialEntreprises, 'menu-entreprises')
                    .then(() => {
                        showSuccessMessage(data.message);
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('Une erreur est survenue lors de la modification.');
                    });
                    
            } else {
                alert('Erreur lors de la modification.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de la modification.');
        });
    }

    // Personnel
    function handleAddPersonnel(form) {
        const nomInput = document.getElementById('addPersonnelNom');
        let isValid = true;

        if (!nomInput.value.trim()) {
            nomInput.classList.add('border-red-500');
            document.querySelector('#addPersonnelForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            nomInput.classList.remove('border-red-500');
            document.querySelector('#addPersonnelForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        fetch(`${U.ajouterPersonnel}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeAddPersonnelModal();
                rechargerRessourcesOuvertes();
                showSuccessMessage(data.message);
            } else {
                alert('Erreur: ' + JSON.stringify(data.errors));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de l\'ajout.');
        });
    }

    function handleEditPersonnel(form) {
        const nomInput = document.getElementById('editPersonnelNom');
        let isValid = true;

        if (!nomInput.value.trim()) {
            nomInput.classList.add('border-red-500');
            document.querySelector('#editPersonnelForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            nomInput.classList.remove('border-red-500');
            document.querySelector('#editPersonnelForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        const id = document.getElementById('editPersonnelId').value;

        fetch(`${U.modifierPersonnel.replace('0', id)}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeEditPersonnelModal();
                rechargerRessourcesOuvertes(parseInt(id, 10));
                showSuccessMessage(data.message);
            } else {
                alert('Erreur lors de la modification.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de la modification.');
        });
    }

    // Matériel
    function handleAddMateriel(form) {
        const designationInput = document.getElementById('addMaterielDesignation');
        let isValid = true;

        if (!designationInput.value.trim()) {
            designationInput.classList.add('border-red-500');
            document.querySelector('#addMaterielForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            designationInput.classList.remove('border-red-500');
            document.querySelector('#addMaterielForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);

        fetch(`${U.ajouterMateriel}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeAddMaterielModal();
                rechargerRessourcesOuvertes();
                showSuccessMessage(data.message);
            } else {
                alert('Erreur: ' + JSON.stringify(data.errors));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de l\'ajout.');
        });
    }

    function handleEditMateriel(form) {
        const designationInput = document.getElementById('editMaterielDesignation');
        let isValid = true;

        if (!designationInput.value.trim()) {
            designationInput.classList.add('border-red-500');
            document.querySelector('#editMaterielForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            designationInput.classList.remove('border-red-500');
            document.querySelector('#editMaterielForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        const id = document.getElementById('editMaterielId').value;

        fetch(`${U.modifierMateriel.replace('0', id)}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeEditMaterielModal();
                rechargerRessourcesOuvertes(parseInt(id, 10));
                showSuccessMessage(data.message);
            } else {
                alert('Erreur lors de la modification.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de la modification.');
        });
    }

    // Types de matériel
    function handleAddTypeMateriel(form) {
        const nomInput = document.getElementById('addTypeMaterielNom');
        let isValid = true;
        if (!nomInput.value.trim()) {
            nomInput.classList.add('border-red-500');
            document.querySelector('#addTypeMaterielForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            nomInput.classList.remove('border-red-500');
            document.querySelector('#addTypeMaterielForm .invalid-feedback').classList.add('hidden');
        }
        if (!isValid) return;

        const formData = new FormData(form);
        fetch(U.ajouterTypeMateriel + "?modal=true", {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeAddTypeMaterielModal();
                // ⬇️ loadModule, pas rechargerRessourcesOuvertes
                loadModule(U.partialTypesMateriel, 'menu-types-materiel')
                    .then(() => showSuccessMessage(data.message));
            } else {
                alert('Erreur: ' + JSON.stringify(data.errors));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de l\'ajout.');
        });
    }

    function handleEditTypeMateriel(form) {
        const nomInput = document.getElementById('editTypeMaterielNom');
        let isValid = true;
        if (!nomInput.value.trim()) {
            nomInput.classList.add('border-red-500');
            document.querySelector('#editTypeMaterielForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            nomInput.classList.remove('border-red-500');
            document.querySelector('#editTypeMaterielForm .invalid-feedback').classList.add('hidden');
        }
        if (!isValid) return;

        const formData = new FormData(form);
        const id = document.getElementById('editTypeMaterielId').value;
        const modifierUrl = U.modifierTypeMateriel.replace('0', id);

        fetch(`${modifierUrl}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeEditTypeMaterielModal();
                // ⬇️ CORRECTION : utiliser loadModule, pas rechargerRessourcesOuvertes
                loadModule(U.partialTypesMateriel, 'menu-types-materiel')
                    .then(() => showSuccessMessage(data.message));
            } else {
                alert('Erreur: ' + JSON.stringify(data.errors));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de la modification.');
        });
    }
    
    // Transports
    function handleAddTransport(form) {
        const designationInput = document.getElementById('addTransportDesignation');
        let isValid = true;

        if (!designationInput.value.trim()) {
            designationInput.classList.add('border-red-500');
            document.querySelector('#addTransportForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            designationInput.classList.remove('border-red-500');
            document.querySelector('#addTransportForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);

        fetch(`${U.ajouterTransport}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeAddTransportModal();
                rechargerRessourcesOuvertes();
                showSuccessMessage(data.message);
            } else {
                alert('Erreur: ' + JSON.stringify(data.errors));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de l\'ajout.');
        });
    }

    function handleEditTransport(form) {
        const designationInput = document.getElementById('editTransportDesignation');
        let isValid = true;

        if (!designationInput.value.trim()) {
            designationInput.classList.add('border-red-500');
            document.querySelector('#editTransportForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            designationInput.classList.remove('border-red-500');
            document.querySelector('#editTransportForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        const transportId = document.getElementById('editTransportId').value;
        const modifierTransportUrl = U.modifierTransport.replace('0', transportId);

        fetch(`${modifierTransportUrl}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeEditTransportModal();
                rechargerRessourcesOuvertes(parseInt(transportId, 10));
                showSuccessMessage(data.message);
            } else {
                alert('Erreur: ' + JSON.stringify(data.errors));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de la modification.');
        });
    }

    // Locations
    function handleAddLocation(form) {
        const designationInput = document.getElementById('addLocationDesignation');
        let isValid = true;

        if (!designationInput.value.trim()) {
            designationInput.classList.add('border-red-500');
            document.querySelector('#addLocationForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            designationInput.classList.remove('border-red-500');
            document.querySelector('#addLocationForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        fetch(`${U.ajouterLocation}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeAddLocationModal();
                rechargerRessourcesOuvertes();
                showSuccessMessage(data.message);
            } else {
                alert('Erreur: ' + JSON.stringify(data.errors));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de l\'ajout.');
        });
    }

    function handleEditLocation(form) {
        const designationInput = document.getElementById('editLocationDesignation');
        let isValid = true;

        if (!designationInput.value.trim()) {
            designationInput.classList.add('border-red-500');
            document.querySelector('#editLocationForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            designationInput.classList.remove('border-red-500');
            document.querySelector('#editLocationForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        const id = document.getElementById('editLocationId').value;

        fetch(`${U.modifierLocation.replace('0', id)}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeEditLocationModal();
                rechargerRessourcesOuvertes(parseInt(id, 10));
                showSuccessMessage(data.message);
            } else {
                alert('Erreur lors de la modification.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de la modification.');
        });
    }

    // Sous-traitances
    function handleAddSousTraitance(form) {
        const designationInput = document.getElementById('addSousTraitanceDesignation');
        let isValid = true;

        if (!designationInput.value.trim()) {
            designationInput.classList.add('border-red-500');
            document.querySelector('#addSousTraitanceForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            designationInput.classList.remove('border-red-500');
            document.querySelector('#addSousTraitanceForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        fetch(`${U.ajouterSousTraitance}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeAddSousTraitanceModal();
                rechargerRessourcesOuvertes();
                showSuccessMessage(data.message);
            } else {
                alert('Erreur: ' + JSON.stringify(data.errors));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de l\'ajout.');
        });
    }

    function handleEditSousTraitance(form) {
        const designationInput = document.getElementById('editSousTraitanceDesignation');
        let isValid = true;

        if (!designationInput.value.trim()) {
            designationInput.classList.add('border-red-500');
            document.querySelector('#editSousTraitanceForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            designationInput.classList.remove('border-red-500');
            document.querySelector('#editSousTraitanceForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        const id = document.getElementById('editSousTraitanceId').value;

        fetch(`${U.modifierSousTraitance.replace('0', id)}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeEditSousTraitanceModal();
                rechargerRessourcesOuvertes(parseInt(id, 10));
                showSuccessMessage(data.message);
            } else {
                alert('Erreur lors de la modification.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de la modification.');
        });
    }

    // Consommables
    function handleAddConsommable(form) {
        const designationInput = document.getElementById('addConsommableDesignation');
        let isValid = true;

        if (!designationInput.value.trim()) {
            designationInput.classList.add('border-red-500');
            document.querySelector('#addConsommableForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            designationInput.classList.remove('border-red-500');
            document.querySelector('#addConsommableForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        fetch(`${U.ajouterConsommable}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeAddConsommableModal();
                rechargerRessourcesOuvertes();
                showSuccessMessage(data.message);
            } else {
                alert('Erreur: ' + JSON.stringify(data.errors));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de l\'ajout.');
        });
    }

    function handleEditConsommable(form) {
        const designationInput = document.getElementById('editConsommableDesignation');
        let isValid = true;

        if (!designationInput.value.trim()) {
            designationInput.classList.add('border-red-500');
            document.querySelector('#editConsommableForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            designationInput.classList.remove('border-red-500');
            document.querySelector('#editConsommableForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        const id = document.getElementById('editConsommableId').value;

        fetch(`${U.modifierConsommable.replace('0', id)}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeEditConsommableModal();
                rechargerRessourcesOuvertes(parseInt(id, 10));
                showSuccessMessage(data.message);
            } else {
                alert('Erreur lors de la modification.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de la modification.');
        });
    }

    // Fournitures
    function handleAddFourniture(form) {
        const designationInput = document.getElementById('addFournitureDesignation');
        let isValid = true;

        if (!designationInput.value.trim()) {
            designationInput.classList.add('border-red-500');
            document.querySelector('#addFournitureForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            designationInput.classList.remove('border-red-500');
            document.querySelector('#addFournitureForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        fetch(`${U.ajouterFourniture}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeAddFournitureModal();
                rechargerRessourcesOuvertes();
                showSuccessMessage(data.message);
            } else {
                alert('Erreur: ' + JSON.stringify(data.errors));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de l\'ajout.');
        });
    }

    function handleEditFourniture(form) {
        const designationInput = document.getElementById('editFournitureDesignation');
        let isValid = true;

        if (!designationInput.value.trim()) {
            designationInput.classList.add('border-red-500');
            document.querySelector('#editFournitureForm .invalid-feedback').classList.remove('hidden');
            isValid = false;
        } else {
            designationInput.classList.remove('border-red-500');
            document.querySelector('#editFournitureForm .invalid-feedback').classList.add('hidden');
        }

        if (!isValid) return;

        const formData = new FormData(form);
        const id = document.getElementById('editFournitureId').value;

        fetch(`${U.modifierFourniture.replace('0', id)}?modal=true`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeEditFournitureModal();
                rechargerRessourcesOuvertes(parseInt(id, 10));
                showSuccessMessage(data.message);
            } else {
                alert('Erreur lors de la modification.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Une erreur est survenue lors de la modification.');
        });
    }

    window.filterMaterielTable = function() {
        const search = (document.getElementById('materielSearchInput')?.value || '').toLowerCase().trim();
        const typeId = document.getElementById('materielTypeFilter')?.value || '';
        const rows = document.querySelectorAll('#materielTable tbody tr');
        let visibles = 0;

        rows.forEach(row => {
            const designation = row.dataset.designation || '';
            const rowTypeId = row.dataset.typeId || '';
            const matchSearch = !search || designation.includes(search);
            const matchType = !typeId || rowTypeId === typeId;
            const visible = matchSearch && matchType;
            row.classList.toggle('hidden', !visible);
            if (visible) visibles++;
        });

        document.getElementById('materielNoResult')?.classList.toggle('hidden', visibles > 0);

        // Réinitialiser la sélection quand le filtre change (évite les faux positifs)
        document.querySelectorAll('#materielTable .materiel-row-checkbox').forEach(cb => {
            const row = cb.closest('tr');
            if (row.classList.contains('hidden')) cb.checked = false;
        });
        if (typeof updateMaterielSelectionBar === 'function') {
            updateMaterielSelectionBar();
        }
    };
    
    // ============================================================
    // Sélection multiple + suppression en masse
    // ============================================================

    window.toggleSelectAllMateriel = function(checkbox) {
        const rows = document.querySelectorAll('#materielTable tbody tr:not(.hidden)');
        rows.forEach(row => {
            const cb = row.querySelector('.materiel-row-checkbox');
            if (cb) cb.checked = checkbox.checked;
        });
        updateMaterielSelectionBar();
    };

    window.updateMaterielSelectionBar = function() {
        const checkboxes = document.querySelectorAll('#materielTable .materiel-row-checkbox:checked');
        const bar = document.getElementById('materielBulkBar');
        const count = document.getElementById('materielBulkCount');
        if (!bar || !count) return;

        const n = checkboxes.length;
        if (n > 0) {
            bar.classList.remove('hidden');
            count.textContent = n;
        } else {
            bar.classList.add('hidden');
        }

        // Synchroniser la case "Tout sélectionner"
        const all = document.getElementById('materielSelectAll');
        if (all) {
            const total = document.querySelectorAll('#materielTable tbody tr:not(.hidden)').length;
            all.checked = (n > 0 && n === total);
            all.indeterminate = (n > 0 && n < total);
        }
    };

    window.clearMaterielSelection = function() {
        document.querySelectorAll('#materielTable .materiel-row-checkbox').forEach(cb => cb.checked = false);
        const all = document.getElementById('materielSelectAll');
        if (all) { all.checked = false; all.indeterminate = false; }
        updateMaterielSelectionBar();
    };

    window.supprimerSelectionMateriel = function() {
        const ids = Array.from(
            document.querySelectorAll('#materielTable .materiel-row-checkbox:checked')
        ).map(cb => cb.value);

        if (ids.length === 0) return;

        const msg = ids.length === 1
            ? `Supprimer ce matériel ?`
            : `⚠️ Supprimer ${ids.length} matériels ?\n\nCette action est irréversible.`;
        if (!confirm(msg)) return;

        // Double confirmation pour les gros volumes
        if (ids.length > 10) {
            if (!confirm(`Confirmer la suppression de ${ids.length} matériels ?`)) return;
        }

        fetch(U.supprimerMaterielMasse, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ ids: ids })
        })
        .then(async r => {
            const data = await r.json();
            if (!r.ok || !data.success) throw data;
            return data;
        })
        .then(data => {
            showSuccessMessage(data.message || `${ids.length} matériel(s) supprimé(s).`);
            // Recharger uniquement le conteneur ouvert (préserve l'accordéon)
            if (typeof rechargerRessourcesOuvertes === 'function') {
                rechargerRessourcesOuvertes();
            } else {
                loadModule(U.partialCategoriesCharges, 'menu-personnel');
            }
        })
        .catch(error => {
            console.error('Suppression en masse:', error);
            showErrorMessage(error.message || 'Erreur lors de la suppression.');
        });
    };

    // ============================================================
    // Import de matériel depuis un tableur
    // ============================================================

    window.openImportMaterielModal = function() {
        document.getElementById('importMaterielText').value = '';
        document.getElementById('importHasHeader').checked = true;
        document.getElementById('importCreateTypes').checked = false;
        document.getElementById('importUpdateExisting').checked = false;
        document.getElementById('importMaterielStep1').classList.remove('hidden');
        document.getElementById('importMaterielStep2').classList.add('hidden');
        document.getElementById('importMaterielRapport').innerHTML = '';
        document.getElementById('importMaterielModal').style.display = 'block';
        document.getElementById('modalBackdrop').style.display = 'block';
    };

    window.closeImportMaterielModal = function() {
        document.getElementById('importMaterielModal').style.display = 'none';
        document.getElementById('modalBackdrop').style.display = 'none';
    };

    window.retourImportMateriel = function() {
        document.getElementById('importMaterielStep1').classList.remove('hidden');
        document.getElementById('importMaterielStep2').classList.add('hidden');
    };

    window.analyserImportMateriel = function() {
        const texte = document.getElementById('importMaterielText').value;
        if (!texte.trim()) {
            alert('Collez d\'abord des données.');
            return;
        }
        envoyerImportMateriel(true);
    };

    window.confirmerImportMateriel = function() {
        if (!confirm('Confirmer l\'import ? Les données seront enregistrées.')) return;
        envoyerImportMateriel(false);
    };

    function envoyerImportMateriel(dryRun) {
        const texte = document.getElementById('importMaterielText').value;
        const hasHeader = document.getElementById('importHasHeader').checked ? 'true' : 'false';
        const createTypes = document.getElementById('importCreateTypes').checked ? 'true' : 'false';
        const updateExisting = document.getElementById('importUpdateExisting').checked ? 'true' : 'false';

        const formData = new FormData();
        formData.append('texte', texte);
        formData.append('has_header', hasHeader);
        formData.append('create_types', createTypes);
        formData.append('update_existing', updateExisting);
        formData.append('csrfmiddlewaretoken', getCsrfToken());

        const url = '/materiel/importer/?dry_run=' + (dryRun ? '1' : '0');

        fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken(),
            },
        })
        .then(async response => {
            const data = await response.json();
            if (!response.ok) throw data;
            return data;
        })
        .then(data => {
            renderImportMaterielRapport(data, dryRun);
            if (!dryRun) {
                // Import réel : recharger la liste après
                setTimeout(() => {
                    closeImportMaterielModal();
                    loadModule(U.partialMateriel, 'menu-materiel');
                }, 1500);
            }
        })
        .catch(error => {
            console.error('Import error:', error);
            alert('Erreur lors de l\'import : ' + (error.message || JSON.stringify(error)));
        });
    }

    function renderImportMaterielRapport(data, dryRun) {
        const container = document.getElementById('importMaterielRapport');
        let html = '';

        // Titre
        const titre = dryRun ? 'Aperçu (rien n\'a été enregistré)' : 'Import effectué';
        html += `<p class="text-cyan-300 font-semibold mb-3">${titre}</p>`;

        // Warnings
        if (data.warnings && data.warnings.length) {
            html += '<div class="p-2 bg-yellow-900/40 border border-yellow-700 rounded text-yellow-200 text-xs space-y-1">';
            data.warnings.forEach(w => { html += `<div><i class="fas fa-info-circle mr-1"></i> ${w}</div>`; });
            html += '</div>';
        }

        // Créés
        if (data.created && data.created.length) {
            html += `<div class="p-3 bg-green-900/40 border border-green-700 rounded">`;
            html += `<p class="text-green-300 font-semibold mb-1"><i class="fas fa-check-circle mr-1"></i> ${data.created.length} matériel(s) ${dryRun ? 'seront créés' : 'créés'} :</p>`;
            html += '<ul class="list-disc list-inside text-green-200 text-xs space-y-0.5">';
            data.created.forEach(item => {
                html += `<li>${item.designation} <span class="text-green-400">(${item.type})</span></li>`;
            });
            html += '</ul></div>';
        }

        // Mis à jour
        if (data.updated && data.updated.length) {
            html += `<div class="p-3 bg-blue-900/40 border border-blue-700 rounded">`;
            html += `<p class="text-blue-300 font-semibold mb-1"><i class="fas fa-edit mr-1"></i> ${data.updated.length} matériel(s) ${dryRun ? 'seront mis à jour' : 'mis à jour'} :</p>`;
            html += '<ul class="list-disc list-inside text-blue-200 text-xs space-y-0.5">';
            data.updated.forEach(item => {
                html += `<li>${item.designation} <span class="text-blue-400">(${item.type})</span></li>`;
            });
            html += '</ul></div>';
        }

        // Ignorés
        if (data.ignored && data.ignored.length) {
            html += `<div class="p-3 bg-yellow-900/40 border border-yellow-700 rounded">`;
            html += `<p class="text-yellow-300 font-semibold mb-1"><i class="fas fa-exclamation-triangle mr-1"></i> ${data.ignored.length} ligne(s) ignorée(s) :</p>`;
            html += '<ul class="list-disc list-inside text-yellow-200 text-xs space-y-0.5">';
            data.ignored.forEach(item => {
                html += `<li>Ligne ${item.numero} : ${item.designation} — ${item.raison}</li>`;
            });
            html += '</ul></div>';
        }

        // Erreurs
        if (data.errors && data.errors.length) {
            html += `<div class="p-3 bg-red-900/40 border border-red-700 rounded">`;
            html += `<p class="text-red-300 font-semibold mb-1"><i class="fas fa-times-circle mr-1"></i> ${data.errors.length} ligne(s) en erreur :</p>`;
            html += '<ul class="list-disc list-inside text-red-200 text-xs space-y-0.5">';
            data.errors.forEach(item => {
                html += `<li>Ligne ${item.numero} : ${item.raison}</li>`;
            });
            html += '</ul></div>';
        }

        // Résumé si vide
        if (!data.created?.length && !data.updated?.length && !data.ignored?.length && !data.errors?.length) {
            html += '<p class="text-gray-400">Aucune ligne exploitable.</p>';
        }

        container.innerHTML = html;
        document.getElementById('importMaterielStep1').classList.add('hidden');
        document.getElementById('importMaterielStep2').classList.remove('hidden');

        // Désactiver le bouton "Confirmer" si dry_run était déjà un import réel
        if (!dryRun) {
            document.getElementById('importMaterielConfirmBtn').disabled = true;
            document.getElementById('importMaterielConfirmBtn').classList.add('opacity-50', 'cursor-not-allowed');
        }
    }
    // ============================================================
    // Récupération du jeton CSRF
    // ============================================================
    window.getCsrfToken = function() {
        // 1. Depuis un champ de formulaire (le plus fiable)
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        if (input && input.value) return input.value;

        // 2. Depuis le cookie csrftoken
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        if (match) return match[1];

        // 3. Fallback : chercher dans tous les cookies
        for (const cookie of document.cookie.split(';')) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') return value;
        }

        console.warn('getCsrfToken: aucun token trouvé');
        return '';
    };

    // ═══════════════════════════════════════════════════════════════
    // RECHARGEMENT DES RESSOURCES DANS LES ACCORDÉONS CATÉGORIES
    // ═══════════════════════════════════════════════════════════════

    /**
     * Recharge le contenu d'un conteneur de ressource (ex : materiel)
     * dans une catégorie donnée, en respectant son état ouvert/fermé.
     */
    window.reloadCategoryResource = function (categoryId) {
        const container = document.getElementById(`category-resource-${categoryId}`);
        if (!container) {
            console.warn(`Conteneur #category-resource-${categoryId} introuvable`);
            return Promise.resolve();
        }

        const button = document.querySelector(`[data-resource-target="category-resource-${categoryId}"]`);
        if (!button || !button.dataset.resourceUrl) {
            console.warn('Bouton toggle ou URL introuvable pour la catégorie', categoryId);
            return Promise.resolve();
        }

        const etaitOuvert = !container.classList.contains('hidden');

        return fetch(button.dataset.resourceUrl, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(r => r.text())
        .then(html => {
            container.innerHTML = html;
            container.dataset.loaded = 'true';
            // Respecter l'état précédent (ne pas rouvrir si c'était fermé)
            container.classList.toggle('hidden', !etaitOuvert);
        })
        .catch(err => {
            console.error('Erreur rechargement ressource:', err);
        });
    };

    /**
     * Recharge uniquement les conteneurs de ressources actuellement OUVERTS,
     * sans recharger tout le module. Préserve l'état ouvert/fermé,
     * les filtres internes et la position de scroll.
     *
     * @param {number|null} focusMaterielId - ID du matériel sur lequel remettre le focus (optionnel)
     */
    window.rechargerRessourcesOuvertes = function (focusMaterielId) {
        const conteneurs = document.querySelectorAll('[data-category-resource]:not(.hidden)');
        const promises = [];

        conteneurs.forEach(container => {
            const match = container.id.match(/category-resource-(\d+)/);
            if (!match) return;
            const categoryId = match[1];
            const button = document.querySelector(`[data-resource-target="category-resource-${categoryId}"]`);
            if (!button || !button.dataset.resourceUrl) return;

            const p = fetch(button.dataset.resourceUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(r => r.text())
            .then(html => {
                container.innerHTML = html;
                container.dataset.loaded = 'true';
                // On ne touche pas à .hidden : le conteneur reste ouvert
            })
            .catch(err => console.error('Erreur rechargement ressource:', err));

            promises.push(p);
        });

        // Restaurer le focus sur le bouton d'édition de l'élément modifié
        if (focusMaterielId) {
            Promise.all(promises).then(() => {
                const btn = document.querySelector(`[data-edit-materiel-button][data-id="${focusMaterielId}"]`);
                if (btn) btn.focus({ preventScroll: true });
            });
        }
    };

    // ═══════════════════════════════════════════════════════════════
    // TOASTS — Système de notifications flash unifié
    // ═══════════════════════════════════════════════════════════════

    /**
     * Récupère ou crée le conteneur de toasts (bas-droite, empilable)
     */
    function getOrCreateToastContainer() {
        let container = document.getElementById('toast-container');
        if (container) return container;

        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed bottom-6 right-6 z-[9999] flex flex-col gap-3 pointer-events-none';
        // Sur mobile : largeur limitée
        container.style.cssText = `
            position: fixed;
            bottom: 1.5rem;
            right: 1.5rem;
            left: auto;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            z-index: 9999;
            pointer-events: none;
            max-width: calc(100vw - 3rem);
        `;
        document.body.appendChild(container);
        return container;
    }

    /**
     * Affiche un toast générique
     * @param {string} message - Texte à afficher
     * @param {string} type    - 'success' | 'error' | 'warning' | 'info'
     * @param {number} duration - Durée en ms (défaut 3500)
     */
    window.showToast = function (message, type = 'info', duration = 3500) {
        const container = getOrCreateToastContainer();

        const icons = {
            success: 'fa-check-circle',
            error: 'fa-circle-exclamation',
            warning: 'fa-triangle-exclamation',
            info: 'fa-circle-info',
        };

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <i class="fas ${icons[type] || icons.info}"></i>
            <span class="toast-message">${message}</span>
            <button type="button" class="toast-close" aria-label="Fermer">
                <i class="fas fa-times"></i>
            </button>
        `;

        // Fermeture manuelle
        toast.querySelector('.toast-close').addEventListener('click', () => hideToast(toast));

        container.appendChild(toast);

        // Auto-hide
        const timer = setTimeout(() => hideToast(toast), duration);
        toast._toastTimer = timer;
    };

    /**
     * Cache un toast avec animation
     */
    function hideToast(toast) {
        if (!toast || toast._hiding) return;
        toast._hiding = true;
        clearTimeout(toast._toastTimer);

        toast.classList.add('toast-hiding');
        toast.addEventListener('animationend', () => {
            toast.remove();
            // Nettoyer le conteneur s'il est vide
            const container = document.getElementById('toast-container');
            if (container && container.children.length === 0) container.remove();
        }, { once: true });
    }

    // ── Raccourcis (compatibilité avec l'existant) ──
    window.showSuccessMessage = (msg) => window.showToast(msg, 'success');
    window.showErrorMessage   = (msg) => window.showToast(msg, 'error', 5000);
    window.showWarningMessage = (msg) => window.showToast(msg, 'warning', 4500);
    window.showInfoMessage    = (msg) => window.showToast(msg, 'info', 4000);
    // ═══════════════════════════════════════════════════════════════
    // EXPOSITION GLOBALE DES FONCTIONS DE FERMETURE
    // (nécessaire pour les onclick="..." dans les templates modals)
    // ═══════════════════════════════════════════════════════════════
    Object.assign(window, {
        // Ingénieurs
        closeEditIngenieurModal, closeAddIngenieurModal,
        // Clients
        closeEditClientModal, closeAddClientModal,
        // Entreprises
        closeEditEntrepriseModal, closeAddEntrepriseModal,
        // Personnel
        closeEditPersonnelModal, closeAddPersonnelModal,
        // Matériel
        closeEditMaterielModal, closeAddMaterielModal,
        // Types de matériel
        closeEditTypeMaterielModal, closeAddTypeMaterielModal,
        // Transport
        closeEditTransportModal, closeAddTransportModal,
        // Locations
        closeEditLocationModal, closeAddLocationModal,
        // Sous-traitances
        closeEditSousTraitanceModal, closeAddSousTraitanceModal,
        // Consommables
        closeEditConsommableModal, closeAddConsommableModal,
        // Fournitures
        closeEditFournitureModal, closeAddFournitureModal,
        // Global
        closeAllModals,
    });
})();