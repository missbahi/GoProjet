(function () {
    'use strict';

    if (window.GoPlanGantt) {
        window.GoPlanGantt.init();
        return;
    }
    const initialized = new WeakSet();

    // ══════════════════════════════════════════════════════════════
    // SCROLL RESTORATION — HTMX, reload, tab close
    // ══════════════════════════════════════════════════════════════
    const scrollKey = () => 'goplan:scroll:' + window.location.pathname;

    function saveGanttScroll() {
        const scroller = document.querySelector('.goplan-gantt-split');
        if (!scroller) return;
        if (!scroller.scrollLeft && !scroller.scrollTop) return;
        try {
            sessionStorage.setItem(scrollKey(), JSON.stringify({
                left: Math.round(scroller.scrollLeft),
                top: Math.round(scroller.scrollTop),
            }));
        } catch (_) { /* mode privé */ }
    }

    function loadGanttScroll() {
        try {
            const raw = sessionStorage.getItem(scrollKey());
            return raw ? JSON.parse(raw) : null;
        } catch (_) { return null; }
    }
    // ══════════════════════════════════════════════════════════════

    document.addEventListener('htmx:beforeSwap', saveGanttScroll);
    window.addEventListener('pagehide', saveGanttScroll);
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') saveGanttScroll();
    });

    const escapeHTML = value => value.replace(/[&<>"']/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[char]));
    const formatDate = value => value.split('-').reverse().join('/');
    const dayNumber = date => Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86400000;
    const zoomLevels = [0.75, 1, 1.25, 1.5, 2];
    const columnWidths = { Day: 38, Week: 140, Month: 120 };

    function barGeometry(appearance) {
        const height = { fine: 14, normale: 22, epaisse: 28 }[appearance.gantt_epaisseur];
        const radius = { rectangle: 0, arrondi: 7, capsule: height / 2 }[appearance.gantt_arrondi];
        return { height, radius };
    }

    function connectorPath(points, rounded) {
        let path = `M ${points[0][0]} ${points[0][1]}`;
        for (let i = 1; i < points.length - 1; i++) {
            const previous = points[i - 1];
            const current = points[i];
            const next = points[i + 1];
            const before = Math.hypot(current[0] - previous[0], current[1] - previous[1]);
            const after = Math.hypot(next[0] - current[0], next[1] - current[1]);
            const radius = rounded ? Math.min(5, before / 2, after / 2) : 0;
            if (!radius) {
                path += ` L ${current[0]} ${current[1]}`;
                continue;
            }
            const entry = current.map((value, axis) => value + (previous[axis] - value) * radius / before);
            const exit = current.map((value, axis) => value + (next[axis] - value) * radius / after);
            path += ` L ${entry[0]} ${entry[1]} Q ${current[0]} ${current[1]} ${exit[0]} ${exit[1]}`;
        }
        return `${path} L ${points.at(-1)[0]} ${points.at(-1)[1]}`;
    }

    function timelineDays(start, width, dayWidth, calendar) {
        const days = [];
        for (let offset = 0; offset * dayWidth < width; offset++) {
            const date = new Date((dayNumber(start) + offset) * 86400000);
            const iso = date.toISOString().slice(0, 10);
            days.push({
                date: iso, x: offset * dayWidth,
                width: Math.min(dayWidth, width - offset * dayWidth),
                nonWorking: calendar ? !calendar.isWorkingDay(iso) : false,
                boundary: date.getUTCMonth() === 0 && date.getUTCDate() === 1 ? 'year'
                    : date.getUTCDate() === 1 ? 'month'
                        : date.getUTCDay() === 1 ? 'week' : '',
            });
        }
        return days;
    }

    function visibleTasks(data, collapsed) {
        const parents = new Map(data.editable.map(task => [task.id, task.parent_id]));
        return data.tasks.filter(task => {
            const visited = new Set([task.id]);
            let parent = parents.get(task.id);
            while (parent && !visited.has(parent)) {
                if (collapsed.has(parent)) return false;
                visited.add(parent);
                parent = parents.get(parent);
            }
            return true;
        });
    }

    function initialize(root) {
        if (initialized.has(root)) return;
        initialized.add(root);
        const svg = root.querySelector('#gantt-svg');
        const restoredContainer = svg.closest('.gantt-container');
        if (restoredContainer) restoredContainer.replaceWith(svg);
        svg.replaceChildren();
        svg.removeAttribute('width');
        svg.removeAttribute('height');
        const error = root.querySelector('#gantt-error');
        const buttons = root.querySelectorAll('.gantt-view-btn');
        const today = root.querySelector('#gantt-today-btn');
        const zoomIn = root.querySelector('#gantt-zoom-in');
        const zoomOut = root.querySelector('#gantt-zoom-out');
        const zoomLabel = root.querySelector('#gantt-zoom-level');
        const status = root.querySelector('#gantt-status');
        const form = root.querySelector('#gantt-task-form');
        const fieldset = form.querySelector('fieldset');
        const fields = [...form.querySelectorAll('[name]')].filter(el => el.name !== 'csrfmiddlewaretoken');
        const field = name => form.elements.namedItem(name);
        const colorPicker = root.querySelector('#gantt-task-color');
        const resetColor = root.querySelector('#gantt-reset-color');
        const colorSwatches = root.querySelectorAll('[data-task-color]');
        const colorPanel = root.querySelector('#gantt-color-panel');
        const colorPreview = root.querySelector('#gantt-color-preview');
        const saveColorBtn = root.querySelector('#gantt-save-color');
        const splitRoot     = root.querySelector('.goplan-gantt-split');
        const openColorBtn = root.querySelector('#gantt-open-color');
        const paintBtn = root.querySelector('#gantt-paint-mode');
        const select = root.querySelector('#gantt-task-select');
        const newButton = root.querySelector('#gantt-new-task');
        const deleteButton = root.querySelector('#gantt-delete-task');
        const position = root.querySelector('#gantt-position');
        const dialog = root.querySelector('#gantt-unsaved-dialog');
        const context = root.querySelector('#gantt-editor-context');
        const groupDurationInfo = root.querySelector('#gantt-group-duration-info');
        const submit = root.querySelector('#gantt-save-task');
        const linkButton = root.querySelector('#gantt-link-task');
        const editorToggle = root.querySelector('#gantt-toggle-editor');
        const leftPanel  = root.querySelector('#gantt-left-panel');
        const leftBody   = root.querySelector('#gantt-left-body');
        const leftHeader = root.querySelector('#gantt-left-header');
        const scroller = root.querySelector('.goplan-gantt-split');
        const timeline = svg.closest('.goplan-gantt-container');
        timeline.querySelectorAll('.gantt-fixed-calendar').forEach(el => el.remove());
        const fixedCalendar = document.createElement('div');
        fixedCalendar.className = 'gantt-fixed-calendar';
        fixedCalendar.setAttribute('aria-hidden', 'true');
        timeline.prepend(fixedCalendar);
        const appearanceScript = root.querySelector('#goplan-gantt-appearance');
        let savedAppearance = JSON.parse(appearanceScript.textContent);
        let appearance = { ...savedAppearance.values };
        const appearanceDialog = root.querySelector('#gantt-appearance-dialog');
        const appearanceForm = root.querySelector('#gantt-appearance-form');
        const appearanceFields = [...appearanceForm.querySelectorAll('select, input[type="color"]')];
        const appearanceErrors = root.querySelector('#gantt-appearance-errors');
        const appearanceCancel = root.querySelector('#gantt-appearance-cancel');
        let savingAppearance = false;
        let data = JSON.parse(root.querySelector('#goplan-gantt-data').textContent);
        const collapsed = new Set(root.dataset.collapsedGroups
            ? JSON.parse(root.dataset.collapsedGroups) : (data.collapsed || []));
        let editable = new Map();
        let byId = new Map();
        let gantt = null;
        let calendar = null;
        let activeId = '';
        let editId = '';
        let baseline = '';
        let busy = false;
        let currentView = 'Week';
        let initialColor = '';
        let paintMode = false;
        let paintColor = '';
        let paintRestoreEditor = true;
        let zoomIndex = 1;
        const snapshot = () => JSON.stringify(fields.map(el => el.value));
        const dirty = () => snapshot() !== baseline;
        const markDirty = () => { form.dataset.dirty = String(dirty()); };

        function previewAppearance() {
            appearance = Object.fromEntries(appearanceFields.map(input => [input.name, input.value]));
            const left = scroller.scrollLeft;
            const top = scroller.scrollTop;
            root.style.setProperty('--goplan-link-color', appearance.gantt_couleur_liaison);
            if (gantt && data.tasks.length) applyZoom();
            scroller.scrollLeft = left;
            scroller.scrollTop = top;
        }

        function fillAppearance(values) {
            appearanceFields.forEach(input => { input.value = values[input.name]; });
            previewAppearance();
        }

        function cancelAppearance() {
            if (savingAppearance) return;
            fillAppearance(savedAppearance.values);
            appearanceDialog.close();
        }

        root.querySelector('#gantt-open-appearance').addEventListener('click', () => {
            if (colorPanel.matches(':popover-open')) colorPanel.hidePopover();
            appearanceErrors.textContent = '';
            fillAppearance(savedAppearance.values);
            appearanceDialog.showModal();
        });

        appearanceFields.forEach(input => input.addEventListener('input', previewAppearance));

        root.querySelector('#gantt-appearance-defaults').addEventListener('click', () => {
            fillAppearance(savedAppearance.defaults);
        });

        appearanceCancel.addEventListener('click', cancelAppearance);

        appearanceDialog.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                event.preventDefault();
                event.stopPropagation();
                cancelAppearance();
            }
        });

        appearanceDialog.addEventListener('cancel', event => {
            event.preventDefault();
            cancelAppearance();
        });

        appearanceForm.addEventListener('submit', async event => {
            event.preventDefault();
            if (savingAppearance || !appearanceForm.reportValidity()) return;
            appearanceErrors.textContent = '';
            const payload = new FormData(appearanceForm);
            payload.set('revision', savedAppearance.revision);
            savingAppearance = true;
            appearanceForm.setAttribute('aria-busy', 'true');
            appearanceForm.querySelector('fieldset').disabled = true;
            appearanceForm.querySelector('[type="submit"]').disabled = true;
            appearanceCancel.disabled = true;
            try {
                const response = await fetch(appearanceForm.action, {
                    method: 'POST', body: payload,
                    headers: {
                        'X-CSRFToken': appearanceForm.elements.namedItem('csrfmiddlewaretoken').value,
                        'Accept': 'application/json',
                    },
                });
                if (response.redirected) throw new Error("Session expirée. Reconnectez-vous avant d'appliquer l'apparence.");
                if (!response.headers.get('content-type')?.includes('application/json')) {
                    throw new Error(`Enregistrement de l'apparence refusé (HTTP ${response.status}).`);
                }
                const result = await response.json();
                if (!response.ok) {
                    appearanceErrors.textContent = Object.values(result.errors || {}).flat().join(' ')
                        || `Enregistrement refusé (HTTP ${response.status}).`;
                    return;
                }
                savedAppearance = result;
                appearanceScript.textContent = JSON.stringify(result);
                fillAppearance(result.values);
                appearanceDialog.close();
                status.textContent = 'Apparence du planning enregistrée.';
            } catch (err) {
                console.error('[GoPlan/Gantt] Apparence', err);
                appearanceErrors.textContent = err.message;
            } finally {
                savingAppearance = false;
                appearanceForm.setAttribute('aria-busy', 'false');
                appearanceForm.querySelector('fieldset').disabled = false;
                appearanceForm.querySelector('[type="submit"]').disabled = false;
                appearanceCancel.disabled = false;
            }
        });

        colorPanel.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                event.preventDefault();
                event.stopPropagation();
                colorPanel.hidePopover();
                root.querySelector('#gantt-open-color').focus();
            }
        });

        colorPanel.addEventListener('beforetoggle', event => {
            if (event.newState === 'open') {
                initialColor = (field('couleur').value || '').toLowerCase();
                syncColorSaveButton();
            }
        });

        saveColorBtn?.addEventListener('click', async () => {
            if (saveColorBtn.disabled) return;
            const ok = await saveTask();
            if (!ok) return;
            if (colorPanel.matches(':popover-open')) colorPanel.hidePopover();
            openColorBtn.focus();
        });

        paintBtn?.addEventListener('click', () => {
            if (paintMode) {
                exitPaintMode();
            } else {
                enterPaintMode();
            }
        });

        document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && paintMode) {
                event.preventDefault();
                exitPaintMode();
            }
        });

        function syncColorPicker() {
            const custom = /^#[0-9a-f]{6}$/i.test(field('couleur').value);
            colorPicker.value = custom ? field('couleur').value : '#7baec1';
            colorPicker.title = custom ? 'Couleur personnalisée' : 'Couleur automatique selon le type de tâche';
            colorPreview.style.backgroundColor = colorPicker.value;
            colorPreview.title = colorPicker.title;
            resetColor.disabled = !field('couleur').value;
            colorSwatches.forEach(button => button.setAttribute(
                'aria-pressed', String(button.dataset.taskColor === field('couleur').value.toLowerCase()),
            ));
            syncColorSaveButton();
        }

        function syncColorSaveButton() {
            if (!saveColorBtn) return;
            const current = (field('couleur').value || '').toLowerCase();
            saveColorBtn.disabled = busy || fieldset.disabled || current === initialColor;
        }

        function syncPaintButton() {
            if (!paintBtn) return;
            paintBtn.disabled = busy || !editId || fieldset.disabled;
        }

        function enterPaintMode() {
            if (paintMode || !editId) return;
            const color = (field('couleur').value || '').toLowerCase();
            paintColor = color;
            paintMode = true;
            paintBtn.setAttribute('aria-pressed', 'true');
            splitRoot?.classList.add('is-painting');

            // Verrouille tous les contrôles sauf le brush
            root.querySelectorAll(
                '.goplan-toolbar-btn, .goplan-toolbar a, #gantt-task-select, .gantt-view-btn, ' +
                '#gantt-task-form input, #gantt-task-form select, #gantt-task-form textarea, ' +
                '#gantt-task-form button'
            ).forEach(el => {
                if (el === paintBtn) return;
                el.dataset.paintWasDisabled = el.disabled ? '1' : '0';
                el.disabled = true;
                if (el.tagName === 'A') el.classList.add('is-disabled');
            });

            const label = color ? color : 'automatique';
            status.textContent = `Mode reproduction — couleur ${label}. Cliquez sur les tâches. Échap ou re-clic sur le pinceau pour terminer.`;
            paintRestoreEditor = !form.hidden;
            setEditorVisible(false);
        }

        function exitPaintMode() {
            if (!paintMode) return;
            paintMode = false;
            paintColor = '';
            paintBtn.setAttribute('aria-pressed', 'false');
            splitRoot?.classList.remove('is-painting');
            root.querySelectorAll('[data-paint-was-disabled]').forEach(el => {
                el.disabled = el.dataset.paintWasDisabled === '1';
                el.classList.remove('is-disabled');
                delete el.dataset.paintWasDisabled;
            });
            status.textContent = '';
            syncPaintButton();
            if (paintRestoreEditor) setEditorVisible(paintRestoreEditor);
        }

        async function applyPaintToTask(taskId) {
            if (busy || !paintMode) return;
            const task = byId.get(taskId);
            if (!task) return;
            if ((task.color || '').toLowerCase() === paintColor) return;

            const payload = new FormData();
            payload.set('task_id', taskId);
            payload.set('color', paintColor);
            payload.set('revision', data.revision);
            setBusy(true);
            try {
                const response = await fetch(root.dataset.colorUrl, {
                    method: 'POST', body: payload,
                    headers: {
                        'X-CSRFToken': field('csrfmiddlewaretoken').value,
                        'Accept': 'application/json',
                    },
                });
                if (response.redirected) throw new Error('Session expirée.');
                const result = await response.json();
                if (!response.ok) {
                    const flat = result.errors ? Object.values(result.errors).flat().join(' ') : '';
                    throw new Error(flat || `HTTP ${response.status}`);
                }
                updateData(result);
                render();
                const wrapper = svg.querySelector(`.bar-wrapper[data-id="${CSS.escape(taskId)}"]`);
                wrapper?.classList.add('is-paint-flash');
                setTimeout(() => wrapper?.classList.remove('is-paint-flash'), 400);
                status.textContent = `Couleur appliquée à « ${task.name} ».`;
            } catch (err) {
                console.error('[GoPlan/Gantt] Application couleur', err);
                status.textContent = `Échec : ${err.message}`;
            } finally {
                setBusy(false);
                // setBusy(false) a réactivé tous les contrôles ; on remet le verrou paint
                if (paintMode) {
                    root.querySelectorAll(
                        '.goplan-toolbar-btn, .goplan-toolbar a, #gantt-task-select, .gantt-view-btn, ' +
                        '#gantt-task-form input, #gantt-task-form select, #gantt-task-form textarea, ' +
                        '#gantt-task-form button'
                    ).forEach(el => {
                        if (el === paintBtn) return;
                        if (el.dataset.paintWasDisabled === undefined) {
                            el.dataset.paintWasDisabled = el.disabled ? '1' : '0';
                        }
                        el.disabled = true;
                        if (el.tagName === 'A') el.classList.add('is-disabled');
                    });
                }
            }
        }
        colorSwatches.forEach(button => button.addEventListener('click', () => {
            field('couleur').value = button.dataset.taskColor;
            syncColorPicker();
            markDirty();
        }));

        colorPicker.addEventListener('input', () => {
            field('couleur').value = colorPicker.value;
            syncColorPicker();
            markDirty();
        });

        resetColor.addEventListener('click', () => {
            field('couleur').value = '';
            syncColorPicker();
            markDirty();
        });

        function setEditorVisible(visible) {
            form.hidden = !visible;
            editorToggle.setAttribute('aria-expanded', String(visible));
            const label = visible ? 'Masquer le formulaire de tâche' : 'Afficher le formulaire de tâche';
            editorToggle.title = label;
            editorToggle.setAttribute('aria-label', label);
            editorToggle.querySelector('i').className = visible ? 'fas fa-chevron-up' : 'fas fa-chevron-down';
        }

        setEditorVisible(!form.hidden);

        editorToggle.addEventListener('click', () => setEditorVisible(form.hidden));

        submit.addEventListener('click', () => setEditorVisible(true));

        function showErrors(errors = {}) {
            if (Object.keys(errors).length) setEditorVisible(true);
            form.querySelectorAll('[data-error-for]').forEach(el => { el.textContent = ''; });
            fields.forEach(el => el.removeAttribute('aria-invalid'));
            const general = [];
            Object.entries(errors).forEach(([name, messages]) => {
                const target = form.querySelector(`[data-error-for="${name}"]`);
                if (target) {
                    target.textContent = messages.join(' ');
                    field(name).setAttribute('aria-invalid', 'true');
                } else general.push(...messages);
            });
            root.querySelector('#gantt-form-errors').textContent = general.join(' ')
                || (Object.keys(errors).length ? 'Corrigez les champs signalés.' : '');
        }

        function hasChildren(taskId) {
            return data.editable.some(task => task.parent_id === taskId);
        }

        function syncGroupDurationRule() {
            const group = Boolean(editId && hasChildren(editId));
            if (group) field('type_tache').value = 'GROUPE';
            const locking = field('type_tache').value === 'GROUPE';
            field('type_tache').disabled = group;
            for (const name of ['duree', 'date_debut', 'date_fin']) {
                const input = field(name);
                input.disabled = locking;
                input.title = locking ? 'Calculé automatiquement depuis les sous-tâches' : '';
                if (group) input.value = editable.get(editId).values[name] ?? '';
            }
            groupDurationInfo.classList.toggle('hidden', !locking);
        }

        function updateContext() {
            const reference = editable.get(activeId);
            select.value = activeId;
            position.querySelector('[value="before"]').disabled = !reference;
            if (!reference && position.value === 'before') position.value = 'end';
            root.querySelector('#gantt-position-field').hidden = Boolean(editId);
            const saveLabel = editId ? 'Enregistrer la tâche' : 'Ajouter la tâche';
            submit.title = saveLabel;
            submit.setAttribute('aria-label', saveLabel);
            submit.querySelector('i').className = editId ? 'fas fa-save' : 'fas fa-plus';
            linkButton.disabled = busy || !activeId || !calendar || data.invalid_hierarchy;
            deleteButton.hidden = !activeId;
            deleteButton.disabled = busy || !activeId || !calendar || data.invalid_hierarchy;
            syncGroupDurationRule();
            const linkSummary = root.querySelector('#gantt-task-links');
            linkSummary.textContent = window.GoPlanTaskLinks.describe(data, editId);
            linkSummary.title = linkSummary.textContent;
            context.textContent = editId
                ? `Modification : ${editable.get(editId).label}`
                : position.value === 'before'
                    ? `Nouvelle tâche — avant ${reference.label}`
                    : 'Nouvelle tâche — à la fin du planning';
            svg.querySelectorAll('.bar-wrapper').forEach(el => {
                const selected = el.dataset.id === activeId;
                el.classList.toggle('gantt-selected', selected);
                el.setAttribute('aria-pressed', String(selected));
            });
            if (leftBody) {
                leftBody.querySelectorAll('.goplan-gantt-left-row').forEach(el => {
                    el.classList.toggle('is-selected', el.dataset.id === activeId);
                    el.querySelector('.goplan-task-label').setAttribute(
                        'aria-pressed', String(el.dataset.id === activeId));
                });
                if (activeId) {
                    const row = leftBody.querySelector(
                        `.goplan-gantt-left-row[data-id="${CSS.escape(activeId)}"]`
                    );
                    if (row) {
                        const bounds = row.getBoundingClientRect();
                        const viewportTop = scroller.getBoundingClientRect().top + scroller.clientTop;
                        const top = viewportTop + leftHeader.getBoundingClientRect().height;
                        const bottom = viewportTop + scroller.clientHeight;
                        if (bounds.top < top) scroller.scrollTop += bounds.top - top;
                        else if (bounds.bottom > bottom) scroller.scrollTop += bounds.bottom - bottom;
                    }
                }
            }
            syncPaintButton();
        }

        function resetEditor(id = '') {
            if (paintMode) exitPaintMode();
            if (colorPanel.matches(':popover-open')) colorPanel.hidePopover();
            editId = id;
            showErrors();
            status.textContent = '';
            if (id) {
                fields.forEach(el => { el.value = editable.get(id).values[el.name] ?? ''; });
            } else {
                fields.forEach(el => { el.value = ''; });
                field('type_tache').value = 'TACHE';
                field('contrainte').value = 'ASAP';
                field('duree').value = '1';
                field('avancement').value = '0';
                if (calendar) {
                    try {
                        const last = data.editable.map(task => task.values.date_fin).filter(Boolean).sort().pop();
                        const start = last ? calendar.nextDate(last) : root.dataset.planStart;
                        field('date_debut').value = calendar.nextWorkingDay(start);
                        field('date_fin').value = calendar.endDate(field('date_debut').value, 1);
                    } catch (err) {
                        console.error('[GoPlan/Gantt] Date initiale', err);
                        showErrors({ __all__: [err.message] });
                    }
                }
            }
            syncColorPicker();
            baseline = snapshot();
            markDirty();
            updateContext();
        }

        function updateData(next) {
            data = next;
            // HTMX history restores the serialized DOM, not this closure.
            root.querySelector('#goplan-gantt-data').textContent = JSON.stringify(data)
                .replace(/</g, '\\u003C').replace(/>/g, '\\u003E').replace(/&/g, '\\u0026');
            editable = new Map(data.editable.map(task => [task.id, task]));
            byId = new Map(data.tasks.map(task => [task.id, task]));
            select.replaceChildren(new Option('— Aucune —', ''));
            data.editable.forEach(task => select.add(new Option(task.label, task.id)));
            const undated = root.querySelector('#gantt-undated');
            undated.textContent = `${data.undated_count} tâche(s) sans dates complètes ou avec des dates inversées : non affichée(s). Utilisez la liste des tâches pour les modifier.`;
            undated.classList.toggle('hidden', !data.undated_count);
            root.querySelector('#gantt-hierarchy-warning').classList.toggle('hidden', !data.invalid_hierarchy);
        }

        function drawLinks() {
            svg.querySelectorAll('.gantt-links').forEach(el => el.remove());
            const ns = 'http://www.w3.org/2000/svg';
            const layer = document.createElementNS(ns, 'g');
            layer.classList.add('gantt-links');
            const bars = new Map([...svg.querySelectorAll('.bar-wrapper')].map(wrapper => [
                wrapper.dataset.id, wrapper.querySelector('.bar'),
            ]));
            for (const link of data.links) {
                const predecessor = bars.get(link.predecessor);
                const successor = bars.get(link.successor);
                if (!predecessor || !successor) continue;
                const edge = (bar, finish, id) => Number(bar.getAttribute('x'))
                    + (finish && byId.get(id).type !== 'JALON' ? Number(bar.getAttribute('width')) : 0);
                const sourceFinish = link.type[0] === 'F';
                const targetFinish = link.type[1] === 'F';
                const x1 = edge(predecessor, sourceFinish, link.predecessor);
                const x2 = edge(successor, targetFinish, link.successor);
                const y1 = Number(predecessor.getAttribute('y')) + Number(predecessor.getAttribute('height')) / 2;
                const y2 = Number(successor.getAttribute('y')) + Number(successor.getAttribute('height')) / 2;
                const outer1 = x1 + (sourceFinish ? 12 : -12);
                const outer2 = x2 + (targetFinish ? 12 : -12);
                const middle = (y1 + y2) / 2;
                const path = document.createElementNS(ns, 'path');
                path.classList.add('gantt-link-arrow', 'gantt-link-connector');
                const direction = targetFinish ? 1 : -1;
                path.setAttribute('d', connectorPath([
                    [x1, y1], [outer1, y1], [outer1, middle],
                    [outer2, middle], [outer2, y2], [x2, y2],
                ], appearance.gantt_liaison === 'arrondis'));
                if (appearance.gantt_liaison === 'tirets') path.setAttribute('stroke-dasharray', '6 4');
                if (appearance.gantt_liaison === 'pointilles') {
                    path.setAttribute('stroke-dasharray', '1 4');
                    path.setAttribute('stroke-linecap', 'round');
                }
                const title = document.createElementNS(ns, 'title');
                title.textContent = `${editable.get(link.predecessor)?.label} → ${editable.get(link.successor)?.label} : ${link.type}, ${link.lag} j ouvrés`;
                path.appendChild(title);
                layer.appendChild(path);
                const head = document.createElementNS(ns, 'path');
                head.classList.add('gantt-link-arrow');
                head.setAttribute('d', `M ${x2 + direction * 5} ${y2 - 4} L ${x2} ${y2} L ${x2 + direction * 5} ${y2 + 4}`);
                layer.appendChild(head);
                const label = document.createElementNS(ns, 'text');
                label.classList.add('gantt-link-label');
                label.setAttribute('x', (outer1 + outer2) / 2);
                label.setAttribute('y', middle - 3);
                label.setAttribute('text-anchor', 'middle');
                label.textContent = `${link.type}${link.lag ? ` ${link.lag > 0 ? '+' : ''}${link.lag}j` : ''}`;
                layer.appendChild(label);
            }
            svg.appendChild(layer);
        }

        function decorate() {
            svg.querySelectorAll('.bar-wrapper').forEach(wrapper => {
                wrapper.querySelectorAll('.gantt-summary, .gantt-diamond').forEach(el => el.remove());
                const task = byId.get(wrapper.dataset.id);
                wrapper.style.removeProperty('--goplan-task-color');
                if (/^#[0-9a-f]{6}$/i.test(task.color || '')) {
                    wrapper.style.setProperty('--goplan-task-color', task.color);
                }
                wrapper.setAttribute('tabindex', '0');
                wrapper.setAttribute('role', 'button');
                wrapper.setAttribute('aria-label', `${task.name}, ${formatDate(task.start)} - ${formatDate(task.end)}`);
                const bar = wrapper.querySelector('.bar');
                const geometry = barGeometry(appearance);
                wrapper.querySelectorAll('.bar, .bar-progress').forEach(rect => {
                    rect.setAttribute('rx', geometry.radius);
                    rect.setAttribute('ry', geometry.radius);
                });
                const x = Number(bar.getAttribute('x'));
                const y = Number(bar.getAttribute('y')) + Number(bar.getAttribute('height')) / 2;
                if (task.type === 'GROUPE') {
                    const width = Number(bar.getAttribute('width'));
                    const scale = geometry.height / 22;
                    const cap = Math.min(6 * scale, width / 2);
                    const summary = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    summary.setAttribute('d', appearance.gantt_groupe === 'bande'
                        ? `M ${x} ${y - 5 * scale} H ${x + width} V ${y + 5 * scale} H ${x} Z`
                        : `M ${x} ${y - 5 * scale} H ${x + width} V ${y + 8 * scale} L ${x + width - cap} ${y + 2 * scale} H ${x + cap} L ${x} ${y + 8 * scale} Z`);
                    summary.classList.add('gantt-summary');
                    bar.parentElement.insertBefore(summary, bar);
                }
                if (task.type !== 'JALON') return;
                const size = 8 * geometry.height / 22;
                const circle = appearance.gantt_jalon === 'cercle';
                const diamond = document.createElementNS('http://www.w3.org/2000/svg', circle ? 'circle' : 'polygon');
                if (circle) {
                    diamond.setAttribute('cx', x);
                    diamond.setAttribute('cy', y);
                    diamond.setAttribute('r', size);
                } else {
                    diamond.setAttribute('points', appearance.gantt_jalon === 'triangle'
                        ? `${x},${y - size} ${x + size},${y + size} ${x - size},${y + size}`
                        : `${x},${y - size} ${x + size},${y} ${x},${y + size} ${x - size},${y}`);
                }
                diamond.classList.add('gantt-diamond');
                wrapper.appendChild(diamond);
            });
            drawLinks();
            syncLeftLayout();
            drawCalendar();
            syncCalendarHeader();
            updateContext();
        }

        function syncCalendarHeader() {
            const header = svg.querySelector('.grid-header');
            const dates = svg.querySelector('.date');
            fixedCalendar.replaceChildren();
            fixedCalendar.hidden = !header || !dates;
            if (!header || !dates) return;
            const height = Number(header.getAttribute('height'));
            fixedCalendar.style.height = `${height}px`;
            fixedCalendar.style.marginBottom = `${-height}px`;
            const copy = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            copy.setAttribute('class', svg.getAttribute('class'));
            copy.setAttribute('width', svg.getAttribute('width'));
            copy.setAttribute('height', height);
            copy.append(header.cloneNode(true), dates.cloneNode(true));
            const separators = svg.querySelector('.gantt-calendar-lines');
            if (separators) copy.appendChild(separators.cloneNode(true));
            fixedCalendar.appendChild(copy);
        }

        function drawCalendar() {
            svg.querySelectorAll('.gantt-calendar-bands, .gantt-calendar-lines').forEach(el => el.remove());
            const firstRow = svg.querySelector('.grid-row');
            if (!firstRow) return;
            const ns = 'http://www.w3.org/2000/svg';
            const top = Number(firstRow.getAttribute('y'));
            const width = Number(firstRow.getAttribute('width'));
            const bottom = top + gantt.tasks.length * Number(firstRow.getAttribute('height'));
            const bands = document.createElementNS(ns, 'g');
            bands.classList.add('gantt-calendar-bands');
            const lines = document.createElementNS(ns, 'g');
            lines.classList.add('gantt-calendar-lines');
            const divider = gantt.options.header_height - 18;
            const line = (x1, y1, x2, y2, className) => {
                const el = document.createElementNS(ns, 'line');
                for (const [name, value] of Object.entries({ x1, y1, x2, y2 })) {
                    el.setAttribute(name, value);
                }
                el.setAttribute('class', className);
                lines.appendChild(el);
            };
            line(0, divider, width, divider, 'gantt-header-divider');
            line(0, top, width, top, 'gantt-header-divider');
            const dayWidth = gantt.options.column_width / (currentView === 'Month' ? 30 : gantt.options.step / 24);
            for (const day of timelineDays(gantt.gantt_start, width, dayWidth, calendar)) {
                if (day.nonWorking) {
                    const band = document.createElementNS(ns, 'rect');
                    for (const [name, value] of Object.entries({
                        x: day.x, y: top, width: day.width, height: bottom - top,
                    })) band.setAttribute(name, value);
                    band.dataset.date = day.date;
                    bands.appendChild(band);
                }
                if (day.boundary) {
                    const y = day.boundary === 'week' ? (currentView === 'Month' ? top : divider) : 0;
                    line(day.x, y, day.x, bottom, `gantt-period-${day.boundary}`);
                }
            }
            // Behind bars and links: shading never changes their color or click targets.
            const grid = svg.querySelector('.grid');
            grid.append(bands, lines);
        }

        function updateZoomControls() {
            const unavailable = !gantt || !data.tasks.length || !error.classList.contains('hidden');
            zoomOut.disabled = unavailable || zoomIndex === 0;
            zoomIn.disabled = unavailable || zoomIndex === zoomLevels.length - 1;
            zoomLabel.textContent = `${zoomLevels[zoomIndex] * 100} %`;
        }

        function applyZoom() {
            const geometry = barGeometry(appearance);
            gantt.options.bar_height = geometry.height;
            gantt.options.bar_corner_radius = geometry.radius;
            gantt.options.padding = parseFloat(getComputedStyle(svg.closest('.goplan-gantt-container'))
                .getPropertyValue('--goplan-row-height')) - geometry.height;
            gantt.options.column_width = columnWidths[currentView] * zoomLevels[zoomIndex];
            gantt.render();
            decorate();
            updateZoomControls();
        }

        function renderLeftPanel() {
            if (!leftBody) return;
            leftBody.replaceChildren();

            if (!data.tasks.length) {
                const empty = document.createElement('div');
                empty.className = 'goplan-gantt-left-empty';
                empty.textContent = 'Aucune tâche affichable';
                leftBody.appendChild(empty);
                return;
            }

            const frag = document.createDocumentFragment();
            for (const task of visibleTasks(data, collapsed)) {
                const row = document.createElement('div');
                row.className = 'goplan-gantt-left-row';
                row.dataset.id   = task.id;
                row.dataset.type = task.type;
                if (task.critical) row.classList.add('is-critical');
                row.style.paddingLeft = `${0.5 + (task.level || 0) * 0.85}rem`;
                row.setAttribute('title', task.name);

                const dot = document.createElement('span');
                dot.className = 'goplan-type-dot';
                dot.setAttribute('aria-hidden', 'true');

                if (hasChildren(task.id)) {
                    const toggle = document.createElement('button');
                    toggle.type = 'button';
                    toggle.className = 'goplan-gantt-group-toggle';
                    const expanded = !collapsed.has(task.id);
                    toggle.setAttribute('aria-expanded', String(expanded));
                    toggle.setAttribute('aria-label',
                        `${expanded ? 'Masquer' : 'Afficher'} les sous-tâches de ${task.name}`);
                    toggle.title = toggle.getAttribute('aria-label');
                    const icon = document.createElement('i');
                    icon.className = expanded ? 'fas fa-chevron-down' : 'fas fa-chevron-right';
                    icon.setAttribute('aria-hidden', 'true');
                    toggle.appendChild(icon);
                    toggle.addEventListener('click', () => {
                        if (collapsed.has(task.id)) collapsed.delete(task.id);
                        else collapsed.add(task.id);
                        root.dataset.collapsedGroups = JSON.stringify([...collapsed]);
                        persistFold([task.id], collapsed.has(task.id));
                        render();
                        leftBody.querySelector(
                            `[data-id="${CSS.escape(task.id)}"] .goplan-gantt-group-toggle`
                        ).focus({ preventScroll: true });
                    });
                    row.appendChild(toggle);
                } else row.appendChild(dot);

                const label = document.createElement('button');
                label.type = 'button';
                label.className = 'goplan-task-label';
                label.textContent = task.name;
                label.setAttribute('aria-pressed', String(task.id === activeId));

                row.appendChild(label);
                label.addEventListener('click', () => {
                    if (task.id === activeId) {
                        setEditorVisible(true);
                        field('nom').focus();
                    } else {
                        selectTask(task.id);
                    }
                });
                frag.appendChild(row);
            }
            leftBody.appendChild(frag);

            if (activeId) {
                leftBody.querySelector(
                    `.goplan-gantt-left-row[data-id="${CSS.escape(activeId)}"]`
                )?.classList.add('is-selected');
            }
        }

        function syncLeftLayout() {
            const row = svg.querySelector('.grid-row');
            if (!row || !leftHeader || !leftBody) return;
            // Frappe starts its rows before the bottom of its header rectangle.
            const top = Number(row.getAttribute('y'));
            leftHeader.style.height = `${top}px`;
            leftHeader.style.minHeight = `${top}px`;
            svg.querySelector('.grid-header').setAttribute('height', top);
            leftBody.style.setProperty('--goplan-row-height', `${row.getAttribute('height')}px`);
        }

        function scrollToFirstTask() {
            const firstX = Math.min(...[...svg.querySelectorAll('.bar-wrapper .bar')]
                .map(bar => Number(bar.getAttribute('x'))));
            const margin = Math.min(gantt.options.column_width,
                (scroller.clientWidth - leftPanel.offsetWidth) / 4);
            scroller.scrollLeft = Math.max(0, firstX - margin);
        }

        function render() {
            error.classList.add('hidden');
            const empty = !data.tasks.length;
            svg.classList.toggle('hidden', empty);
            root.querySelector('#gantt-empty').classList.toggle('hidden', !empty);
            buttons.forEach(button => { button.disabled = empty; });
            today.disabled = empty;
            if (empty) {
                fixedCalendar.hidden = true;
                fixedCalendar.replaceChildren();
                svg.replaceChildren();
                renderLeftPanel();
                updateZoomControls();
                return;
            }
            try {
                if (typeof window.Gantt !== 'function') throw new Error('Frappe Gantt indisponible.');
                const tasks = visibleTasks(data, collapsed).map(task => ({
                    id: task.id,
                    name: escapeHTML(`${'\u00a0\u00a0\u00a0'.repeat(task.level)}${task.name}`),
                    start: task.start, end: task.end, progress: task.progress,
                    dependencies: [],
                    custom_class: [
                        task.critical ? 'gantt-critical' : '',
                        task.type === 'GROUPE' ? 'gantt-group' : '',
                        task.type === 'JALON' ? 'gantt-milestone' : '',
                        task.type === 'RECUR' ? 'gantt-recurring' : '',
                    ].join(' '),
                }));
                if (gantt) {
                    const left = scroller.scrollLeft;
                    const top = scroller.scrollTop;
                    gantt.refresh(tasks);
                    applyZoom();
                    scroller.scrollLeft = left;
                    scroller.scrollTop = top;
                } else {
                    gantt = new window.Gantt(svg, tasks, {
                        view_mode: currentView, language: 'fr',
                        bar_height: 22, bar_corner_radius: 7,
                        padding: parseFloat(getComputedStyle(svg.closest('.goplan-gantt-container'))
                            .getPropertyValue('--goplan-row-height')) - 22,
                        custom_popup_html: () => '',
                    });
                    applyZoom();
                    if (!loadGanttScroll()) scrollToFirstTask();
                }
            } catch (err) {
                fixedCalendar.hidden = true;
                console.error('[GoPlan/Gantt]', err);
                svg.classList.add('hidden');
                error.textContent = "Impossible d'afficher le Gantt. Rechargez la page et vérifiez l'accès au CDN Frappe Gantt.";
                error.classList.remove('hidden');
                buttons.forEach(button => { button.disabled = true; });
                today.disabled = true;
            }
            renderLeftPanel();
            updateContext();
            updateZoomControls();
        }

        function setBusy(value) {
            busy = value;
            fieldset.disabled = value || !calendar || data.invalid_hierarchy;
            submit.disabled = fieldset.disabled;
            select.disabled = value;
            newButton.disabled = value;
            linkButton.disabled = value || !activeId || !calendar || data.invalid_hierarchy;
            deleteButton.disabled = value || !activeId || !calendar || data.invalid_hierarchy;
            form.setAttribute('aria-busy', String(value));
            syncColorSaveButton();
            syncPaintButton();
            if (!value && paintMode) {
                // busy terminé : re-verrouille tout sauf le brush
                root.querySelectorAll(
                    '.goplan-toolbar-btn, .goplan-toolbar a, #gantt-task-select, .gantt-view-btn, ' +
                    '#gantt-task-form input, #gantt-task-form select, #gantt-task-form textarea, ' +
                    '#gantt-task-form button'
                ).forEach(el => {
                    if (el === paintBtn) return;
                    if (el.dataset.paintWasDisabled === undefined) {
                        el.dataset.paintWasDisabled = el.disabled ? '1' : '0';
                    }
                    el.disabled = true;
                    if (el.tagName === 'A') el.classList.add('is-disabled');
                });
            }
        }

        async function saveTask() {
            if (busy || fieldset.disabled) return false;
            setEditorVisible(true);
            if (!form.reportValidity()) return false;
            showErrors();
            status.textContent = '';
            const wasEditing = Boolean(editId);
            const payload = new FormData(form);
            payload.set('task_id', editId);
            payload.set('reference_id', activeId);
            payload.set('position', position.value);
            payload.set('revision', data.revision);
            setBusy(true);
            try {
                const response = await fetch(form.action, {
                    method: 'POST', body: payload,
                    headers: { 'X-CSRFToken': field('csrfmiddlewaretoken').value, 'Accept': 'application/json' },
                });
                if (response.redirected) throw new Error("Session expirée. Reconnectez-vous avant d'enregistrer.");
                if (!response.headers.get('content-type')?.includes('application/json')) {
                    throw new Error(`Enregistrement refusé (HTTP ${response.status}). Rechargez la page après avoir conservé votre saisie.`);
                }
                const result = await response.json();
                if (!response.ok) {
                    showErrors(result.errors || { __all__: [`Enregistrement refusé (HTTP ${response.status}).`] });
                    return false;
                }
                updateData(result);
                if (wasEditing || position.value === 'end') activeId = result.saved_id;
                if (wasEditing) editId = result.saved_id;
                render();
                resetEditor(wasEditing ? result.saved_id : '');
                status.textContent = wasEditing ? 'Tâche enregistrée.' : 'Tâche ajoutée. La ligne est prête pour la suivante.';
                return true;
            } catch (err) {
                console.error('[GoPlan/Gantt] Enregistrement', err);
                showErrors({ __all__: [err.message] });
                return false;
            } finally {
                setBusy(false);
                if (!wasEditing && !dirty()) field('nom').focus();
            }
        }

        function decide() {
            return new Promise(resolve => {
                const finish = value => {
                    dialog.removeEventListener('click', click);
                    dialog.removeEventListener('cancel', cancel);
                    dialog.close();
                    resolve(value);
                };
                const click = event => {
                    const button = event.target.closest('[data-decision]');
                    if (button) finish(button.dataset.decision);
                };
                const cancel = event => { event.preventDefault(); finish('stay'); };
                dialog.addEventListener('click', click);
                dialog.addEventListener('cancel', cancel);
                dialog.showModal();
            });
        }

        async function transition(action) {
            if (busy) {
                status.textContent = 'Enregistrement en cours. Patientez avant de changer de page.';
                return;
            }
            if (dialog.open) return;
            if (dirty()) {
                const choice = await decide();
                if (choice === 'stay' || (choice === 'save' && !await saveTask())) {
                    select.value = activeId;
                    return;
                }
            }
            action();
        }

        async function deleteTask() {
            if (busy || deleteButton.disabled || !activeId) return;
            const removed = new Set([activeId]);
            let count;
            do {
                count = removed.size;
                data.editable.forEach(task => {
                    if (removed.has(task.parent_id)) removed.add(task.id);
                });
            } while (removed.size !== count);
            const descendants = removed.size - 1;
            const message = `Supprimer « ${editable.get(activeId).label} »`
                + (descendants ? ` et ses ${descendants} sous-tâche(s)` : '')
                + ' ? Les liaisons et affectations associées seront aussi supprimées.'
                + (dirty() ? ' La saisie non enregistrée sera abandonnée.' : '');
            if (!window.confirm(message)) return;
            const payload = new FormData();
            payload.set('task_id', activeId);
            payload.set('revision', data.revision);
            showErrors();
            status.textContent = '';
            setBusy(true);
            try {
                const response = await fetch(deleteButton.dataset.url, {
                    method: 'POST', body: payload,
                    headers: { 'X-CSRFToken': field('csrfmiddlewaretoken').value, 'Accept': 'application/json' },
                });
                if (response.redirected) throw new Error('Session expirée : reconnectez-vous avant de supprimer.');
                if (!response.headers.get('content-type')?.includes('application/json')) {
                    throw new Error(`Suppression refusée (HTTP ${response.status}). Rechargez la page.`);
                }
                const result = await response.json();
                if (!response.ok) {
                    showErrors(result.errors || { __all__: [`Suppression refusée (HTTP ${response.status}).`] });
                    return;
                }
                activeId = '';
                updateData(result);
                resetEditor();
                render();
                status.textContent = `${result.deleted_count} tâche(s) supprimée(s).`;
            } catch (err) {
                console.error('[GoPlan/Gantt] Suppression', err);
                showErrors({ __all__: [err.message] });
            } finally {
                setBusy(false);
            }
        }
        deleteButton.addEventListener('click', deleteTask);

        const links = window.GoPlanTaskLinks(root, {
            getData: () => data,
            csrfToken: () => field('csrfmiddlewaretoken').value,
            setBusy,
            onSaved(result, action) {
                updateData(result);
                render();
                resetEditor(activeId);
                status.textContent = action === 'delete'
                    ? 'Liaison supprimée. Les autres contraintes restent appliquées.'
                    : 'Liaison enregistrée et dates des successeurs recalculées.';
            },
        });

        linkButton.addEventListener('click', () => transition(() => {
            resetEditor(activeId);
            links.open(activeId);
        }));

        function revealTask(id) {
            const visited = new Set([id]);
            let parent = editable.get(id)?.parent_id;
            const opened = [];
            while (parent && !visited.has(parent)) {
                if (collapsed.delete(parent)) opened.push(parent);
                visited.add(parent);
                parent = editable.get(parent)?.parent_id;
            }
            if (opened.length) {
                root.dataset.collapsedGroups = JSON.stringify([...collapsed]);
                persistFold(opened, false);
                render();
            }
        }

        // Remembers the folded state so the inline editor and the print preview use it too.
        function persistFold(ids, folded) {
            if (!root.dataset.foldUrl) return;
            ids.forEach(id => {
                const body = new FormData();
                body.append('task', id);
                body.append('replie', folded ? '1' : '0');
                fetch(root.dataset.foldUrl, {
                    method: 'POST', body, credentials: 'same-origin',
                    headers: { 'X-CSRFToken': field('csrfmiddlewaretoken').value, 'Accept': 'application/json' },
                }).then(response => {
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                }).catch(err => {
                    console.error('[GoPlan/Gantt] Mémorisation du repli', err);
                    status.textContent = "L'état replié n'a pas pu être mémorisé.";
                });
            });
        }

        function selectTask(id) {
            if (id === editId && id === activeId) {
                revealTask(id);
                setEditorVisible(true);
                return;
            }
            transition(() => {
                activeId = id;
                revealTask(id);
                resetEditor(id);
                setEditorVisible(true);
                field('nom').focus();
            });
        }

        select.addEventListener('change', () => {
            const id = select.value;
            select.value = activeId;
            selectTask(id);
        });

        form.addEventListener('goplan:leave', event => transition(event.detail.proceed));

        newButton.addEventListener('click', () => transition(() => {
            resetEditor();
            setEditorVisible(true);
            field('nom').focus();
        }));

        position.addEventListener('change', updateContext);

        form.addEventListener('input', markDirty);

        form.addEventListener('change', event => {
            try {
                syncGroupDurationRule();
                if (calendar && field('type_tache').value !== 'GROUPE'
                    && ['date_debut', 'date_fin', 'duree', 'type_tache'].includes(event.target.name)) {
                    const start = field('date_debut');
                    const end = field('date_fin');
                    const duration = field('duree');
                    if (field('type_tache').value === 'JALON') {
                        duration.value = '0';
                        end.value = start.value;
                    } else if (start.value) {
                        start.value = calendar.nextWorkingDay(start.value);
                        if (event.target === end && end.value) {
                            if (end.value < start.value) throw new Error('La fin ne peut précéder le début.');
                            duration.value = calendar.workingDaysBetween(start.value, end.value);
                        }
                        if (duration.value && Number(duration.value) > 0) {
                            end.value = calendar.endDate(start.value, Number(duration.value));
                        }
                    }
                }
            } catch (err) {
                console.error('[GoPlan/Gantt] Calendrier', err);
                showErrors({ __all__: [err.message] });
            }
            if (event.target.name === 'type_tache') syncGroupDurationRule();
            markDirty();
        });

        form.addEventListener('submit', event => { event.preventDefault(); saveTask(); });

        // Frappe 0.6.1 has no read-only option; changes go through the form only.
        svg.addEventListener('mousedown', event => {
            if (event.target.closest('.bar-wrapper')) event.stopImmediatePropagation();
        }, true);

        svg.addEventListener('click', event => {
            const wrapper = event.target.closest('.bar-wrapper');
            if (!wrapper) return;
            event.preventDefault();
            if (paintMode) {
                applyPaintToTask(wrapper.dataset.id);
            } else {
                selectTask(wrapper.dataset.id);
            }
        });

        svg.addEventListener('keydown', event => {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            const wrapper = event.target.closest('.bar-wrapper');
            if (!wrapper) return;
            if (paintMode) {
                event.preventDefault();
                event.stopPropagation();
                applyPaintToTask(wrapper.dataset.id);
                return;
            }
            selectTask(wrapper.dataset.id);
        });

        buttons.forEach(button => button.addEventListener('click', () => {
            if (!gantt) return;
            currentView = button.dataset.view;
            gantt.change_view_mode(currentView);
            applyZoom();
            scrollToFirstTask();
            buttons.forEach(other => {
                other.classList.toggle('is-active', other === button);
                other.setAttribute('aria-pressed', String(other === button));
            });
        }));

        function changeZoom(delta) {
            const next = Math.max(0, Math.min(zoomLevels.length - 1, zoomIndex + delta));
            if (!gantt || next === zoomIndex) return;
            const visibleWidth = scroller.clientWidth - leftPanel.offsetWidth;
            const center = (scroller.scrollLeft + visibleWidth / 2) / gantt.options.column_width;
            const top = scroller.scrollTop;
            zoomIndex = next;
            applyZoom();
            scroller.scrollLeft = center * gantt.options.column_width - visibleWidth / 2;
            scroller.scrollTop = top;
        }

        zoomIn.addEventListener('click', () => changeZoom(1));

        zoomOut.addEventListener('click', () => changeZoom(-1));

        today.addEventListener('click', () => {
            if (!gantt) return;
            const days = dayNumber(new Date()) - dayNumber(gantt.gantt_start);
            const x = days * gantt.options.column_width /
                (currentView === 'Month' ? 30 : gantt.options.step / 24);
            const visibleWidth = scroller.clientWidth - leftPanel.offsetWidth;
            const width = svg.getBBox().width;
            status.textContent = x < 0 || x > width
                ? "Aujourd'hui est en dehors de la période affichée." : '';
            scroller.scrollLeft = Math.max(0, Math.min(x - visibleWidth / 2, width));
        });

        root.style.setProperty('--goplan-link-color', appearance.gantt_couleur_liaison);

        // Used by the print preview to print up to a hierarchy level.
        root.addEventListener('goplan:set-collapsed', event => {
            collapsed.clear();
            event.detail.forEach(id => collapsed.add(String(id)));
            root.dataset.collapsedGroups = JSON.stringify([...collapsed]);
            render();
        });

        updateData(data);

        try {
            calendar = new window.GoPlanWorkCalendar(
                JSON.parse(root.querySelector('#goplan-gantt-calendar').textContent),
            );
        } catch (err) {
            console.error('[GoPlan/Gantt] Calendrier', err);
            root.querySelector('#gantt-form-errors').textContent = err.message;
        }

        resetEditor();

        if (!calendar) showErrors({ __all__: ['Calendrier invalide : corrigez-le avant de saisir des tâches.'] });

        render();

        setBusy(false);

        const savedScroll = loadGanttScroll();
        if (savedScroll) {
            requestAnimationFrame(() => {
                scroller.scrollLeft = savedScroll.left;
                scroller.scrollTop = savedScroll.top;
            });
        }
    }

    function init() {
        document.querySelectorAll('[data-goplan-gantt]').forEach(initialize);
    }

    window.GoPlanGantt = { init, visibleTasks, timelineDays, barGeometry, connectorPath };
    
    window.addEventListener('beforeunload', event => {
        if (document.querySelector('#gantt-task-form[data-dirty="true"], #gantt-task-form[aria-busy="true"], #gantt-appearance-form[aria-busy="true"]')) {
            event.preventDefault();
            event.returnValue = '';
        }
    });

    window.addEventListener('beforeunload', () => {
        if (paintMode) exitPaintMode();
    });

    document.addEventListener('htmx:confirm', event => {
        const form = document.querySelector('#gantt-task-form[data-dirty="true"], #gantt-task-form[aria-busy="true"]');
        if (!form || !event.detail.target?.contains(form)) return;
        event.preventDefault();
        form.dispatchEvent(new CustomEvent('goplan:leave', {
            detail: { proceed: () => event.detail.issueRequest(true) },
        }));
    });
    
    document.addEventListener('DOMContentLoaded', init);
    
    document.addEventListener('htmx:afterSettle', init);
    
    document.addEventListener('htmx:historyRestore', init);
    
    init();
})();
