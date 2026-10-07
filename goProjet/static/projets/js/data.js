(function () {
    'use strict';

    const U = window.DATA_URLS;
    const $ = (id) => document.getElementById(id);
    const $$ = (sel, root = document) => root.querySelector(sel);
    const $$all = (sel, root = document) => root.querySelectorAll(sel);

    /* ═══════════════════════════════════════════════════════════
       REGISTRE DES ENTITÉS
       ═══════════════════════════════════════════════════════════ */

    const ENTITIES = {
        // ═══════════════════════════════════════════════════════════
        // MODULES DIRECTS (items sidebar)
        // ═══════════════════════════════════════════════════════════
        ingenieur: {
            addUrl:    U.ajouterIngenieur,
            editUrl:   U.modifierIngenieur,
            deleteUrl: U.supprimerIngenieur,
            partial:   U.partialIngenieurs,
            menuId:    'menu-ingenieurs',
            reload:    'module',
            fields:    ['id', 'nom'],
            required:  ['nom'],
            label:     'cet ingénieur',
        },

        client: {
            addUrl:    U.ajouterClient,
            editUrl:   U.modifierClient,
            deleteUrl: U.supprimerClient,
            partial:   U.partialClients,
            menuId:    'menu-clients',
            reload:    'module',
            fields:    ['id', 'nom', 'contact', 'email', 'telephone', 'adresse'],
            required:  ['nom'],
            label:     'ce client',
        },

        entreprise: {
            addUrl:    U.ajouterEntreprise,
            editUrl:   U.modifierEntreprise,
            deleteUrl: U.supprimerEntreprise,
            partial:   U.partialEntreprises,
            menuId:    'menu-entreprises',
            reload:    'module',
            fields:    ['id', 'nom', 'contact', 'email', 'telephone', 'adresse'],
            required:  ['nom'],
            label:     'cette entreprise',
        },

        typeMateriel: {
            addUrl:    U.ajouterTypeMateriel,
            editUrl:   U.modifierTypeMateriel,
            deleteUrl: U.supprimerTypeMateriel,
            partial:   U.partialTypesMateriel,
            menuId:    'menu-types-materiel',
            reload:    'module',
            fields:    ['id', 'nom', 'icone', 'actif'],
            required:  ['nom'],
            label:     'ce type de matériel',
            onOpenEdit: (modal, data) => {
                updateIconePreview(modal);
            },
        },

        // ═══════════════════════════════════════════════════════════
        // RESSOURCES IMBRIQUÉES (accordéon catégories)
        // ═══════════════════════════════════════════════════════════
        categorie: {
            addUrl:    U.ajouterCategorie,
            editUrl:   U.modifierCategorie,
            deleteUrl: U.supprimerCategorie,
            partial:   U.partialCategoriesCharges,
            menuId:    'menu-categories',
            reload:    'module',
            fields:    ['id', 'code', 'nom', 'ordre', 'actif'],
            required:  ['code', 'nom'],
            label:     'cette catégorie',
        },
        // Ressources 
        personnel: {
            addUrl:    U.ajouterPersonnel,
            editUrl:   U.modifierPersonnel,
            deleteUrl: U.supprimerPersonnel,
            partial:   U.partialPersonnel,
            reload:    'resources',
            fields:    ['id', 'nom', 'fonction', 'telephone', 'unite', 'tarif', 'actif'],
            required:  ['nom'],
            label:     'ce membre du personnel',
        },

        materiel: {
            addUrl:    U.ajouterMateriel,
            editUrl:   U.modifierMateriel,
            deleteUrl: U.supprimerMateriel,
            partial:   U.partialMateriel,
            reload:    'resources',
            fields:    ['id', 'designation', 'type_materiel', 'immatriculation', 'unite', 'prix_unitaire', 'actif'],
            required:  ['designation'],
            label:     'ce matériel',
            onOpenEdit: (modal, data) => {
                if (typeof rebuildTypeMaterielSelect !== 'function') return;
                rebuildTypeMaterielSelect(
                    'editMaterielTypeMateriel',
                    data.typeId,
                    data.typeActif === 'false' ? { id: data.typeId, nom: data.typeNom } : null
                );
            },
        },

        transport: {
            addUrl:    U.ajouterTransport,
            editUrl:   U.modifierTransport,
            deleteUrl: U.supprimerTransport,
            partial:   U.partialTransports,
            reload:    'resources',
            fields:    ['id', 'designation', 'type_transport', 'transporteur', 'unite', 'prix_unitaire', 'actif'],
            required:  ['designation'],
            label:     'ce transport',
        },

        location: {
            addUrl:    U.ajouterLocation,
            editUrl:   U.modifierLocation,
            deleteUrl: U.supprimerLocation,
            partial:   U.partialLocations,
            reload:    'resources',
            fields:    ['id', 'designation', 'type_materiel', 'locataire', 'unite', 'prix_unitaire', 'actif'],
            required:  ['designation'],
            label:     'cette location',
        },

        sousTraitance: {
            addUrl:    U.ajouterSousTraitance,
            editUrl:   U.modifierSousTraitance,
            deleteUrl: U.supprimerSousTraitance,
            partial:   U.partialSousTraitances,
            reload:    'resources',
            fields:    ['id', 'designation', 'type_sous_traitance', 'prestataire', 'unite', 'prix_unitaire', 'actif'],
            required:  ['designation'],
            label:     'cette sous-traitance',
        },

        consommable: {
            addUrl:    U.ajouterConsommable,
            editUrl:   U.modifierConsommable,
            deleteUrl: U.supprimerConsommable,
            partial:   U.partialConsommables,
            reload:    'resources',
            fields:    ['id', 'designation', 'type_consommable', 'fournisseur', 'unite', 'prix_unitaire', 'actif'],
            required:  ['designation'],
            label:     'ce consommable',
        },

        fourniture: {
            addUrl:    U.ajouterFourniture,
            editUrl:   U.modifierFourniture,
            deleteUrl: U.supprimerFourniture,
            partial:   U.partialFournitures,
            reload:    'resources',
            fields:    ['id', 'designation', 'type_fourniture', 'fournisseur', 'unite', 'prix_unitaire', 'actif'],
            required:  ['designation'],
            label:     'cette fourniture',
        },
    };

    /* ═══════════════════════════════════════════════════════════
       UTILITAIRES
       ═══════════════════════════════════════════════════════════ */
    function capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    function getModalId(entity, mode) {
        return `${mode}${capitalize(entity)}Modal`;
    }

    function getModal(entity, mode) {
        return document.getElementById(getModalId(entity, mode));
    }

    function getBackdrop() {
        return document.getElementById('modalBackdrop');
    }

    function getCsrfToken() {
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        if (input && input.value) return input.value;
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : '';
    }

    // /* ═══════════════════════════════════════════════════════════
    //    TOASTS (notifications flash)
    //    ═══════════════════════════════════════════════════════════ */
    // function getOrCreateToastContainer() {
    //     let container = document.getElementById('toast-container');
    //     if (container) return container;

    //     container = document.createElement('div');
    //     container.id = 'toast-container';
    //     container.style.cssText = `
    //         position: fixed;
    //         bottom: 1.5rem;
    //         right: 1.5rem;
    //         display: flex;
    //         flex-direction: column;
    //         gap: 0.75rem;
    //         z-index: 9999;
    //         pointer-events: none;
    //         max-width: calc(100vw - 3rem);
    //     `;
    //     document.body.appendChild(container);
    //     return container;
    // }

    // function showToast(message, type = 'info', duration = 3500) {
    //     const container = getOrCreateToastContainer();
    //     const icons = {
    //         success: 'fa-check-circle',
    //         error:   'fa-circle-exclamation',
    //         warning: 'fa-triangle-exclamation',
    //         info:    'fa-circle-info',
    //     };

    //     const toast = document.createElement('div');
    //     toast.className = `toast toast-${type}`;
    //     toast.style.pointerEvents = 'auto';
    //     toast.innerHTML = `
    //         <i class="fas ${icons[type] || icons.info}"></i>
    //         <span class="toast-message">${message}</span>
    //         <button type="button" class="toast-close" aria-label="Fermer">
    //             <i class="fas fa-times"></i>
    //         </button>
    //     `;

    //     toast.querySelector('.toast-close').addEventListener('click', () => hideToast(toast));
    //     container.appendChild(toast);

    //     toast._toastTimer = setTimeout(() => hideToast(toast), duration);
    // }

    // function hideToast(toast) {
    //     if (!toast || toast._hiding) return;
    //     toast._hiding = true;
    //     clearTimeout(toast._toastTimer);

    //     const remove = () => {
    //         if (toast.parentElement) toast.remove();
    //         const container = document.getElementById('toast-container');
    //         if (container && container.children.length === 0) container.remove();
    //     };

    //     toast.classList.add('toast-hiding');
    //     const fallback = setTimeout(remove, 350);
    //     toast.addEventListener('animationend', () => {
    //         clearTimeout(fallback);
    //         remove();
    //     }, { once: true });
    // }

    // window.showToast = showToast;
    // window.showSuccessMessage = (msg) => showToast(msg, 'success');
    // window.showErrorMessage   = (msg) => showToast(msg, 'error', 5000);
    // window.showWarningMessage = (msg) => showToast(msg, 'warning', 4500);
    // window.showInfoMessage    = (msg) => showToast(msg, 'info');

    // ═══════════════════════════════════════════════════════════
    // MODALES — OUVERTURE / FERMETURE
    // ═══════════════════════════════════════════════════════════ 
    function openModal(entity, mode, data = {}) {
        const cfg = ENTITIES[entity];
        if (!cfg) return console.warn('[openModal] Entité inconnue :', entity);

        const modal = getModal(entity, mode);
        if (!modal) return console.warn('[openModal] Modal introuvable :', getModalId(entity, mode));

        const form = modal.querySelector('form');
        if (!form) return console.warn('[openModal] Form absent dans', modal.id);

        clearFormErrors(form);

        if (mode === 'add') {
            form.reset();
        }

        if (mode === 'edit') {
            cfg.fields.forEach(field => {
                const input = form.querySelector(`[name="${field}"]`);
                if (!input) return;
                const value = data[field];
                if (input.type === 'checkbox') {
                    input.checked = value === true || value === 'true' || value === 'on';
                } else if (input.type === 'number') {
                    input.value = normalizeNumber(value);
                } else {
                    input.value = value ?? '';
                }
            });
        }

        if (typeof cfg.onOpenEdit === 'function' && mode === 'edit') {
            try {
                cfg.onOpenEdit(modal, data);
            } catch (err) {
                console.error(`[openModal] onOpenEdit(${entity}) :`, err);
            }
        }

        modal.style.display = 'block';
        const backdrop = getBackdrop();
        if (backdrop) backdrop.style.display = 'block';

        const firstInput = form.querySelector('input:not([type="hidden"]):not([disabled]), textarea, select');
        if (firstInput) setTimeout(() => firstInput.focus(), 50);
    }

    // ═══════════════════════════════════════════════════════════
    // MODALES — FERMETURE
    // ═══════════════════════════════════════════════════════════

    function closeModal(entity, mode) {
        const modal = getModal(entity, mode);
        if (!modal) return;

        modal.style.display = 'none';
        const form = modal.querySelector('form');
        if (form) {
            form.classList.remove('was-validated');
            clearFormErrors(form);
        }

        if (!document.querySelector('.modal[style*="block"]')) {
            const backdrop = getBackdrop();
            if (backdrop) backdrop.style.display = 'none';
        }
    }

    function closeAllModals() {
        Object.keys(ENTITIES).forEach(entity => {
            closeModal(entity, 'add');
            closeModal(entity, 'edit');
        });
        const backdrop = getBackdrop();
        if (backdrop) backdrop.style.display = 'none';
    }

    /* ═══════════════════════════════════════════════════════════
       VALIDATION DE FORMULAIRE
       ═══════════════════════════════════════════════════════════ */
    function clearFormErrors(form) {
        form.querySelectorAll('.invalid-feedback').forEach(el => el.classList.add('hidden'));
        form.querySelectorAll('.border-red-500').forEach(el => el.classList.remove('border-red-500'));
    }

    function showFieldError(input) {
        input.classList.add('border-red-500');
        const feedback = input.parentElement.querySelector('.invalid-feedback');
        if (feedback) feedback.classList.remove('hidden');
    }

    function validateForm(form, requiredFields = []) {
        clearFormErrors(form);
        let valid = true;
        let firstError = null;

        requiredFields.forEach(field => {
            const input = form.querySelector(`[name="${field}"]`);
            if (!input) return;

            const value = input.type === 'checkbox'
                ? input.checked
                : (input.value || '').trim();

            if (!value) {
                showFieldError(input);
                valid = false;
                if (!firstError) firstError = input;
            }
        });

        if (firstError) firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return valid;
    }

    /* ═══════════════════════════════════════════════════════════
       SOUMISSION
       ═══════════════════════════════════════════════════════════ */
    function buildEditUrl(template, id) {
        return template.replace('/0/', `/${id}/`);
    }

    async function reloadEntity(entity, focusId = null) {
        const cfg = ENTITIES[entity];
        if (!cfg) return;

        if (cfg.reload === 'resources') {
            // Appel direct de la fonction locale (plus de garde "typeof")
            await rechargerRessourcesOuvertes(focusId);
        } else if (cfg.partial && cfg.menuId) {
            await loadModule(cfg.partial, cfg.menuId);
        }
    }

    async function submitForm(form, entity, mode) {
        const cfg = ENTITIES[entity];
        if (!cfg) return showErrorMessage(`Entité inconnue : ${entity}`);

        if (!validateForm(form, cfg.required)) return;

        const idInput = form.querySelector('[name="id"]');
        const id = idInput ? idInput.value : null;

        const baseUrl = mode === 'add' ? cfg.addUrl : buildEditUrl(cfg.editUrl, id);
        const url = `${baseUrl}?modal=true`;

        let data;
        try {
            const formData = new FormData(form);
            const res = await fetch(url, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken') || getCsrfToken(),
                },
            });
            data = await res.json();
        } catch (err) {
            console.error(`[submitForm ${entity}/${mode}]`, err);
            return showErrorMessage('Erreur réseau. Vérifiez votre connexion.');
        }

        if (!data.success) {
            const detail = data.message
                || (data.errors ? JSON.stringify(data.errors) : null)
                || 'Erreur lors de l\'enregistrement.';
            return showErrorMessage(detail);
        }

        // Fermeture de la modale UNIQUEMENT si elle existe (cas catégories : non)
        const modal = getModal(entity, mode);
        if (modal) closeModal(entity, mode);

        try {
            await reloadEntity(entity, id);
        } catch (err) {
            console.error(`[reloadEntity ${entity}]`, err);
        }

        showSuccessMessage(data.message || 'Enregistré avec succès.');
    }

    // ═══════════════════════════════════════════════════════════
    // MODALES — SUPPRESSION
    // ═══════════════════════════════════════════════════════════
    async function deleteEntity(entity, id) {
        const cfg = ENTITIES[entity];
        if (!cfg || !cfg.deleteUrl) return;

        // Confirmation
        const label = cfg.label || entity;
        if (!confirm(`Supprimer ${label} ? Cette action est irréversible.`)) return;

        const url = buildEditUrl(cfg.deleteUrl, id);  // même helper /0/ → /id/

        let data;
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken(),
                },
            });
            data = await res.json();
        } catch (err) {
            console.error(`[deleteEntity ${entity}]`, err);
            return showErrorMessage('Erreur réseau. Vérifiez votre connexion.');
        }

        if (!data.success) {
            return showErrorMessage(data.message || 'Impossible de supprimer.');
        }

        await reloadEntity(entity);
        showSuccessMessage(data.message || 'Supprimé avec succès.');
    }

    
    // MISE À JOUR DE L'APERÇU DE L'ICÔNE
    function updateIconePreview(modal) {
        if (!modal) return;
        const select = modal.querySelector('[name="icone"]');
        const preview = modal.querySelector('[data-icone-preview]');
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

    /* ═══════════════════════════════════════════════════════════
       CHARGEMENT DE MODULE (sidebar)
       ═══════════════════════════════════════════════════════════ */
    let activeMenuItemId = null;

    function closeMobileSidebar() {
        $('mobileSidebar')?.classList.remove('open');
        $('sidebarOverlay')?.classList.remove('open');
    }

    function loadModule(url, menuItemId) {
        if (activeMenuItemId) {
            $(activeMenuItemId)?.classList.remove('active-menu-item');
        }
        $(menuItemId)?.classList.add('active-menu-item');
        activeMenuItemId = menuItemId;

        const area = $('content-area');
        if (!area) return Promise.resolve();

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

    /**
     * Normalise une valeur numérique pour un <input type="number">.
     * - Supprime les espaces (séparateurs de milliers)
     * - Remplace la virgule décimale par un point
     * - Renvoie une chaîne vide si la valeur est nulle/undefined
     */
    function normalizeNumber(value) {
        if (value === null || value === undefined) return '';
        const n = Number(String(value).replace(/\s/g, '').replace(',', '.'));
        return isNaN(n) ? '' : String(n);
    }

    /**
     * Reconstruit le <select> des types de matériel dans une modal.
     * Utilise window.MATERIEL_TYPES (injecté par le partial materiel.html).
     *
     * @param {string} selectId     - ID du <select> à remplir
     * @param {number|string} selectedId - ID du type à sélectionner
     * @param {object|null} inactiveType - { id, nom } du type inactif (si le matériel est lié à un type désactivé)
     */
    function rebuildTypeMaterielSelect(selectId, selectedId, inactiveType) {
        const select = document.getElementById(selectId);
        if (!select) return console.warn('[rebuildTypeMaterielSelect] select introuvable');

        select.innerHTML = '';

        // Option vide
        const emptyOpt = document.createElement('option');
        emptyOpt.value = '';
        emptyOpt.textContent = '— Non défini —';
        select.appendChild(emptyOpt);

        // Types depuis le DOM
        const types = getMaterielTypes();   // ← au lieu de window.MATERIEL_TYPES
        types.forEach(type => {
            const opt = document.createElement('option');
            opt.value = String(type.id);
            opt.textContent = type.nom;
            select.appendChild(opt);
        });

        // Type inactif
        if (inactiveType && inactiveType.id) {
            const opt = document.createElement('option');
            opt.value = String(inactiveType.id);
            opt.textContent = `${inactiveType.nom} (inactif)`;
            select.appendChild(opt);
        }

        select.value = selectedId != null ? String(selectedId) : '';
    }

    /**
     * Récupère les types de matériel actifs depuis le DOM
     * (data-types du conteneur [data-materiel-module]).
     */
    function getMaterielTypes() {
        const container = document.querySelector('[data-materiel-module]');
        if (!container || !container.dataset.types) return [];
        try {
            return JSON.parse(container.dataset.types);
        } catch (err) {
            console.error('[getMaterielTypes] Parse error:', err);
            return [];
        }
    }
    /* ═══════════════════════════════════════════════════════════════
    RECHARGEMENT DES RESSOURCES IMBRIQUÉES (accordéons catégories)
    ═══════════════════════════════════════════════════════════════ */

    /**
     * Recharge le contenu d'un conteneur de ressource dans une catégorie donnée,
     * en respectant son état ouvert/fermé.
     */
    async function reloadCategoryResource(categoryId) {
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
        try {
            const response = await fetch(button.dataset.resourceUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const html = await response.text();
            container.innerHTML = html;
            container.dataset.loaded = 'true';
            container.classList.toggle('hidden', !etaitOuvert);
        } catch (err) {
            console.error('Erreur rechargement ressource:', err);
        }
    }

    /**
     * Recharge uniquement les conteneurs de ressources actuellement OUVERTS.
     * Utilisé après un ajout / modif / suppression d'une ressource imbriquée
     * (personnel, materiel, transport, etc.).
     *
     * @param {number|string|null} focusId - ID de l'élément modifié (optionnel)
     */
    function rechargerRessourcesOuvertes(focusId) {
        const conteneurs = document.querySelectorAll('[data-category-resource]:not(.hidden)');
        const promises = [];

        if (conteneurs.length === 0) {
            // Aucun accordéon ouvert : rien à rafraîchir visuellement.
            // On informe que la modification est enregistrée.
            return Promise.resolve();
        }

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
            })
            .catch(err => console.error('Erreur rechargement ressource:', err));

            promises.push(p);
        });

        return Promise.all(promises);
    }

    window.loadModule = loadModule;

    /* ═══════════════════════════════════════════════════════════
       DELEGATION D'ÉVÉNEMENTS
       ═══════════════════════════════════════════════════════════ */
    document.body.addEventListener('click', (e) => {
        // 1. Sidebar menu (data-config-menu)
        const menuBtn = e.target.closest('[data-config-menu]');
        if (menuBtn) {
            e.preventDefault();
            const url = menuBtn.dataset.configUrl;
            const menuId = menuBtn.dataset.configTarget;
            if (!url) return;

            document.querySelectorAll('[data-config-menu]').forEach(b => {
                b.classList.toggle('active-menu-item', b === menuBtn);
            });

            loadModule(url, menuId);
            closeMobileSidebar();
            return;
        }

        // 2. Sidebar mobile
        if (e.target.closest('#mobileMenuBtn')) {
            $('mobileSidebar')?.classList.add('open');
            $('sidebarOverlay')?.classList.add('open');
            return;
        }
        if (e.target.closest('#mobileSidebarClose') || e.target.closest('#sidebarOverlay')) {
            closeMobileSidebar();
            return;
        }

        // 3. Bouton "Ajouter"
        const addBtn = e.target.closest('[data-add]');
        if (addBtn) {
            e.preventDefault();
            const entity = addBtn.dataset.entity;
            if (entity) openModal(entity, 'add');
            return;
        }

        // 4. Bouton "Modifier"
        const editBtn = e.target.closest('[data-edit]');
        if (editBtn) {
            e.preventDefault();
            const entity = editBtn.dataset.entity;
            let payload = {};
            try { payload = JSON.parse(editBtn.dataset.payload || '{}'); } catch (_) {}
            if (entity) openModal(entity, 'edit', payload);
            return;
        }
        
        // 6. Bouton "Supprimer"
        const deleteBtn = e.target.closest('[data-delete]');
        if (deleteBtn) {
            e.preventDefault();
            const entity = deleteBtn.dataset.entity;
            const id = deleteBtn.dataset.id;
            if (entity && id) deleteEntity(entity, id);
            return;
        }

        // 5. Fermeture modal (croix, Annuler, etc.)
        const closeBtn = e.target.closest('[data-modal-close]');
        if (closeBtn) {
            e.preventDefault();
            const modal = closeBtn.closest('.modal');
            if (modal) {
                const match = modal.id.match(/^(add|edit)([A-Z]\w+)Modal$/);
                if (match) {
                    const mode = match[1];
                    const entity = match[2].charAt(0).toLowerCase() + match[2].slice(1);
                    closeModal(entity, mode);
                } else {
                    closeAllModals();
                }
            }
            return;
        }

        // Bouton "Importer depuis un tableur"
        const importBtn = e.target.closest('[data-import-materiel-button]');
        if (importBtn) {
            e.preventDefault();
            openImportMaterielModal();
            return;
        }

        // ─── Accordéon ressources (chargement dynamique) ───
        const resourceToggle = e.target.closest('[data-resource-url]');
        if (resourceToggle) {
            e.preventDefault();
            const target = document.getElementById(resourceToggle.dataset.resourceTarget);
            if (!target) return;

            const chevron = resourceToggle.querySelector('.fa-chevron-down, .fa-chevron-up');
            const isOpen = !target.classList.contains('hidden');

            // Fermeture
            if (isOpen) {
                target.classList.add('hidden');
                chevron?.classList.remove('rotate-180');
                return;
            }

            // Ouverture
            target.classList.remove('hidden');
            chevron?.classList.add('rotate-180');

            // Déjà chargé une fois → ne pas re-fetch
            if (target.dataset.loaded === 'true') {
                return;
            }

            // Premier chargement
            target.dataset.loaded = 'loading';
            target.innerHTML = '<p class="py-3 text-sm" style="color: var(--text-muted);">Chargement...</p>';

            fetch(resourceToggle.dataset.resourceUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(r => {
                if (!r.ok) throw new Error('Chargement impossible');
                return r.text();
            })
            .then(html => {
                if (target.dataset.loaded === 'loading') {
                    target.innerHTML = html;
                    target.dataset.loaded = 'true';
                }
            })
            .catch(err => {
                console.error('[resource-toggle]', err);
                target.dataset.loaded = '';
                target.innerHTML = '<p class="py-3 text-sm" style="color: var(--accent-danger);">Impossible de charger le référentiel.</p>';
            });
            return;
        }
    });

    // Soumission de formulaires
    document.body.addEventListener('submit', (e) => {
        const form = e.target.closest('[data-entity-form]');
        if (!form) return;
        e.preventDefault();
        submitForm(form, form.dataset.entity, form.dataset.mode);
    });
    
    // Changement de l'icône : met à jour l'aperçu
    document.body.addEventListener('change', (e) => {
        const select = e.target.closest('[name="icone"]');
        if (!select) return;
        const modal = select.closest('.modal');
        if (modal) updateIconePreview(modal);
    });

    // Échap : ferme toutes les modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeAllModals();
    });

    // Backdrop : ferme toutes les modals
    const backdropEl = getBackdrop();
    if (backdropEl) backdropEl.addEventListener('click', closeAllModals);

    /* ═══════════════════════════════════════════════════════════
       CHARGEMENT PAR DÉFAUT
       ═══════════════════════════════════════════════════════════ */
    document.addEventListener('DOMContentLoaded', () => {
        loadModule(U.partialIngenieurs, 'menu-ingenieurs');
    });

    /* ═══════════════════════════════════════════════════════════════
    FILTRE + SÉLECTION MULTIPLE MATÉRIEL
    ═══════════════════════════════════════════════════════════════
    Ces fonctions sont exposées globalement car elles sont appelées
    via des attributs HTML inline (oninput, onchange, onclick).
    ═══════════════════════════════════════════════════════════════ */

    /**
     * Filtre les lignes du tableau matériel selon :
     *   - le texte de recherche (désignation)
     *   - le type de matériel sélectionné
     */
    window.filterMaterielTable = function () {
        const search = (document.getElementById('materielSearchInput')?.value || '')
            .toLowerCase().trim();
        const typeId = document.getElementById('materielTypeFilter')?.value || '';
        const rows = document.querySelectorAll('#materielTable tbody tr');
        let visibles = 0;

        rows.forEach(row => {
            const designation = (row.dataset.designation || '').toLowerCase();
            const rowTypeId = String(row.dataset.typeId || '');
            const matchSearch = !search || designation.includes(search);
            const matchType = !typeId || rowTypeId === typeId;
            const visible = matchSearch && matchType;

            row.classList.toggle('hidden', !visible);
            if (visible) visibles++;
        });

        // Message "aucun résultat"
        const noResult = document.getElementById('materielNoResult');
        if (noResult) noResult.classList.toggle('hidden', visibles > 0);

        // Décocher les lignes masquées (évite les faux positifs)
        document.querySelectorAll('#materielTable .materiel-row-checkbox').forEach(cb => {
            const row = cb.closest('tr');
            if (row.classList.contains('hidden')) cb.checked = false;
        });

        // Rafraîchir la barre de sélection
        window.updateMaterielSelectionBar();
    };

    /**
     * Coche / décoche toutes les lignes VISIBLES.
     */
    window.toggleSelectAllMateriel = function (checkbox) {
        const rows = document.querySelectorAll('#materielTable tbody tr:not(.hidden)');
        rows.forEach(row => {
            const cb = row.querySelector('.materiel-row-checkbox');
            if (cb) cb.checked = checkbox.checked;
        });
        window.updateMaterielSelectionBar();
    };

    /**
     * Met à jour la barre d'actions groupées + l'état de la case "Tout sélectionner".
     */
    window.updateMaterielSelectionBar = function () {
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

    /**
     * Décoche toutes les lignes + reset des états.
     */
    window.clearMaterielSelection = function () {
        document.querySelectorAll('#materielTable .materiel-row-checkbox').forEach(cb => {
            cb.checked = false;
        });
        const all = document.getElementById('materielSelectAll');
        if (all) {
            all.checked = false;
            all.indeterminate = false;
        }
        window.updateMaterielSelectionBar();
    };

    /**
     * Supprime en masse les matériels sélectionnés.
     */
    window.supprimerSelectionMateriel = async function () {
        const ids = Array.from(
            document.querySelectorAll('#materielTable .materiel-row-checkbox:checked')
        ).map(cb => cb.value);

        if (ids.length === 0) return;

        const msg = ids.length === 1
            ? 'Supprimer ce matériel ?'
            : `⚠️ Supprimer ${ids.length} matériels ?\n\nCette action est irréversible.`;
        if (!confirm(msg)) return;

        // Double confirmation pour gros volumes
        if (ids.length > 10) {
            if (!confirm(`Confirmer la suppression de ${ids.length} matériels ?`)) return;
        }

        let data;
        try {
            const res = await fetch(U.supprimerMaterielMasse, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ ids: ids }),
            });
            data = await res.json();
        } catch (err) {
            console.error('[supprimerSelectionMateriel]', err);
            return showErrorMessage('Erreur réseau. Vérifiez votre connexion.');
        }

        if (!data.success) {
            return showErrorMessage(data.message || 'Impossible de supprimer la sélection.');
        }

        // Recharger uniquement les accordéons ouverts
        if (typeof rechargerRessourcesOuvertes === 'function') {
            await rechargerRessourcesOuvertes();
        }

        showSuccessMessage(data.message || `${ids.length} matériel(s) supprimé(s).`);
    };

    /* ═══════════════════════════════════════════════════════════════
    IMPORT MATÉRIEL DEPUIS UN TABLEUR
    ═══════════════════════════════════════════════════════════════ */

    /**
     * Ouvre la modal d'import et remet l'état à zéro.
     */
    window.openImportMaterielModal = function () {
        const modal = document.getElementById('importMaterielModal');
        if (!modal) return console.warn('[import] modal introuvable');

        // Reset des champs
        document.getElementById('importMaterielText').value = '';
        document.getElementById('importHasHeader').checked = true;
        document.getElementById('importCreateTypes').checked = false;
        document.getElementById('importUpdateExisting').checked = false;

        // Reset des étapes
        document.getElementById('importMaterielStep1').classList.remove('hidden');
        document.getElementById('importMaterielStep2').classList.add('hidden');
        document.getElementById('importMaterielRapport').innerHTML = '';

        // Bouton de confirmation : état initial
        const confirmBtn = document.getElementById('importMaterielConfirmBtn');
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        }

        modal.style.display = 'block';
        const backdrop = getBackdrop();
        if (backdrop) backdrop.style.display = 'block';
    };

    /**
     * Ferme la modal d'import.
     */
    window.closeImportMaterielModal = function () {
        const modal = document.getElementById('importMaterielModal');
        if (!modal) return;
        modal.style.display = 'none';

        const backdrop = getBackdrop();
        if (backdrop) backdrop.style.display = 'none';
    };

    /**
     * Retour à l'étape 1 (saisie) depuis l'étape 2 (aperçu).
     */
    window.retourImportMateriel = function () {
        document.getElementById('importMaterielStep1').classList.remove('hidden');
        document.getElementById('importMaterielStep2').classList.add('hidden');
    };

    /**
     * Étape 1 → analyse à blanc (dry_run=true).
     */
    window.analyserImportMateriel = function () {
        const texte = document.getElementById('importMaterielText').value;
        if (!texte.trim()) {
            return showWarningMessage('Collez d\'abord des données.');
        }
        envoyerImportMateriel(true);
    };

    /**
     * Étape 2 → import réel (dry_run=false).
     */
    window.confirmerImportMateriel = function () {
        if (!confirm('Confirmer l\'import ? Les données seront enregistrées.')) return;
        envoyerImportMateriel(false);
    };

    /**
     * Envoi réel de la requête d'import.
     * @param {boolean} dryRun - true = analyse seule, false = import réel
     */
    async function envoyerImportMateriel(dryRun) {
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

        const url = `${U.importerMateriels}?dry_run=${dryRun ? '1' : '0'}`;

        // Indicateur visuel
        const rapport = document.getElementById('importMaterielRapport');
        if (rapport) {
            rapport.innerHTML = `<p style="color: var(--text-muted);">Analyse en cours...</p>`;
        }
        document.getElementById('importMaterielStep1').classList.add('hidden');
        document.getElementById('importMaterielStep2').classList.remove('hidden');

        let data;
        try {
            const res = await fetch(url, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken(),
                },
            });
            data = await res.json();
        } catch (err) {
            console.error('[envoyerImportMateriel]', err);
            showErrorMessage('Erreur réseau. Vérifiez votre connexion.');
            // Revenir à l'étape 1
            document.getElementById('importMaterielStep1').classList.remove('hidden');
            document.getElementById('importMaterielStep2').classList.add('hidden');
            return;
        }

        if (data.success === false && data.message) {
            showErrorMessage(data.message);
            document.getElementById('importMaterielStep1').classList.remove('hidden');
            document.getElementById('importMaterielStep2').classList.add('hidden');
            return;
        }

        renderImportMaterielRapport(data, dryRun);

        // Import réel : fermer après 1.5s et recharger
        if (!dryRun) {
            setTimeout(async () => {
                closeImportMaterielModal();
                await rechargerRessourcesOuvertes();
                showSuccessMessage(data.message || 'Import effectué avec succès.');
            }, 1500);
        }
    }

    /**
     * Construit le rapport HTML de l'import.
     */
    function renderImportMaterielRapport(data, dryRun) {
        const container = document.getElementById('importMaterielRapport');
        if (!container) return;

        let html = '';

        // Titre
        const titre = dryRun ? 'Aperçu (rien n\'a été enregistré)' : 'Import effectué';
        html += `<p class="font-semibold mb-3" style="color: var(--accent-info);">${titre}</p>`;

        // Warnings
        if (data.warnings && data.warnings.length) {
            html += `<div class="p-2 rounded text-xs space-y-1" style="background-color: rgba(245, 158, 11, 0.15); border: 1px solid var(--accent-warning); color: var(--accent-warning);">`;
            data.warnings.forEach(w => {
                html += `<div><i class="fas fa-info-circle mr-1"></i>${w}</div>`;
            });
            html += `</div>`;
        }

        // Créés
        if (data.created && data.created.length) {
            html += `<div class="p-3 rounded" style="background-color: rgba(16, 185, 129, 0.1); border: 1px solid var(--accent-success);">`;
            html += `<p class="font-semibold mb-1" style="color: var(--accent-success);">`;
            html += `<i class="fas fa-check-circle mr-1"></i>`;
            html += `${data.created.length} matériel(s) ${dryRun ? 'seront créés' : 'créés'} :`;
            html += `</p>`;
            html += `<ul class="list-disc list-inside text-xs space-y-0.5" style="color: var(--text-primary);">`;
            data.created.forEach(item => {
                html += `<li>${item.designation} <span style="color: var(--text-muted);">(${item.type || '—'})</span></li>`;
            });
            html += `</ul></div>`;
        }

        // Mis à jour
        if (data.updated && data.updated.length) {
            html += `<div class="p-3 rounded mt-2" style="background-color: rgba(59, 130, 246, 0.1); border: 1px solid var(--accent-info);">`;
            html += `<p class="font-semibold mb-1" style="color: var(--accent-info);">`;
            html += `<i class="fas fa-edit mr-1"></i>`;
            html += `${data.updated.length} matériel(s) ${dryRun ? 'seront mis à jour' : 'mis à jour'} :`;
            html += `</p>`;
            html += `<ul class="list-disc list-inside text-xs space-y-0.5" style="color: var(--text-primary);">`;
            data.updated.forEach(item => {
                html += `<li>${item.designation} <span style="color: var(--text-muted);">(${item.type || '—'})</span></li>`;
            });
            html += `</ul></div>`;
        }

        // Ignorés
        if (data.ignored && data.ignored.length) {
            html += `<div class="p-3 rounded mt-2" style="background-color: rgba(245, 158, 11, 0.1); border: 1px solid var(--accent-warning);">`;
            html += `<p class="font-semibold mb-1" style="color: var(--accent-warning);">`;
            html += `<i class="fas fa-exclamation-triangle mr-1"></i>`;
            html += `${data.ignored.length} ligne(s) ignorée(s) :`;
            html += `</p>`;
            html += `<ul class="list-disc list-inside text-xs space-y-0.5" style="color: var(--text-primary);">`;
            data.ignored.forEach(item => {
                html += `<li>Ligne ${item.numero} : ${item.designation} — <em>${item.raison}</em></li>`;
            });
            html += `</ul></div>`;
        }

        // Erreurs
        if (data.errors && data.errors.length) {
            html += `<div class="p-3 rounded mt-2" style="background-color: rgba(239, 68, 68, 0.1); border: 1px solid var(--accent-danger);">`;
            html += `<p class="font-semibold mb-1" style="color: var(--accent-danger);">`;
            html += `<i class="fas fa-times-circle mr-1"></i>`;
            html += `${data.errors.length} ligne(s) en erreur :`;
            html += `</p>`;
            html += `<ul class="list-disc list-inside text-xs space-y-0.5" style="color: var(--text-primary);">`;
            data.errors.forEach(item => {
                html += `<li>Ligne ${item.numero} : ${item.raison}</li>`;
            });
            html += `</ul></div>`;
        }

        // Aucun résultat
        const total = (data.created?.length || 0) + (data.updated?.length || 0)
                    + (data.ignored?.length || 0) + (data.errors?.length || 0);
        if (total === 0) {
            html += `<p style="color: var(--text-muted);">Aucune ligne exploitable.</p>`;
        }

        container.innerHTML = html;

        // Bouton "Confirmer" : désactivé après un import réel
        const confirmBtn = document.getElementById('importMaterielConfirmBtn');
        if (confirmBtn && !dryRun) {
            confirmBtn.disabled = true;
            confirmBtn.classList.add('opacity-50', 'cursor-not-allowed');
        }
    }
})();