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
    const escapeHTML = value => String(value).replace(/[&<>"']/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[char]));

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
        
        function computeDirty() {
            return form.dataset.bound === 'true'
                || snapshot() !== form.dataset.savedSnapshot;
        }

        let saveButtonTimer = null;
        function scheduleSaveButtonUpdate() {
            if (saveButtonTimer) clearTimeout(saveButtonTimer);
            saveButtonTimer = setTimeout(updateSaveButton, 200);
        }

        function updateSaveButton() {
            if (!saveButton) return;
            if (saveButtonTimer) {
                clearTimeout(saveButtonTimer);
                saveButtonTimer = null;
            }
            saveButton.disabled = linkBusy || !validTree || !calendar || !computeDirty();
        }
        form.addEventListener('input', scheduleSaveButtonUpdate, { passive: true });
        form.addEventListener('change', scheduleSaveButtonUpdate, { passive: true });
        
        const buttons = {
            indent: document.getElementById('toolbar-indent'),
            desindent: document.getElementById('toolbar-outdent'),
            moveUp: document.getElementById('toolbar-up'),
            moveDown: document.getElementById('toolbar-down'),
        };

        const deleteButton = document.getElementById('inline-delete-task');
        const copyButton = document.getElementById('inline-copy-task');
        const cutButton = document.getElementById('inline-cut-task');
        const pasteButton = document.getElementById('inline-paste-task');
        const saveButton = document.getElementById('inline-save-task');
        const pasteDialog = rootElement.querySelector('#paste-preview-dialog');
        const pasteForm = rootElement.querySelector('#paste-preview-form');
        const pasteSummary = rootElement.querySelector('#paste-preview-summary');
        const pasteTbody = rootElement.querySelector('#paste-preview-tbody');
        const pasteWarnings = rootElement.querySelector('#paste-preview-warnings');
        const pasteConfirm = rootElement.querySelector('#paste-preview-confirm');
        let pendingPaste = null;

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
        let clipboard = null;
        let isSubmitting = false;

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

        // ══════════════════════════════════════════════════════════════
        // COPY / CUT / PASTE
        // ══════════════════════════════════════════════════════════════

        function isAncestorOrSelf(maybeAncestor, node) {
            let cur = node;
            while (cur) {
                if (cur === maybeAncestor) return true;
                cur = cur.parent;
            }
            return false;
        }

        function clearCutVisuals() {
            if (clipboard?.mode === 'cut') {
                const row = rows.get(clipboard.sourceNode.id);
                if (row) row.classList.remove('is-cutting');
            }
        }

        function clearClipboard() {
            clearCutVisuals();
            clipboard = null;
            updateToolbar();
        }

        function copyActive() {
            if (!current || linkBusy || !validTree) return;
            clearError();
            clearCutVisuals();
            // Snapshot DFS (les valeurs sont figées au moment du Copy)
            const entries = [];
            (function walk(node, parentSourceId) {
                const row = rows.get(node.id);
                entries.push({
                    sourceId: node.id,
                    parentSourceId,
                    type_tache: node.type_tache,
                    values: {
                        nom: field(row, 'nom')?.value || '',
                        duree: field(row, 'duree')?.value || '1',
                        couleur: field(row, 'couleur')?.value || '',
                    },
                });
                node.children.forEach(child => walk(child, node.id));
            })(current, null);
            clipboard = { mode: 'copy', entries };
            updateToolbar();
            linkStatus.textContent = `Copié : ${entries.length} tâche(s) (${current.type_tache}).`;
        }

        function cutActive() {
            if (!current || linkBusy || !validTree) return;
            clearError();
            clearCutVisuals();
            clipboard = { mode: 'cut', sourceNode: current };
            const row = rows.get(current.id);
            if (row) row.classList.add('is-cutting');
            updateToolbar();
            linkStatus.textContent = `Coupé : « ${field(row, 'nom')?.value || current.id} ». Collez pour déplacer.`;
        }

        function pasteClipboard() {
            if (!clipboard || linkBusy || !validTree || !calendar) return;
            clearError();

            // Cible : avant la tâche active ; sinon fin de la racine
            const source = clipboard.mode === 'cut' ? clipboard.sourceNode : null;
            let targetParent = current ? (current.parent || root) : root;

            // Refus : cycle (cut uniquement)
            if (source && isAncestorOrSelf(source, targetParent)) {
                report('Impossible de coller ici : la tâche ne peut pas être déplacée sous elle-même.');
                return;
            }

            // Refus : coller une tâche coupée avant elle-même
            if (source && source === current) {
                clearClipboard();
                return;
            }

            if (clipboard.mode === 'cut') {
                // ─── CUT : déplacement en place ───
                if (source.parent) source.parent.removeChild(source);
                let targetIndex;
                if (current && current.parent === targetParent) {
                    targetIndex = current.getIndex();
                } else if (current) {
                    targetParent = current.parent || root;
                    targetIndex = current.getIndex();
                } else {
                    targetIndex = targetParent.children.length;
                }
                targetParent.insertChildAt(source, Math.max(0, targetIndex));
                const row = rows.get(source.id);
                if (row) row.classList.remove('is-cutting');
                clipboard = null;
                current = source;
                render();
                updateSaveButton();
                linkStatus.textContent = 'Tâche déplacée.';
            } else {
                // ─── COPY : clonage récursif ───
                const sourceIdMap = new Map();
                const targetIndex = current ? Math.max(0, current.getIndex()) : root.children.length;

                const start = (() => {
                    // Date de début du parent (ou du projet si root/group sans date)
                    let cur = targetParent;
                    while (cur && cur !== root) {
                        if (cur.date_debut) return cur.date_debut;
                        cur = cur.parent;
                    }
                    return form.dataset.planStart;
                })();

                try {
                    clipboard.entries.forEach((entry, i) => {
                        const index = Number(totalForms.value);
                        const wrapper = document.createElement('tbody');
                        wrapper.innerHTML = template.innerHTML.replace(/__prefix__/g, String(index));
                        const newRow = wrapper.querySelector('tr.task-row');
                        if (!newRow) throw new Error('Template introuvable.');
                        totalForms.value = index + 1;

                        field(newRow, 'nom').value = entry.values.nom;
                        field(newRow, 'duree').value = entry.values.duree;
                        field(newRow, 'type_tache').value = entry.type_tache;
                        field(newRow, 'couleur').value = entry.values.couleur || '';
                        // contrainte / avancement / code : valeurs par défaut du form

                        const clone = createNode(newRow);
                        clone.type_tache = entry.type_tache;

                        // Dates
                        if (entry.type_tache === 'GROUPE') {
                            // Recalculées par updateGroupSchedules au render()
                        } else if (entry.type_tache === 'JALON') {
                            field(newRow, 'duree').value = '0';
                            field(newRow, 'date_debut').value = start;
                            field(newRow, 'date_fin').value = start;
                            field(newRow, 'couleur').value = entry.values.couleur || '';
                        } else {
                            const duration = Number(field(newRow, 'duree').value) || 1;
                            field(newRow, 'date_debut').value = start;
                            const workStart = calendar.nextWorkingDay(start);
                            field(newRow, 'date_fin').value = calendar.endDate(workStart, duration);
                            field(newRow, 'couleur').value = entry.values.couleur || '';
                        }

                        // Insertion
                        if (i === 0) {
                            targetParent.insertChildAt(clone, Math.max(0, targetIndex));
                        } else {
                            const parentClone = sourceIdMap.get(entry.parentSourceId);
                            if (parentClone) parentClone.addChild(clone);
                        }
                        sourceIdMap.set(entry.sourceId, clone);
                    });

                    // Tout déplier pour révéler
                    for (let p = targetParent; p && p !== root; p = p.parent) {
                        p.expanded = true;
                    }

                    current = sourceIdMap.get(clipboard.entries[0].sourceId);
                    render();
                    updateSaveButton();
                    linkStatus.textContent = `${clipboard.entries.length} tâche(s) collée(s).`;
                    // clipboard conservé : paste répétable
                } catch (err) {
                    console.error('[GoPlan] Paste', err);
                    report(err.message);
                    render();
                    updateSaveButton();
                }
            }
        }

        // ESC annule le buffer (hors dialog)
        document.addEventListener('keydown', event => {
            if (event.key !== 'Escape' || !clipboard) return;
            if (document.querySelector('dialog[open]')) return;
            const t = event.target;
            if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT')) return;
            event.preventDefault();
            clearClipboard();
        });

        function updateActiveTaskInfo() {
            const info = rootElement.querySelector('#inline-active-task-info');
            if (!info) return;
            if (!current) {
                info.textContent = '';
                return;
            }
            const row = rows.get(current.id);
            if (!row) {
                info.textContent = '';
                return;
            }
            // WBS : pas un champ éditable → lecture dans linkData (absent pour les lignes non enregistrées)
            const savedTask = linkData.editable.find(t => t.id === current.id);
            const wbs = savedTask?.wbs || '';
            // Code et nom : lecture live dans le formulaire pour suivre les modifications en cours
            const code = field(row, 'code')?.value || '';
            const nom = field(row, 'nom')?.value || '';
            const parts = [];
            if (wbs) {
                parts.push(`<span class="goplan-active-wbs" title="WBS">${escapeHTML(wbs)}</span>`);
            }
            if (code) {
                parts.push(`<span class="goplan-active-code" title="Code">${escapeHTML(code)}</span>`);
            }
            if (nom) {
                parts.push(
                    `<span class="goplan-active-name" title="${escapeHTML(nom)}">${escapeHTML(nom)}</span>`
                );
            }
            info.innerHTML = parts.join(
                '<span class="goplan-active-sep" aria-hidden="true">·</span>'
            );
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
            if (deleteButton) {
                deleteButton.disabled = linkBusy || !validTree || !current;
            }
            if (copyButton) copyButton.disabled = linkBusy || !validTree || !current;
            if (cutButton) cutButton.disabled = linkBusy || !validTree || !current;
            if (pasteButton) {
                pasteButton.disabled = linkBusy || !validTree || !calendar || !clipboard;
                pasteButton.classList.toggle('has-buffer', !!clipboard);
            }
            updateActiveTaskInfo(); 
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

        function findScrollParent(el) {
            let parent = el?.parentElement;
            while (parent) {
                const style = getComputedStyle(parent);
                if (/(auto|scroll)/.test(style.overflowY)) return parent;
                parent = parent.parentElement;
            }
            return document.scrollingElement || document.documentElement;
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
            updateSaveButton();
        } catch (error) {
            validTree = false;
            console.error('[GoPlan] Chargement de la hiérarchie impossible.', error);
            report(error.message);
            updateToolbar();
        }
        
        if (!form.dataset.savedSnapshot) form.dataset.savedSnapshot = snapshot();
        updateSaveButton();
        
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
                updateSaveButton();
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

        // ═══ Paste from clipboard ═══
        form.addEventListener('paste', event => {
            const text = event.clipboardData?.getData('text/plain');
            if (!text || !text.trim()) return;
            if (!text.includes('\t') && text.trim().split(/\r\n|\r|\n/).length < 2) return;

            event.preventDefault();
            if (!validTree || linkBusy || !calendar) {
                report('Collage indisponible : vérifiez le calendrier et la hiérarchie, ou attendez la fin de l’enregistrement.');
                return;
            }
            clearError();

            try {
                const { entries, warnings } = analyzeClipboard(text);
                if (!entries.length) {
                    report('Aucune donnée exploitable dans le presse-papier.');
                    return;
                }
                showPastePreview(entries, warnings);
            } catch (error) {
                console.error('[GoPlan] Lecture du presse-papier impossible.', error);
                report(error.message);
            }
        });

        // Dialog paste
        document.getElementById('paste-preview-close')?.addEventListener('click', () => {
            pendingPaste = null;
            pasteDialog.close();
        });
        document.getElementById('paste-preview-cancel')?.addEventListener('click', () => {
            pendingPaste = null;
            pasteDialog.close();
        });
        pasteForm?.addEventListener('submit', event => {
            event.preventDefault();
            applyPaste();
        });
        pasteDialog?.addEventListener('close', () => { pendingPaste = null; });

        deleteButton?.addEventListener('click', () => {
            if (!current || !validTree || linkBusy) return;
            deleteNode(current);
        });

        copyButton?.addEventListener('click', copyActive);
        cutButton?.addEventListener('click', cutActive);
        pasteButton?.addEventListener('click', pasteClipboard);

        function nodeFor(row) {
            return nodes.get(field(row, 'node_key').value);
        }

        tbody.addEventListener('focusin', event => {
            const row = event.target.closest('tr.task-row');
            if (row) {
                const node = nodeFor(row);
                select(node);
            }
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

        function deleteNode(node) {
            if (!node || !node.parent) return;
            if (node.hasChildren && !window.confirm(
                'Supprimer cette tâche et toutes ses sous-tâches ?'
            )) return;
            const removed = [node, ...node.descendants];
            const next = node.getNextSibling() || node.getPreviousSibling()
                || (node.parent === root ? null : node.parent);
            node.parent.removeChild(node);
            removed.forEach(item => {
                const deletedRow = rows.get(item.id);
                if (!deletedRow) return;
                field(deletedRow, 'DELETE').checked = true;
                deletedRow.classList.add('hidden');
                deletedRow.classList.remove('is-current');
                deletedRow.setAttribute('aria-selected', 'false');
                nodes.delete(item.id);
                rows.delete(item.id);
            });
            current = next;
            clearError();
            if (clipboard?.mode === 'cut') {
                const cutNode = clipboard.sourceNode;
                if (cutNode === node || node.descendants.includes(cutNode)) {
                    clearCutVisuals();
                    clipboard = null;
                }
            }
            render();
            updateSaveButton();
        }

        tbody.addEventListener('click', event => {
            const row = event.target.closest('tr.task-row');
            if (!row || !validTree) return;
            const node = nodeFor(row);
            const foldButton = event.target.closest('[data-fold]');
            if (foldButton) {
                // ─── Ancrage du scroll ───
                const scrollParent = findScrollParent(tbody);
                const anchorTop = row.getBoundingClientRect().top;

                node.expanded = !node.expanded;
                persistFold(node);
                select(node);
                render();
                updateSaveButton();

                // Après reflow, réaligne le scroll pour que la ligne cliquée
                // reste à la même position visuelle dans le viewport.
                if (row.isConnected && scrollParent) {
                    const newTop = row.getBoundingClientRect().top;
                    if (newTop !== anchorTop) {
                        scrollParent.scrollTop += (newTop - anchorTop);
                    }
                }

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
            deleteNode(node);
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
                updateSaveButton();
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
            if (event.target === field(row, 'code') || event.target === field(row, 'nom')) {
                if (current && current.id === field(row, 'node_key').value) {
                    updateActiveTaskInfo();
                }
            }
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

        // ══════════════════════════════════════════════════════════════
        // PASTE FROM EXCEL
        // ══════════════════════════════════════════════════════════════

        const TYPE_ALIASES = {
            'tache': 'TACHE', 'tâche': 'TACHE', 'task': 'TACHE',
            'jalon': 'JALON', 'milestone': 'JALON',
            'groupe': 'GROUPE', 'group': 'GROUPE',
            'recur': 'RECUR', 'récurrente': 'RECUR', 'recurrente': 'RECUR', 'recurring': 'RECUR',
        };

        function parseDate(value) {
            if (!value) return null;
            const v = String(value).trim();
            let iso = /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : null;
            const m = v.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{4})$/);
            if (m) {
                const [, d, mo, y] = m;
                iso = `${y}-${mo.padStart(2, '0')}-${d.padStart(2, '0')}`;
            }
            if (!iso) return null;
            const date = new Date(`${iso}T00:00:00Z`);
            return !Number.isNaN(date.getTime()) && date.getUTCFullYear() >= 1
                && date.toISOString().slice(0, 10) === iso ? iso : null;
        }

        function parseClipboardRows(text) {
            const result = [];
            let cells = [];
            let cell = '';
            let quoted = false;
            let closedQuote = false;
            const pushCell = () => {
                cells.push(cell);
                cell = '';
                closedQuote = false;
            };
            for (let i = 0; i < text.length; i++) {
                const char = text[i];
                if (quoted) {
                    if (char === '"') {
                        if (text[i + 1] === '"') { cell += '"'; i++; }
                        else { quoted = false; closedQuote = true; }
                    } else {
                        cell += char;
                    }
                } else if (char === '\t') {
                    pushCell();
                } else if (char === '\r' || char === '\n') {
                    pushCell();
                    result.push(cells);
                    cells = [];
                    if (char === '\r' && text[i + 1] === '\n') i++;
                } else if (char === '"' && cell === '' && !closedQuote) {
                    quoted = true;
                } else {
                    if (closedQuote) throw new Error('Cellule mal délimitée après un guillemet fermant.');
                    cell += char;
                }
            }
            if (quoted) throw new Error('Cellule entre guillemets non terminée dans le presse-papier.');
            pushCell();
            result.push(cells);
            return result;
        }

        function analyzeClipboard(text) {
            const lines = parseClipboardRows(text);
            const entries = [];
            const warnings = [];

            lines.forEach((cells, i) => {
                if (cells.every(cell => !cell.trim())) return;
                const [code = '', nom = '', typeRaw = '', dureeRaw = '', debutRaw = ''] =
                    cells.slice(0, 5).map(c => String(c).trim());
                if (cells.length > 5) warnings.push(`Ligne ${i + 1} : colonnes après Début ignorées.`);
                const typeKey = typeRaw.toLowerCase();
                const knownType = Object.prototype.hasOwnProperty.call(TYPE_ALIASES, typeKey);
                const type = knownType ? TYPE_ALIASES[typeKey] : 'TACHE';
                if (typeRaw && !knownType) {
                    warnings.push(`Ligne ${i + 1} : Type « ${typeRaw} » inconnu → TACHE.`);
                }
                if (type === 'GROUPE') {
                    warnings.push(`Ligne ${i + 1} : un groupe sans sous-tâches est converti en TACHE.`);
                }

                const entry = {
                    rowNumber: i + 1,
                    code,
                    nom,
                    type: type === 'GROUPE' ? 'TACHE' : type,
                    duree: 1,
                    debut: null,
                    valid: true,
                    reason: '',
                };

                if (!nom) {
                    entry.valid = false;
                    entry.reason = 'Nom manquant';
                    warnings.push(`Ligne ${i + 1} : Nom manquant — ignorée`);
                    entries.push(entry);
                    return;
                }

                if (entry.type === 'JALON') {
                    entry.duree = 0;
                } else if (dureeRaw !== '') {
                    const numeric = dureeRaw.replace(',', '.');
                    const duration = Number(numeric);
                    if (/^\d+(?:\.\d+)?$/.test(numeric) && Number.isFinite(duration)
                        && duration > 0 && Number.isInteger(duration * 2)) {
                        entry.duree = duration;
                    } else {
                        entry.valid = false;
                        entry.reason = 'Durée positive requise, par pas de 0,5 jour';
                        warnings.push(`Ligne ${i + 1} : Durée « ${dureeRaw} » invalide — ignorée`);
                    }
                }

                if (debutRaw) {
                    const parsed = parseDate(debutRaw);
                    if (parsed) {
                        entry.debut = parsed;
                    } else {
                        entry.valid = false;
                        entry.reason = `Date « ${debutRaw} » invalide`;
                        warnings.push(`Ligne ${i + 1} : Date « ${debutRaw} » invalide — ignorée`);
                    }
                }

                entries.push(entry);
            });

            return { entries, warnings };
        }

        function planPaste(entries) {
            // Combien de tâches existantes seront remplacées ?
            // - Si current existe : on remplace current puis les suivantes dans l'ordre visuel
            // - Sinon : 0 remplacement, tout en création

            const visibleRows = Array.from(tbody.querySelectorAll('tr.task-row:not(.hidden):not(.is-folded)'));
            const startRowIndex = current
                ? visibleRows.findIndex(r => field(r, 'node_key').value === current.id)
                : -1;

            const replaceTargets = [];
            let replaceCount = 0;

            if (startRowIndex >= 0) {
                const available = visibleRows.length - startRowIndex;
                replaceCount = Math.min(entries.length, available);
                for (let i = 0; i < replaceCount; i++) {
                    const row = visibleRows[startRowIndex + i];
                    replaceTargets.push({
                        nodeKey: field(row, 'node_key').value,
                        row,
                    });
                }
            }

            return { replaceTargets, replaceCount };
        }

        function showPastePreview(entries, warnings) {
            const { replaceTargets, replaceCount } = planPaste(entries);
            entries.forEach((entry, i) => {
                if (!entry.valid) return;
                const target = replaceTargets[i];
                const node = target ? nodeFor(target.row) : null;
                if (node?.hasChildren) {
                    entry.type = 'GROUPE';
                    entry.duree = Number(field(target.row, 'duree').value);
                    entry.debut = field(target.row, 'date_debut').value || null;
                    warnings.push(`Ligne ${entry.rowNumber} : groupe conservé ; seuls Code et Nom seront remplacés.`);
                    return;
                }
                try {
                    const start = entry.debut || (target && field(target.row, 'date_debut').value)
                        || form.dataset.planStart;
                    entry.debut = entry.type === 'JALON' ? start : calendar.nextWorkingDay(start);
                    entry.fin = calendar.endDate(entry.debut, entry.duree);
                } catch (error) {
                    entry.valid = false;
                    entry.reason = error.message;
                    warnings.push(`Ligne ${entry.rowNumber} : ${error.message} — ignorée`);
                }
            });
            const replaced = entries.slice(0, replaceCount).filter(entry => entry.valid).length;
            const createCount = entries.slice(replaceCount).filter(entry => entry.valid).length;

            // Résumé
            const parts = [];
            if (replaced > 0) parts.push(`${replaced} remplacée(s)`);
            if (createCount > 0) parts.push(`${createCount} créée(s)`);
            const skipped = entries.filter(e => !e.valid).length;
            if (skipped > 0) parts.push(`${skipped} ignorée(s)`);
            pasteSummary.textContent = `${entries.length} ligne(s) analysée(s) — ${parts.join(' · ')}`;

            // Tableau
            pasteTbody.replaceChildren();
            entries.forEach((entry, i) => {
                const tr = document.createElement('tr');
                if (!entry.valid) tr.classList.add('is-invalid');
                else if (i < replaceCount) tr.classList.add('is-replace');
                else tr.classList.add('is-create');

                tr.innerHTML = `
                    <td class="icon-cell">${entry.rowNumber}</td>
                    <td>${escapeHTML(entry.code || '—')}</td>
                    <td>${escapeHTML(entry.nom)}</td>
                    <td>${escapeHTML(entry.type)}</td>
                    <td class="amount">${entry.duree}</td>
                    <td>${entry.debut ? escapeHTML(entry.debut.split('-').reverse().join('/')) : '—'}</td>
                    <td>${escapeHTML(entry.reason)}</td>
                `;
                pasteTbody.appendChild(tr);
            });

            // Avertissements
            pasteWarnings.textContent = warnings.join(' · ');

            // Bouton désactivé si aucune ligne valide
            const validCount = entries.filter(e => e.valid).length;
            pasteConfirm.disabled = validCount === 0;

            // Stocker pour la confirmation
            pendingPaste = { entries, replaceTargets, replaceCount };

            pasteDialog.showModal();
        }

        function applyPaste() {
            if (!pendingPaste) return;
            if (linkBusy || !validTree || !calendar) {
                report('Collage indisponible : vérifiez le calendrier et la hiérarchie, ou attendez la fin de l’enregistrement.');
                return;
            }
            const { entries, replaceTargets } = pendingPaste;
            const operations = [];
            let nextIndex = Number(totalForms.value);
            const keys = new Set(nodes.keys());
            try {
                // Préparer les nouvelles lignes avant de modifier les tâches existantes.
                entries.forEach((entry, i) => {
                    if (!entry.valid) return;
                    let row = replaceTargets[i]?.row;
                    const created = !row;
                    if (created) {
                        const wrapper = document.createElement('tbody');
                        wrapper.innerHTML = template.innerHTML.replace(/__prefix__/g, String(nextIndex));
                        row = wrapper.querySelector('tr.task-row');
                        if (!row) throw new Error('Le modèle de nouvelle tâche est introuvable.');
                        const key = field(row, 'node_key').value;
                        if (!key || keys.has(key)) throw new Error('Identifiant de nouvelle ligne absent ou dupliqué.');
                        keys.add(key);
                        nextIndex++;
                    }
                    const values = { code: entry.code, nom: entry.nom };
                    if (entry.type !== 'GROUPE') {
                        Object.assign(values, {
                            type_tache: entry.type, duree: String(entry.duree),
                            date_debut: entry.debut, date_fin: entry.fin,
                        });
                    }
                    Object.keys(values).forEach(name => {
                        if (!field(row, name)) throw new Error(`Champ de tâche absent : ${name}.`);
                    });
                    operations.push({ row, entry, values, created });
                });
            } catch (error) {
                console.error('[GoPlan] Préparation du collage impossible.', error);
                pasteWarnings.textContent = error.message;
                report(error.message);
                return;
            }
            if (!operations.length) {
                report('Aucune ligne valide à coller.');
                return;
            }
            clearError();
            operations.forEach(({ row, entry, values, created }) => {
                Object.entries(values).forEach(([name, value]) => { field(row, name).value = value; });
                if (entry.type !== 'GROUPE') field(row, 'date_fin').setCustomValidity('');
                if (created) root.addChild(createNode(row));
                else nodeFor(row).type_tache = entry.type;
            });
            totalForms.value = String(nextIndex);
            render();
            updateSaveButton();
            const createdCount = operations.filter(operation => operation.created).length;
            const replacedCount = operations.length - createdCount;
            linkStatus.textContent = `Collé : ${replacedCount} remplacée(s) · ${createdCount} créée(s). Enregistrez pour persister.`;
            pendingPaste = null;
            pasteDialog.close();
        }
        // Fin Coller depuis Excel


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
                updateSaveButton();
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
            updateSaveButton();
        }, true);

        form.addEventListener('submit', event => {
            if (isSubmitting) {
                event.preventDefault();
                return;
            }
            if (!validTree || !calendar) {
                event.preventDefault();
                report('Corrigez la hiérarchie et le calendrier avant de sauvegarder le planning.');
                return;
            }
            render();
            updateSaveButton();
            isSubmitting = true;
        });

        form.addEventListener('keydown', event => {
            if (event.key !== 'Enter') return;
            const target = event.target;
            // Exceptions : zones multi-lignes et boutons explicites
            if (target.tagName === 'TEXTAREA') return;
            if (target.tagName === 'BUTTON') return;
            if (target.tagName === 'A') return;
            if (target.tagName === 'INPUT' && ['submit', 'button', 'reset'].includes(target.type)) return;
            // Tout le reste : bloqué (text, number, date, select…)
            event.preventDefault();
        }, true);

        document.addEventListener('goplan:before-import', event => {
            if (!form.isConnected) return;
            if (linkBusy || isSubmitting || computeDirty()) {
                event.preventDefault();
                report('Enregistrez les modifications du planning et attendez la fin de l’enregistrement avant d’importer un XML.');
            }
        });

        document.addEventListener('goplan:before-export', event => {
            if (!form.isConnected) return;
            if (linkBusy || isSubmitting || computeDirty()) {
                event.preventDefault();
                report('Enregistrez les modifications du planning et attendez la fin de l’enregistrement avant d’exporter un XML.');
            }
        });

        window.addEventListener('beforeunload', event => {
            if (!form.isConnected || isSubmitting || !computeDirty()) return;
            event.preventDefault();
            event.returnValue = '';
        });
    }

    window.GoPlanTasksInline = { init };
    document.addEventListener('DOMContentLoaded', init);
    document.addEventListener('htmx:afterSwap', init);
    document.addEventListener('htmx:historyRestore', init);
    init();
})();
