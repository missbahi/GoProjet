/**
 * GoPlan - arbre en memoire, rendu en parcours profondeur et formset Django.
 * Dependances : tree-node.js, gtask-node.js, work-calendar.js.
 */
(function () {
    'use strict';

    if (window.GoPlanTasksInline) {
        window.GoPlanTasksInline.init();
        return;
    }

    const initializedForms = new WeakSet();
    const icons = {
        TACHE: 'fas fa-tasks',
        JALON: 'fas fa-flag',
        GROUPE: 'fas fa-layer-group',
        RECUR: 'fas fa-redo',
    };

    function init() {
        const form = document.getElementById('tachesInlineForm');
        if (!form || initializedForms.has(form)) return;
        const tbody = form.querySelector('#task-tbody');
        const template = document.getElementById('task-empty-template');
        const totalForms = form.querySelector('[name="taches-TOTAL_FORMS"]');
        const errorBox = form.querySelector('[data-task-error]');
        const taskCount = document.getElementById('task-count');
        const rootElement = form.closest('[data-goplan-inline]');
        const linkButton = rootElement.querySelector('#toolbar-links');
        const linkStatus = rootElement.querySelector('[data-link-status]');
        const linkDataElement = rootElement.querySelector('#goplan-inline-link-data');
        let linkData = JSON.parse(linkDataElement.textContent);
        let linkBusy = false;
        const snapshot = () => JSON.stringify(Array.from(form.querySelectorAll('[name]'))
            .filter(el => !el.matches('[data-group-field]') && el.name !== 'csrfmiddlewaretoken')
            .map(el => [el.name, el.type === 'checkbox' ? el.checked : el.value]));
        const buttons = {
            indent: document.getElementById('toolbar-indent'),
            desindent: document.getElementById('toolbar-outdent'),
            moveUp: document.getElementById('toolbar-up'),
            moveDown: document.getElementById('toolbar-down'),
        };
        if (!tbody || !template || !totalForms || !errorBox) {
            console.error('[GoPlan] Formulaire inline incomplet.');
            return;
        }
        initializedForms.add(form);

        const stylesheet = form.dataset.stylesheet;
        if (stylesheet && !Array.from(document.querySelectorAll('link[rel="stylesheet"]'))
            .some(link => link.href === new URL(stylesheet, document.baseURI).href)) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = stylesheet;
            document.head.appendChild(link);
        }

        const root = new TreeNode({ id: '__goplan_root__' });
        const nodes = new Map();
        const rows = new Map();
        let current = null;
        let validTree = true;
        let calendar = null;

        function field(row, name) {
            return row.querySelector(`[name$="-${name}"]`);
        }

        function report(message) {
            errorBox.textContent = message;
            errorBox.hidden = false;
            window.showNotification?.(message, 'warning');
        }

        function clearError() {
            errorBox.textContent = '';
            errorBox.hidden = true;
        }

        try {
            calendar = new window.GoPlanWorkCalendar(JSON.parse(
                form.querySelector('#goplan-work-calendar').textContent
            ));
        } catch (error) {
            console.error('[GoPlan] Calendrier inutilisable.', error);
            report('Calendrier invalide : corrigez sa configuration avant de sauvegarder.');
        }

        function createNode(row) {
            const id = field(row, 'node_key').value;
            if (!id || nodes.has(id)) {
                throw new Error('Identifiant de ligne absent ou dupliqué. Rechargez le planning.');
            }
            const node = new GTaskNode({
                id,
                type_tache: field(row, 'type_tache').value,
            });
            node.expanded = row.dataset.replie !== '1';
            nodes.set(id, node);
            rows.set(id, row);
            return node;
        }

        function updateToolbar() {
            const checks = {
                indent: 'canIndent',
                desindent: 'canDesindent',
                moveUp: 'canMoveUp',
                moveDown: 'canMoveDown',
            };
            Object.entries(buttons).forEach(([action, button]) => {
                if (button) button.disabled = linkBusy || !validTree || !current || !current[checks[action]]();
            });
            linkButton.disabled = linkBusy || !calendar || !validTree || !current
                || !linkData.editable.some(task => task.id === current.id);
        }

        function select(node) {
            current = node;
            rows.forEach((row, id) => {
                const selected = id === current?.id;
                row.classList.toggle('is-current', selected);
                row.setAttribute('aria-selected', String(selected));
            });
            updateToolbar();
        }

        // Folding is a display state saved immediately (saved tasks only); it never dirties the form.
        function persistFold(node) {
            const row = rows.get(node.id);
            row.dataset.replie = node.expanded ? '0' : '1';
            const pk = field(row, 'id')?.value;
            if (!pk || !form.dataset.foldUrl) return;
            const body = new FormData();
            body.append('task', pk);
            body.append('replie', node.expanded ? '0' : '1');
            fetch(form.dataset.foldUrl, {
                method: 'POST', body, credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value,
                    'Accept': 'application/json',
                },
            }).then(response => {
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
            }).catch(error => {
                console.error('[GoPlan] Mémorisation du repli impossible.', error);
                window.showNotification?.("L'état replié n'a pas pu être mémorisé.", 'warning');
            });
        }

        function revealCurrent() {
            for (let parent = current?.parent; parent && parent !== root; parent = parent.parent) {
                if (!parent.expanded) {
                    parent.expanded = true;
                    persistFold(parent);
                }
            }
        }

        function render() {
            updateGroupSchedules();
            revealCurrent();
            let order = 0;
            function visit(node, folded) {
                const row = rows.get(node.id);
                const level = node.level - 1; // La racine technique n'est pas une tache.
                row.classList.toggle('is-folded', folded);
                const foldButton = row.querySelector('[data-fold]');
                if (foldButton) {
                    const label = node.expanded ? 'Masquer les sous-tâches' : 'Afficher les sous-tâches';
                    foldButton.hidden = !node.hasChildren;
                    foldButton.setAttribute('aria-expanded', String(node.expanded));
                    foldButton.setAttribute('aria-label', label);
                    foldButton.title = label;
                    foldButton.querySelector('i').className = node.expanded ? 'fas fa-chevron-down' : 'fas fa-chevron-right';
                }
                field(row, 'parent_key').value = node.parent === root ? '' : node.parent.id;
                field(row, 'ordre').value = order++;
                field(row, 'type_tache').value = node.type_tache;
                const summary = row.querySelector('[data-task-links]');
                const description = window.GoPlanTaskLinks.describe(linkData, node.id);
                summary.textContent = description;
                summary.title = description === '—' ? 'Aucun prédécesseur. Gérer les liaisons.' : description;
                summary.disabled = !linkData.editable.some(task => task.id === node.id);
                syncGroupFields(node, row);
                row.dataset.indent = String(level);
                row.dataset.type = node.type_tache;
                row.querySelector('.goplan-name-cell').style.setProperty('--indent-level', String(level));
                const icon = row.querySelector('.goplan-type-icon');
                if (icon) {
                    icon.dataset.type = node.type_tache;
                    icon.querySelector('i').className = icons[node.type_tache];
                }
                tbody.appendChild(row);
                node.children.forEach(child => visit(child, folded || !node.expanded));
            }
            root.children.forEach(child => visit(child, false));
            if (taskCount) taskCount.textContent = String(order);
            select(current);
        }

        function syncGroupFields(node, row) {
            const locked = node.type_tache === 'GROUPE';
            for (const name of ['type_tache', 'duree', 'date_debut', 'date_fin']) {
                const input = field(row, name);
                input.disabled = locked;
                input.title = locked ? 'Calculé automatiquement depuis les sous-tâches' : '';
                let mirror = row.querySelector(`[data-group-field="${name}"]`);
                if (locked) {
                    if (!mirror) {
                        mirror = document.createElement('input');
                        mirror.type = 'hidden';
                        mirror.name = input.name;
                        mirror.dataset.groupField = name;
                        input.after(mirror);
                    }
                    mirror.value = input.value;
                } else if (mirror) {
                    mirror.remove();
                }
            }
        }

        function updateGroupSchedules() {
            if (!calendar) return;
            nodes.forEach(node => {
                if (node.type_tache === 'GROUPE') return;
                const row = rows.get(node.id);
                node.date_debut = field(row, 'date_debut').value || null;
                node.date_fin = field(row, 'date_fin').value || null;
                node.duree = Number(field(row, 'duree').value);
            });
            root.children.forEach(node => node.recalculateSchedule(calendar));
            nodes.forEach(node => {
                if (node.type_tache !== 'GROUPE') return;
                const row = rows.get(node.id);
                field(row, 'date_debut').value = node.date_debut || '';
                field(row, 'date_fin').value = node.date_fin || '';
                field(row, 'duree').value = node.duree;
                syncGroupFields(node, row);
            });
        }

        try {
            const activeRows = Array.from(tbody.querySelectorAll('tr.task-row'))
                .filter(row => !field(row, 'DELETE')?.checked);
            tbody.querySelectorAll('tr.task-row').forEach(row => {
                row.classList.toggle('hidden', Boolean(field(row, 'DELETE')?.checked));
            });
            activeRows.forEach(createNode);
            // Les champs ordre conservent aussi les deplacements apres un POST invalide.
            activeRows.sort((a, b) => Number(field(a, 'ordre').value) - Number(field(b, 'ordre').value));
            activeRows.forEach(row => {
                const node = nodes.get(field(row, 'node_key').value);
                const parentKey = field(row, 'parent_key').value;
                const parent = parentKey ? nodes.get(parentKey) : root;
                if (!parent || !parent.addChild(node)) {
                    throw new Error('Hiérarchie invalide : parent absent ou cycle détecté.');
                }
            });
            nodes.forEach(node => {
                if (!node.hasChildren && node.type_tache === 'GROUPE') node.type_tache = 'TACHE';
            });
            render();
        } catch (error) {
            validTree = false;
            console.error('[GoPlan] Chargement de la hiérarchie impossible.', error);
            report(error.message);
            updateToolbar();
        }
        if (!form.dataset.savedSnapshot) form.dataset.savedSnapshot = snapshot();
        const links = window.GoPlanTaskLinks(rootElement, {
            getData: () => linkData,
            csrfToken: () => form.querySelector('[name="csrfmiddlewaretoken"]').value,
            setBusy(value) {
                linkBusy = value;
                form.inert = value;
                form.setAttribute('aria-busy', String(value));
                updateToolbar();
            },
            onSaved(result, action) {
                linkData = result;
                linkDataElement.textContent = JSON.stringify(result)
                    .replace(/</g, '\\u003C').replace(/>/g, '\\u003E').replace(/&/g, '\\u0026');
                result.editable.forEach(task => {
                    const row = rows.get(task.id);
                    if (!row) return;
                    Object.entries(task.values).forEach(([name, value]) => {
                        // La couleur appartient au formulaire Gantt, pas aux lignes inline.
                        if (name === 'couleur') return;
                        field(row, name).value = value ?? '';
                    });
                });
                render();
                form.dataset.savedSnapshot = snapshot();
                linkStatus.textContent = action === 'delete'
                    ? 'Liaison supprimée. Dates actualisées.'
                    : 'Liaison enregistrée. Dates et groupes recalculés.';
            },
        });
        linkButton.addEventListener('click', () => {
            if (linkButton.disabled) return;
            if (form.dataset.bound === 'true' || snapshot() !== form.dataset.savedSnapshot) {
                report('Enregistrez les modifications du planning avant de gérer les liaisons.');
                return;
            }
            clearError();
            links.open(current.id);
        });

        Object.entries(buttons).forEach(([action, button]) => {
            button?.addEventListener('click', () => {
                if (!current || !validTree) return;
                clearError();
                try {
                    if (!current[action]()) {
                        report('Ce déplacement est impossible pour la tâche sélectionnée.');
                        return;
                    }
                    render();
                } catch (error) {
                    console.error('[GoPlan] Déplacement impossible.', error);
                    report(error.message);
                }
            });
        });

        function nodeFor(row) {
            return nodes.get(field(row, 'node_key').value);
        }

        tbody.addEventListener('focusin', event => {
            const row = event.target.closest('tr.task-row');
            if (row) select(nodeFor(row));
        });
        tbody.addEventListener('keydown', event => {
            if (!['ArrowUp', 'ArrowDown'].includes(event.key) || event.altKey
                || event.ctrlKey || event.metaKey || event.shiftKey || event.isComposing) return;
            const source = event.target;
            if (!source.matches('input:not([type="hidden"]):not([type="checkbox"]), select, button')) return;
            const row = source.closest('tr.task-row');
            if (!row) return;
            const column = source.closest('td').cellIndex;
            const visible = Array.from(tbody.querySelectorAll('tr.task-row:not(.hidden):not(.is-folded)'));
            event.preventDefault();
            const step = event.key === 'ArrowUp' ? -1 : 1;
            let destination;
            for (let index = visible.indexOf(row) + step; index >= 0 && index < visible.length; index += step) {
                destination = visible[index].cells[column].querySelector(
                    'input:not([type="hidden"]):not([type="checkbox"]):not(:disabled), select:not(:disabled), button:not(:disabled):not([data-fold])'
                );
                if (destination) break;
            }
            if (!destination) return;
            const start = source.selectionStart;
            const end = source.selectionEnd;
            destination.focus({ preventScroll: true });
            if (typeof start === 'number' && typeof end === 'number'
                && typeof destination.selectionStart === 'number') {
                destination.setSelectionRange(start, end);
            }
            destination.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        });
        tbody.addEventListener('click', event => {
            const row = event.target.closest('tr.task-row');
            if (!row || !validTree) return;
            const node = nodeFor(row);
            const foldButton = event.target.closest('[data-fold]');
            if (foldButton) {
                node.expanded = !node.expanded;
                persistFold(node);
                select(node);
                render();
                foldButton.focus({ preventScroll: true });
                return;
            }
            if (event.target.closest('[data-task-links]')) {
                select(node);
                linkButton.click();
                return;
            }
            if (!event.target.closest('.goplan-delete-btn')) {
                select(node);
                return;
            }
            event.preventDefault();
            if (node.hasChildren && !window.confirm(
                'Supprimer cette tâche et toutes ses sous-tâches ?'
            )) return;
            const removed = [node, ...node.descendants];
            const next = node.getNextSibling() || node.getPreviousSibling()
                || (node.parent === root ? null : node.parent);
            node.parent.removeChild(node);
            removed.forEach(item => {
                const deletedRow = rows.get(item.id);
                field(deletedRow, 'DELETE').checked = true;
                deletedRow.classList.add('hidden');
                deletedRow.classList.remove('is-current');
                deletedRow.setAttribute('aria-selected', 'false');
                nodes.delete(item.id);
                rows.delete(item.id);
            });
            current = next;
            clearError();
            render();
        });

        tbody.addEventListener('change', event => {
            const row = event.target.closest('tr.task-row');
            if (!row || !validTree) return;
            if (event.target === field(row, 'type_tache')) {
                const node = nodeFor(row);
                const requested = event.target.value;
                clearError();
                if (node.hasChildren && requested !== 'GROUPE') {
                    report('Une tâche avec des sous-tâches doit rester un groupe.');
                } else if (!node.hasChildren && requested === 'GROUPE') {
                    report('Indentez une sous-tâche pour créer un groupe.');
                } else {
                    node.type_tache = requested;
                }
                render();
                calculate(row, recalcFin);
            }
            if (event.target === field(row, 'date_debut') || event.target === field(row, 'duree')) {
                calculate(row, recalcFin);
            }
            if (event.target === field(row, 'date_fin')) calculate(row, recalcDuree);
        });
        tbody.addEventListener('input', event => {
            const row = event.target.closest('tr.task-row');
            if (!row || !validTree) return;
            if (event.target === field(row, 'duree') || event.target === field(row, 'date_debut')) {
                calculate(row, recalcFin);
            }
            if (event.target === field(row, 'date_fin')) calculate(row, recalcDuree);
        });

        function calculate(row, operation) {
            if (!calendar) return;
            try {
                if (nodeFor(row).type_tache !== 'GROUPE') operation(row);
                updateGroupSchedules();
            } catch (error) {
                console.error('[GoPlan] Calcul de dates impossible.', error);
                report(error.message);
            }
        }

        function recalcFin(row) {
            const start = field(row, 'date_debut');
            const end = field(row, 'date_fin');
            end.setCustomValidity('');
            if (field(row, 'type_tache').value === 'JALON') {
                field(row, 'duree').value = 0;
                end.value = start.value;
                return;
            }
            const duration = Number(field(row, 'duree').value);
            if (!start.value || !Number.isFinite(duration) || duration <= 0) return;
            start.value = calendar.nextWorkingDay(start.value);
            end.value = calendar.endDate(start.value, duration);
        }

        function recalcDuree(row) {
            if (field(row, 'type_tache').value === 'JALON') {
                recalcFin(row);
                return;
            }
            const start = field(row, 'date_debut');
            const end = field(row, 'date_fin');
            end.setCustomValidity('');
            if (!start.value || !end.value) return;
            start.value = calendar.nextWorkingDay(start.value);
            const duration = calendar.workingDaysBetween(start.value, end.value);
            if (duration <= 0) {
                const message = 'La fin doit suivre le début et inclure au moins un jour ouvré.';
                end.setCustomValidity(message);
                report(message);
                return;
            }
            field(row, 'duree').value = duration;
            end.value = calendar.endDate(start.value, duration);
        }

        document.getElementById('task-add-btn')?.addEventListener('click', () => {
            if (!validTree || !calendar) return;
            const index = Number(totalForms.value);
            const wrapper = document.createElement('tbody');
            wrapper.innerHTML = template.innerHTML.replace(/__prefix__/g, String(index));
            const row = wrapper.querySelector('tr.task-row');
            if (!row) {
                report('Le modèle de nouvelle tâche est introuvable.');
                return;
            }
            const node = createNode(row);
            root.addChild(node);
            totalForms.value = index + 1;
            const dates = Array.from(rows.values())
                .filter(item => item !== row)
                .map(item => field(item, 'date_fin').value)
                .filter(Boolean);
            try {
                const start = dates.length ? calendar.nextDate(dates.sort().at(-1)) : form.dataset.planStart;
                field(row, 'date_debut').value = calendar.nextWorkingDay(start);
                recalcFin(row);
            } catch (error) {
                console.error('[GoPlan] Date de nouvelle tâche indisponible.', error);
                report(error.message);
                render();
                return;
            }
            clearError();
            current = node;
            render();
            field(row, 'nom').focus();
        });

        form.addEventListener('invalid', event => {
            const row = event.target.closest?.('tr.task-row.is-folded');
            if (!row) return;
            current = nodeFor(row);
            render();
        }, true);

        form.addEventListener('submit', event => {
            if (!validTree || !calendar) {
                event.preventDefault();
                report('Corrigez la hiérarchie et le calendrier avant de sauvegarder le planning.');
                return;
            }
            render();
        });
    }

    window.GoPlanTasksInline = { init };
    document.addEventListener('DOMContentLoaded', init);
    document.addEventListener('htmx:afterSwap', init);
    document.addEventListener('htmx:historyRestore', init);
    init();
})();
