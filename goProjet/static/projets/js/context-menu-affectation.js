/**
 * Menu contextuel du Gantt (planning des ateliers).
 *
 * Deux contextes :
 *   - Ligne parente (.gantt-row-parent)  → menu atelier
 *       Actions : add-affectation, edit-atelier
 *   - Barre enfant (.gantt-bar-child)    → menu affectation
 *       Actions : edit-affectation, delete-affectation
 *
 * Dépendances DOM :
 *   - #gantt-context-menu-atelier
 *   - #gantt-context-menu-affectation
 *   - #affectation-config[data-add-template][data-edit-template][data-delete-template]
 *   - window.AffectationModal
 */
(function () {
    'use strict';

    // ============================================================
    // État interne
    // ============================================================
    let menuAtelier = null;
    let menuAffectation = null;
    let config = null;

    let cible = {
        type: null,       // 'atelier' | 'affectation'
        id: null,         // atelier_id ou affectation_id
    };

    // ============================================================
    // Initialisation
    // ============================================================
    function init() {
        menuAtelier = document.getElementById('gantt-context-menu-atelier');
        menuAffectation = document.getElementById('gantt-context-menu-affectation');
        config = document.getElementById('affectation-config');

        if (!menuAtelier || !menuAffectation || !config) {
            console.warn('[ContextMenu] Éléments manquants');
            return;
        }

        attacherHandlers();
    }

    // ============================================================
    // Handlers
    // ============================================================
    function attacherHandlers() {
        // ------------------------------------------------------------
        // Clic droit sur une ligne parente OU une barre enfant
        // ------------------------------------------------------------
        document.addEventListener('contextmenu', function (e) {
            const barre = e.target.closest('.gantt-bar-child');
            const row = e.target.closest('.gantt-row-parent');

            // Priorité à la barre si on est dessus
            if (barre && barre.dataset.id) {
                e.preventDefault();
                cible.type = 'affectation';
                cible.id = barre.dataset.id;
                ouvrirMenu(menuAffectation, e.clientX, e.clientY);
                return;
            }

            if (row && row.dataset.atelierId) {
                e.preventDefault();
                cible.type = 'atelier';
                cible.id = row.dataset.atelierId;
                ouvrirMenu(menuAtelier, e.clientX, e.clientY);
                return;
            }
        });

        // ------------------------------------------------------------
        // Clic sur un item des menus
        // ------------------------------------------------------------
        [menuAtelier, menuAffectation].forEach(menu => {
            menu.addEventListener('click', function (e) {
                const item = e.target.closest('[data-context-action]');
                if (!item) return;
                if (item.disabled || item.hasAttribute('disabled')) return;

                const action = item.getAttribute('data-context-action');
                executerAction(action);      // 1. lit cible
                fermerTousLesMenus();        // 2. ferme + vide cible
            });
        });

        // ------------------------------------------------------------
        // Fermeture : clic ailleurs, Échap, scroll, resize
        // ------------------------------------------------------------
        document.addEventListener('click', function (e) {
            if (!menuAtelier.hidden && !menuAtelier.contains(e.target)) {
                fermerTousLesMenus();
            }
            if (!menuAffectation.hidden && !menuAffectation.contains(e.target)) {
                fermerTousLesMenus();
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') fermerTousLesMenus();
        });

        window.addEventListener('scroll', fermerTousLesMenus, true);
        window.addEventListener('resize', fermerTousLesMenus);
    }

    // ============================================================
    // Ouverture / fermeture
    // ============================================================
    function ouvrirMenu(menu, x, y) {

        menu.hidden = false;

        const rect = menu.getBoundingClientRect();
        const marge = 8;

        let left = x;
        if (left + rect.width + marge > window.innerWidth) {
            left = window.innerWidth - rect.width - marge;
        }

        let top = y;
        if (top + rect.height + marge > window.innerHeight) {
            top = window.innerHeight - rect.height - marge;
        }

        left = Math.max(marge, left);
        top = Math.max(marge, top);

        menu.style.left = `${left}px`;
        menu.style.top = `${top}px`;
    }

    function fermerTousLesMenus() {
        if (menuAtelier) menuAtelier.hidden = true;
        if (menuAffectation) menuAffectation.hidden = true;
        cible.type = null;
        cible.id = null;
    }

    // ============================================================
    // Actions
    // ============================================================
    function executerAction(action) {
        switch (action) {
            case 'add-affectation':
                ajouterAffectation();
                break;
            case 'edit-affectation':
                modifierAffectation();
                break;
            case 'delete-affectation':
                supprimerAffectation();
                break;
            case 'edit-atelier':
                console.warn('[ContextMenu] Action "edit-atelier" non implémentée');
                break;
            default:
                console.warn(`[ContextMenu] Action inconnue : ${action}`);
        }
    }

    // ------------------------------------------------------------
    // Ajouter une affectation (cible = atelier)
    // ------------------------------------------------------------
    function ajouterAffectation() {
        if (cible.type !== 'atelier' || !cible.id) return;

        const template = config.dataset.addTemplate;
        if (!template) {
            console.warn('[ContextMenu] data-add-template manquant');
            return;
        }

        const url = template.replace('/0/', `/${cible.id}/`);

        if (window.AffectationModal && typeof window.AffectationModal.openAddForAtelier === 'function') {
            window.AffectationModal.openAddForAtelier(cible.id, url);
        } else {
            console.warn('[ContextMenu] AffectationModal.openAddForAtelier indisponible');
        }
    }

    // ------------------------------------------------------------
    // Modifier une affectation (cible = barre enfant)
    // ------------------------------------------------------------
    function modifierAffectation() {
        if (cible.type !== 'affectation' || !cible.id) return;

        // Trouver la barre dans le DOM pour lire ses data-*
        const barre = document.querySelector(
            `.gantt-bar-child[data-id="${cible.id}"]`
        );
        if (!barre) {
            console.warn('[ContextMenu] Barre introuvable pour id', cible.id);
            return;
        }

        if (window.AffectationModal && typeof window.AffectationModal.openEdit === 'function') {
            window.AffectationModal.openEdit(
                barre.dataset.id,
                barre.dataset.materielId,
                barre.dataset.materielLabel,
                barre.dataset.dateDebut,
                barre.dataset.dateFin,
                barre.dataset.commentaire
            );
        } else {
            console.warn('[ContextMenu] AffectationModal.openEdit indisponible');
        }
    }

    // ------------------------------------------------------------
    // Supprimer une affectation (cible = barre enfant)
    // ------------------------------------------------------------
    function supprimerAffectation() {
        if (cible.type !== 'affectation' || !cible.id) return;

        if (window.AffectationModal && typeof window.AffectationModal.deleteById === 'function') {
            window.AffectationModal.deleteById(cible.id);
        } else {
            console.warn('[ContextMenu] AffectationModal.deleteById indisponible');
        }
    }

    // ============================================================
    // Point d'entrée
    // ============================================================
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // ============================================================
    // API publique (debug)
    // ============================================================
    window.GanttContextMenu = {
        close: fermerTousLesMenus,
    };
})();