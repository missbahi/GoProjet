/* static/projets/js/ateliers-planning.js
 * Repli/dépli des ateliers (persistance localStorage) + aperçu impression.
 * Re-exécutable après chaque swap HTMX.
 */
(function () {
    'use strict';

    if (window.__ateliersPlanningInitialized) return;
    window.__ateliersPlanningInitialized = true;

    const STORAGE_KEY = 'gantt_collapsed_ateliers';
    let contextTarget = null;

    function closeContextMenus() {
        document.querySelectorAll('.context-menu').forEach(menu => { menu.hidden = true; });
        contextTarget = null;
    }

    function showContextMenu(target, menuId, x, y) {
        closeContextMenus();
        const menu = document.getElementById(menuId);
        if (!menu) return;
        contextTarget = target;
        menu.hidden = false;
        menu.style.left = `${Math.max(0, Math.min(x, window.innerWidth - menu.offsetWidth))}px`;
        menu.style.top = `${Math.max(0, Math.min(y, window.innerHeight - menu.offsetHeight))}px`;
        menu.querySelector('[role="menuitem"]')?.focus();
    }

    document.addEventListener('contextmenu', function (e) {
        const affectation = e.target.closest('.gantt-bar-child[data-edit-affectation-button]');
        const atelier = e.target.closest('.gantt-row-parent');
        if (!affectation && !atelier) return;
        e.preventDefault();
        showContextMenu(
            affectation || atelier,
            affectation ? 'gantt-context-menu-affectation' : 'gantt-context-menu-atelier',
            e.clientX, e.clientY,
        );
    });

    function editAffectation(target) {
        const d = target.dataset;
        window.AffectationModal.openEdit(
            d.id, d.materielId, d.materielLabel, d.dateDebut, d.dateFin, d.commentaire,
        );
    }

    function handleContextAction(action, target) {
        const d = target.dataset;
        const atelierAction = action.endsWith('atelier');
        const api = atelierAction ? window.AtelierModal : window.AffectationModal;
        if (!api) {
            console.error('[Gantt] Module modal indisponible', action);
            window.showErrorMessage?.("Le module est en cours de chargement. Veuillez réessayer.");
            return;
        }
        switch (action) {
            case 'add-affectation':
                api.openAddForAtelier(d.atelierId);
                break;
            case 'edit-atelier':
                api.openEdit(d.atelierId, d.atelierCode, d.atelierLibelle, d.atelierDescription, d.atelierActif);
                break;
            case 'delete-atelier':
                api.deleteById(d.atelierId);
                break;
            case 'edit-affectation':
                editAffectation(target);
                break;
            case 'delete-affectation':
                api.deleteById(d.id);
                break;
        }
    }

    function chargerEtat() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return [];
            const parsed = JSON.parse(raw);
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            console.warn('[Gantt] localStorage lecture échouée', e);
            return [];
        }
    }

    function sauverEtat(ids) {
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(ids)); }
        catch (e) { console.warn('[Gantt] localStorage écriture échouée', e); }
    }

    function appliquerEtat(atelierId, collapsed) {
        const toggle = document.querySelector(`[data-toggle-atelier="${atelierId}"]`);
        const children = document.getElementById(`atelier-${atelierId}-children`);
        if (!toggle || !children) return;
        toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        children.hidden = collapsed;
    }

    // Délégation des clics (survit aux swaps)
    document.addEventListener('click', function (e) {
        const contextAction = e.target.closest('[data-context-action]');
        if (contextAction && contextTarget) {
            e.preventDefault();
            const target = contextTarget;
            closeContextMenus();
            handleContextAction(contextAction.dataset.contextAction, target);
            return;
        }
        if (!e.target.closest('.context-menu')) closeContextMenus();
        // Toggle individuel
        const toggle = e.target.closest('[data-toggle-atelier]');
        if (toggle) {
            e.preventDefault();
            const id = toggle.getAttribute('data-toggle-atelier');
            const children = document.getElementById(`atelier-${id}-children`);
            if (!children) return;
            const nowCollapsed = !children.hidden;
            appliquerEtat(id, nowCollapsed);
            const current = chargerEtat();
            const idx = current.indexOf(id);
            if (nowCollapsed) { if (idx === -1) current.push(id); }
            else { if (idx !== -1) current.splice(idx, 1); }
            sauverEtat(current);
            return;
        }

        // Tout replier
        if (e.target.closest('#gantt-collapse-all')) {
            const all = [];
            document.querySelectorAll('[data-toggle-atelier]').forEach(t => {
                const id = t.getAttribute('data-toggle-atelier');
                all.push(id);
                appliquerEtat(id, true);
            });
            sauverEtat(all);
            return;
        }

        // Tout déplier
        if (e.target.closest('#gantt-expand-all')) {
            document.querySelectorAll('[data-toggle-atelier]').forEach(t => {
                appliquerEtat(t.getAttribute('data-toggle-atelier'), false);
            });
            sauverEtat([]);
            return;
        }

    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeContextMenus();
        const target = e.target.closest('.gantt-bar-child[data-edit-affectation-button]');
        if (target && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            handleContextAction('edit-affectation', target);
        }
    });

    // Applique l'état au chargement initial + après swap
    function init() {
        const collapsed = chargerEtat();
        document.querySelectorAll('[data-toggle-atelier]').forEach(t => {
            const id = t.getAttribute('data-toggle-atelier');
            appliquerEtat(id, collapsed.includes(id));
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    document.body.addEventListener('htmx:afterSwap', function (e) {
        if (e.detail.target.id === 'main-content') {
            closeContextMenus();
            init();
        }
    });
    document.body.addEventListener('htmx:historyRestore', function () {
        closeContextMenus();
        init();
    });
})();