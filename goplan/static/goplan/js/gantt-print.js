(function () {
    'use strict';

    const papers = {
        A4: { portrait: [210, 297], landscape: [297, 210] },
        A3: { portrait: [297, 420], landscape: [420, 297] },
        A2: { portrait: [420, 594], landscape: [594, 420] },
        A1: { portrait: [594, 841], landscape: [841, 594] },
        A0: { portrait: [841, 1189], landscape: [1189, 841] },
    };
    const columnWidths = { Day: 38, Week: 140, Month: 120 };
    const daysPerColumn = { Day: 1, Week: 7, Month: 30 };
    const columns = [
        { key: 'code', field: 'col_code', label: 'CODE' },
        { key: 'duree', field: 'col_duree', label: 'DURÉE', end: true },
        { key: 'debut', field: 'col_debut', label: 'DÉBUT' },
        { key: 'fin', field: 'col_fin', label: 'FIN' },
        { key: 'avancement', field: 'col_avancement', label: 'AV.', end: true },
        { key: 'predecesseurs', field: 'col_predecesseurs', label: 'PRÉDÉCESSEURS', max: 220 },
    ];
    const numberFields = new Set([
        'margin_top', 'margin_bottom', 'margin_left', 'margin_right',
        'weeks_before', 'weeks_after', 'outline_level', 'vertical_pages', 'min_font_size', 'max_row_height',
        'title_font_size', 'subtitle_font_size', 'header_center_font_size', 'footer_font_size',
        'name_max_width', 'column_max_width',
    ]);
    const textFields = [
        ['header_title', 'print-header-title'],
        ['header_subtitle', 'print-header-subtitle'],
        ['header_center', 'print-header-center'],
        ['footer_text', 'print-footer-title'],
    ];
    const fontStacks = {
        arial: 'Arial, Helvetica, sans-serif',
        calibri: 'Calibri, Carlito, Arial, sans-serif',
        verdana: 'Verdana, Geneva, sans-serif',
        tahoma: 'Tahoma, Verdana, sans-serif',
        georgia: 'Georgia, serif',
        times: '"Times New Roman", Times, serif',
    };
    // Task-name size in the 35px source row; every task text scales with the printed row height.
    const baseFont = 13;
    const maxAutoPages = 50;
    const ns = 'http://www.w3.org/2000/svg';
    const svgElement = (tag, attributes = {}) => {
        const element = document.createElementNS(ns, tag);
        Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
        return element;
    };
    const dayNumber = value => Date.parse(`${value}T00:00:00Z`) / 86400000;
    const dateLabel = value => (value ? value.split('-').reverse().join('/') : '');

    function timelineBounds(bars, width, columnWidth) {
        if (!bars.length) return { start: 0, width };
        const start = Math.max(0, Math.floor(Math.min(...bars.map(bar => bar.x)) / columnWidth) * columnWidth - columnWidth);
        const end = Math.min(width, Math.ceil(Math.max(...bars.map(bar => bar.x + bar.width)) / columnWidth) * columnWidth + columnWidth);
        return { start, width: end - start };
    }

    /*
     * The whole page uses one uniform scale, so texts keep their proportions. The scale is capped by
     * the paper width (scaleX), the maximum row height (maxPoints) and, when rows do not fit, the
     * sheet height. Any spare width widens the timeline only (stretch >= 1).
     * pages = 0 chooses just enough pages to keep the task text at minPoints.
     */
    function pageLayout({
        width, headerHeight, rowHeight, rowCount, chartWidth, chartHeight, pages, minPoints, maxPoints = Infinity,
    }) {
        const scaleX = chartWidth / width;
        const pointsPerScale = baseFont * 72 / 96;
        const cap = Math.min(scaleX, maxPoints / pointsPerScale);
        const rows = Math.max(1, rowCount);
        const scaleFor = count => Math.min(cap, chartHeight / (headerHeight + count * rowHeight + 1));
        const target = Math.min(cap, minPoints / pointsPerScale);
        const fitting = Math.floor((chartHeight / target - headerHeight - 1) / rowHeight + 1e-9);
        const neededPages = fitting >= 1 ? Math.ceil(rows / fitting) : rows;
        const requested = pages > 0 ? pages : Math.min(maxAutoPages, neededPages);
        const evenRows = Math.ceil(rows / Math.min(rows, requested));
        const scale = scaleFor(evenRows);
        // Fill every sheet to capacity at this scale; the last one receives the remainder.
        const capacity = Math.floor((chartHeight / scale - headerHeight - 1) / rowHeight + 1e-9);
        const rowsPerPage = Math.min(rows, Math.max(evenRows, capacity));
        return {
            pages: Math.ceil(rows / rowsPerPage),
            requestedPages: requested,
            rowsPerPage,
            scaleX,
            scale,
            viewWidth: chartWidth / scale,
            fontPoints: scale * pointsPerScale,
            widthPoints: scaleX * pointsPerScale,
            neededPages,
            widthLimited: scaleX * pointsPerScale < minPoints - 1e-6,
        };
    }

    function rowFontPoints(rowHeightMm) {
        return rowHeightMm / 25.4 * 72 * baseFont / 35;
    }

    function previewScale(paperWidth, availableWidth, requested) {
        const fit = Math.min(1.1, Math.max(1, availableWidth) / paperWidth);
        return { fit, scale: requested === null ? fit : Math.max(fit, Math.min(1.1, requested)) };
    }

    function progressColor(color) {
        return '#' + [1, 3, 5].map(start =>
            Math.round(parseInt(color.slice(start, start + 2), 16) * 0.75).toString(16).padStart(2, '0'),
        ).join('');
    }

    function periodBounds(start, end, referenceDate, referenceX, dayWidth, width) {
        const first = referenceX + (dayNumber(start) - dayNumber(referenceDate)) * dayWidth;
        const last = referenceX + (dayNumber(end) - dayNumber(referenceDate) + 1) * dayWidth;
        if (!Number.isFinite(first) || !Number.isFinite(last) || last <= first) {
            throw new Error("Renseignez une période valide, avec une fin après le début.");
        }
        const from = Math.max(0, first);
        const to = Math.min(width, last);
        if (to <= from) throw new Error("La période choisie se situe hors du calendrier affichable.");
        return { start: from, width: to - from };
    }

    function shiftDate(value, days) {
        const date = new Date(`${value}T00:00:00Z`);
        date.setUTCDate(date.getUTCDate() + days);
        return date.toISOString().slice(0, 10);
    }

    function relativePeriod(statusDate, weeksBefore, weeksAfter) {
        if (!statusDate) {
            throw new Error("La période « autour de la date d'état » exige une date d'état : renseignez-la dans les informations du planning.");
        }
        const before = Number(weeksBefore) || 0;
        const after = Number(weeksAfter) || 0;
        if (before + after < 1) throw new Error("Choisissez au moins une semaine avant ou après la date d'état.");
        return { start: shiftDate(statusDate, -7 * before), end: shiftDate(statusDate, 7 * after) };
    }

    function substituteVariables(template, values) {
        return String(template || '').replace(/\{(\w+)\}/g, (match, name) =>
            (Object.prototype.hasOwnProperty.call(values, name) ? String(values[name] ?? '') : match));
    }

    function cellText(row, key) {
        const number = value => Number(value).toLocaleString('fr-FR', { maximumFractionDigits: 2 });
        if (key === 'duree') return `${number(row.duree)} j`;
        if (key === 'avancement') return `${number(row.avancement)} %`;
        if (key === 'debut' || key === 'fin') return dateLabel(row[key]);
        return row[key] || '';
    }

    function taskLabel(row, withCodeColumn) {
        return withCodeColumn || !row.code ? row.nom : `${row.code} ${row.nom}`;
    }

    // Rows hidden by the outline level are collapsed in the source Gantt; undated rows are listed last.
    function collapsedForLevel(rows, outlineLevel) {
        if (!outlineLevel) return [];
        return rows.filter(row => row.level >= outlineLevel - 1).map(row => row.id);
    }

    // Groups folded in the editor or the Gantt are added to the outline-level selection on request.
    function collapsedIds(rows, outlineLevel, respectCollapsed) {
        const ids = new Set(collapsedForLevel(rows, outlineLevel));
        if (respectCollapsed) rows.filter(row => row.replie).forEach(row => ids.add(row.id));
        return [...ids];
    }

    function hasCollapsedAncestor(row, byId, collapsed) {
        const visited = new Set([row.id]);
        let parent = row.parent_id;
        while (parent && !visited.has(parent)) {
            if (collapsed.has(parent)) return true;
            visited.add(parent);
            parent = byId.get(parent)?.parent_id;
        }
        return false;
    }

    function selectRows(rows, visibleDatedIds, datedIds, settings, collapsed = new Set()) {
        const byId = new Map(rows.map(row => [row.id, row]));
        const maxLevel = settings.outline_level ? settings.outline_level - 1 : Infinity;
        const dated = visibleDatedIds.map(id => byId.get(id)).filter(Boolean);
        const undated = settings.show_undated_tasks
            ? rows.filter(row => !datedIds.has(row.id) && row.level <= maxLevel
                && !hasCollapsedAncestor(row, byId, collapsed))
                .map(row => ({ ...row, undated: true }))
            : [];
        return dated.concat(undated);
    }

    const pxPerMm = 96 / 25.4;

    /*
     * Column widths in layout units. Limits are given in printed millimetres (0 = automatic), so they
     * depend on the page scale: limit = mm * px/mm / scale.
     */
    function columnLayout(naturalName, naturalColumns, nameLimitMm, columnLimitMm, scale) {
        const limit = mm => (mm > 0 ? mm * pxPerMm / scale : Infinity);
        const nameWidth = Math.ceil(Math.min(naturalName, limit(nameLimitMm)));
        let x = nameWidth;
        const columns = naturalColumns.map(natural => {
            const width = Math.ceil(Math.min(natural, limit(columnLimitMm)));
            const column = { x, width };
            x += width;
            return column;
        });
        return { nameWidth, columns, leftWidth: x };
    }

    // Per-tab markers: unsaved fields (dirty) and fields rejected by the server (error).
    function tabStates(fields, settings, saved, errors, tabOf) {
        const states = {};
        const mark = (name, key) => {
            const tab = tabOf(name);
            if (!tab) return;
            states[tab] = states[tab] || { dirty: false, error: false };
            states[tab][key] = true;
        };
        fields.forEach(name => {
            if ((settings[name] ?? null) !== (saved[name] ?? null)) mark(name, 'dirty');
        });
        Object.keys(errors || {}).forEach(name => mark(name, 'error'));
        return states;
    }

    window.GoPlanGanttPrint = {
        papers, timelineBounds, pageLayout, rowFontPoints, progressColor, periodBounds, previewScale, fontStacks,
        relativePeriod, substituteVariables, cellText, taskLabel, collapsedForLevel, collapsedIds, selectRows,
        columnLayout, tabStates,
    };

    function initialize() {
        const chart = document.querySelector('#print-chart');
        if (!chart) return;
        const source = document.querySelector('.print-render-source [data-goplan-gantt]');
        // The preview folds groups itself: it must never overwrite the folded state saved by the user.
        if (source) delete source.dataset.foldUrl;
        const sheet = document.querySelector('#print-sheet');
        const pagesHost = document.querySelector('#print-pages');
        const fitAlert = document.querySelector('#print-fit-alert');
        const fitAlertText = document.querySelector('#print-fit-alert-text');
        const fitAlertButton = document.querySelector('#print-fit-alert-button');
        const previewStage = document.querySelector('#print-preview-stage');
        const stage = document.querySelector('.print-paper-stage');
        const zoomInput = document.querySelector('#print-zoom');
        const zoomLabel = document.querySelector('#print-zoom-label');
        const zoomOut = document.querySelector('#print-zoom-out');
        const zoomIn = document.querySelector('#print-zoom-in');
        const dialog = document.querySelector('#print-settings-dialog');
        const form = document.querySelector('#print-settings-form');
        const startInput = document.querySelector('#ps-date-start');
        const endInput = document.querySelector('#ps-date-end');
        const printButton = document.querySelector('#print-button');
        const mainPrintButton = document.querySelector('#print-main-button');
        const saveButton = document.querySelector('#ps-save-settings');
        const resetButton = document.querySelector('#ps-reset-settings');
        const saveStatus = document.querySelector('#ps-save-status');
        const saveErrors = document.querySelector('#ps-save-errors');
        const error = document.querySelector('#print-error');
        const status = document.querySelector('#print-status');
        const readJson = id => JSON.parse(document.getElementById(id).textContent);
        const stored = readJson('goplan-print-settings');
        const printRows = readJson('goplan-print-rows');
        const planContext = readJson('goplan-print-context');
        const data = JSON.parse(source.querySelector('#goplan-gantt-data').textContent);
        const appearance = JSON.parse(source.querySelector('#goplan-gantt-appearance').textContent);
        const datedIds = new Set(data.tasks.map(task => task.id));
        const fields = Object.keys(stored.defaults);
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        const printDate = new Date().toLocaleDateString('fr-FR');
        let saved = { ...stored.values };
        let revision = stored.revision;
        let isSaved = stored.saved;
        let settings = { ...stored.values };
        let sourceView = 'Week';
        let collapsedKey = null;
        let periodLabel = '';
        let requestedScale = null;
        let screenScale = 1;
        let fitScale = 1;
        let model = null;
        let layout = null;
        const starts = data.tasks.map(task => task.start).sort();
        const ends = data.tasks.map(task => task.end).sort();
        const fullStart = starts[0] || source.dataset.planStart;
        const fullEnd = ends.at(-1) || fullStart;

        // URL parameters (links from the Gantt) override the saved settings for this visit.
        const parameters = new URLSearchParams(window.location.search);
        if (Object.hasOwn(papers, parameters.get('format'))) settings.format = parameters.get('format');
        if (Object.hasOwn(columnWidths, parameters.get('view'))) settings.timescale = parameters.get('view');
        if (['portrait', 'landscape'].includes(parameters.get('orientation'))) {
            settings.orientation = parameters.get('orientation');
        }

        function writeForm() {
            fields.forEach(name => {
                const input = form.elements.namedItem(name);
                if (!input) return;
                if (input.type === 'checkbox') input.checked = Boolean(settings[name]);
                else input.value = settings[name] ?? '';
            });
            syncSwatches();
        }

        const swatches = [...dialog.querySelectorAll('[data-background]')];
        const backgroundInput = form.elements.namedItem('background_color');

        function syncSwatches() {
            const value = backgroundInput.value.toLowerCase();
            swatches.forEach(swatch => swatch.setAttribute('aria-pressed', String(swatch.dataset.background === value)));
        }

        swatches.forEach(swatch => swatch.addEventListener('click', () => {
            if (backgroundInput.value.toLowerCase() === swatch.dataset.background) return;
            backgroundInput.value = swatch.dataset.background;
            backgroundInput.dispatchEvent(new Event('input', { bubbles: true }));
            backgroundInput.dispatchEvent(new Event('change', { bubbles: true }));
        }));
        backgroundInput.addEventListener('input', syncSwatches);

        // Tabs: the last one is remembered; markers flag unsaved changes and server-side errors.
        const tabs = [...dialog.querySelectorAll('[role="tab"]')];
        const tabStorageKey = 'goplan.print.tab';
        const segmentSelectors = { format: '[data-format]', orientation: '[data-orientation]', timescale: '[data-view]' };
        let lastErrors = null;

        function selectTab(tab, focus = false) {
            tabs.forEach(item => {
                const selected = item === tab;
                item.setAttribute('aria-selected', String(selected));
                item.tabIndex = selected ? 0 : -1;
                document.getElementById(item.getAttribute('aria-controls')).hidden = !selected;
            });
            try { window.localStorage.setItem(tabStorageKey, tab.dataset.tab); } catch (_) { /* private mode */ }
            if (focus) tab.focus();
        }

        function tabOf(name) {
            const element = segmentSelectors[name]
                ? dialog.querySelector(segmentSelectors[name]) : form.elements.namedItem(name);
            return element?.closest?.('[role="tabpanel"]')?.id || null;
        }

        function updateTabs() {
            const states = tabStates(fields, settings, saved, lastErrors, tabOf);
            tabs.forEach(tab => {
                const state = states[tab.getAttribute('aria-controls')] || {};
                tab.classList.toggle('is-dirty', Boolean(state.dirty));
                tab.classList.toggle('has-error', Boolean(state.error));
                const note = state.error ? 'réglages refusés' : (state.dirty ? 'modifications non enregistrées' : '');
                tab.title = note ? `${tab.textContent.trim()} : ${note}` : '';
                if (note) tab.setAttribute('aria-description', note);
                else tab.removeAttribute('aria-description');
            });
        }

        tabs.forEach(tab => tab.addEventListener('click', () => selectTab(tab)));
        dialog.querySelector('[role="tablist"]').addEventListener('keydown', event => {
            const index = tabs.indexOf(document.activeElement);
            if (index < 0) return;
            const target = {
                ArrowRight: tabs[(index + 1) % tabs.length],
                ArrowLeft: tabs[(index - 1 + tabs.length) % tabs.length],
                Home: tabs[0],
                End: tabs.at(-1),
            }[event.key];
            if (!target) return;
            event.preventDefault();
            selectTab(target, true);
        });
        let storedTab = null;
        try { storedTab = window.localStorage.getItem(tabStorageKey); } catch (_) { storedTab = null; }
        selectTab(tabs.find(tab => tab.dataset.tab === storedTab) || tabs[0]);

        function readForm() {
            fields.forEach(name => {
                const input = form.elements.namedItem(name);
                if (!input) return;
                if (input.type === 'checkbox') settings[name] = input.checked;
                else if (numberFields.has(name)) settings[name] = input.value === '' ? null : Number(input.value);
                else if (input.type === 'date') settings[name] = input.value || null;
                else settings[name] = input.value;
            });
        }

        const isDirty = () => fields.some(name => (settings[name] ?? null) !== (saved[name] ?? null));

        function updateSaveStatus() {
            const dirty = isDirty();
            saveStatus.dataset.state = dirty ? 'dirty' : (isSaved ? 'saved' : 'default');
            saveStatus.textContent = dirty
                ? 'Modifications non enregistrées : elles ne valent que pour cet aperçu.'
                : (isSaved ? 'Réglages enregistrés pour ce planning.' : 'Réglages par défaut (rien d\'enregistré).');
            saveButton.disabled = !dirty;
            resetButton.disabled = !isSaved;
            updateTabs();
        }

        function showSaveErrors(errors) {
            form.querySelectorAll('[aria-invalid]').forEach(input => input.removeAttribute('aria-invalid'));
            lastErrors = errors;
            updateTabs();
            saveErrors.replaceChildren();
            saveErrors.hidden = !errors;
            if (!errors) return;
            const failing = tabs.find(tab => tab.classList.contains('has-error'));
            if (failing) selectTab(failing);
            const list = document.createElement('ul');
            Object.entries(errors).forEach(([name, messages]) => {
                const input = name === '__all__' ? null : form.elements.namedItem(name);
                if (input && input.setAttribute) input.setAttribute('aria-invalid', 'true');
                const label = input && input.id
                    ? form.querySelector(`label[for="${input.id}"]`)?.textContent
                    : input?.closest?.('label, .print-date-field')?.querySelector('span')?.textContent;
                [].concat(messages).forEach(message => {
                    const item = document.createElement('li');
                    item.textContent = label || (name === '__all__' ? '' : name)
                        ? `${(label || name).trim()} : ${message}` : message;
                    list.appendChild(item);
                });
            });
            saveErrors.appendChild(list);
        }

        async function send(url, withValues) {
            const body = new FormData();
            body.append('csrfmiddlewaretoken', form.elements.namedItem('csrfmiddlewaretoken').value);
            body.append('revision', revision);
            if (withValues) {
                fields.forEach(name => {
                    const value = settings[name];
                    if (typeof value === 'boolean') {
                        if (value) body.append(name, 'on');
                    } else body.append(name, value ?? '');
                });
            }
            saveButton.disabled = true;
            resetButton.disabled = true;
            showSaveErrors(null);
            try {
                const response = await fetch(url, {
                    method: 'POST', body, credentials: 'same-origin',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                let payload = null;
                try { payload = await response.json(); } catch (_) { payload = null; }
                if (!response.ok || !payload || !payload.values) {
                    showSaveErrors(payload?.errors || {
                        __all__: [`Le serveur a refusé l'enregistrement (HTTP ${response.status}). Aucune modification sauvegardée.`],
                    });
                    return;
                }
                saved = { ...payload.values };
                revision = payload.revision;
                isSaved = payload.saved;
                if (!withValues) {
                    settings = { ...payload.values };
                    refreshAll();
                }
            } catch (err) {
                console.error('[GoPlan/Impression] Enregistrement des réglages', err);
                showSaveErrors({ __all__: [`Connexion impossible : ${err.message}. Aucune modification sauvegardée.`] });
            } finally {
                updateSaveStatus();
            }
        }

        function setPrintEnabled(enabled) {
            printButton.disabled = !enabled;
            mainPrintButton.disabled = !enabled;
        }

        function text(parent, value, attributes) {
            const element = svgElement('text', attributes);
            element.textContent = value;
            parent.appendChild(element);
            return element;
        }

        function measure(value, font) {
            context.font = font;
            return context.measureText(value).width;
        }

        function fitText(value, width, font) {
            if (measure(value, font) <= width) return value;
            let result = value;
            while (result.length > 1 && measure(`${result}…`, font) > width) result = result.slice(0, -1);
            return `${result}…`;
        }

        function applyCollapsed() {
            const ids = collapsedIds(printRows, settings.outline_level, settings.respect_collapsed);
            const key = ids.join(',');
            if (key === collapsedKey) return new Set(ids);
            collapsedKey = key;
            source.dispatchEvent(new CustomEvent('goplan:set-collapsed', { detail: ids }));
            return new Set(ids);
        }

        function applyView() {
            if (settings.timescale === sourceView) return;
            source.querySelector(`[data-view="${settings.timescale}"]`).click();
            sourceView = settings.timescale;
        }

        function requestedPeriod() {
            if (settings.period_mode === 'custom') {
                if (!settings.period_start || !settings.period_end || settings.period_end < settings.period_start) {
                    throw new Error("Renseignez une période personnalisée valide, avec une fin après le début.");
                }
                return { start: settings.period_start, end: settings.period_end };
            }
            if (settings.period_mode === 'relative') {
                return relativePeriod(planContext.date_etat, settings.weeks_before, settings.weeks_after);
            }
            return null;
        }

        function makeModel() {
            error.textContent = '';
            setPrintEnabled(false);
            model = null;
            chart.replaceChildren();
            const calendarError = source.querySelector('#gantt-form-errors').textContent.trim();
            const rendererError = source.querySelector('#gantt-error').textContent.trim();
            if (rendererError || calendarError) throw new Error(rendererError || calendarError);
            const collapsed = applyCollapsed();
            const visibleIds = window.GoPlanGantt.visibleTasks(data, collapsed).map(task => task.id);
            const rows = selectRows(printRows, visibleIds, datedIds, settings, collapsed);
            const original = source.querySelector('#gantt-svg');
            const gridRows = [...original.querySelectorAll('.grid-row')];
            if (visibleIds.length && gridRows.length !== visibleIds.length) {
                throw new Error("Le moteur Gantt n'a pas terminé son rendu. Rechargez la page et vérifiez l'accès au CDN Frappe Gantt.");
            }
            const rowHeight = gridRows.length ? Number(gridRows[0].getAttribute('height')) : 35;
            const headerHeight = gridRows.length ? Number(gridRows[0].getAttribute('y')) : 56.5;
            const columnWidth = columnWidths[settings.timescale];
            const dayWidth = columnWidth / daysPerColumn[settings.timescale];
            const originalWidth = Number(original.getAttribute('width')) || 500;
            const reference = original.querySelector('.bar-wrapper');
            const referenceTask = reference && data.tasks.find(task => task.id === reference.dataset.id);
            const referenceX = reference && Number(reference.querySelector('.bar').getAttribute('x'));
            const dateX = value => referenceX + (dayNumber(value) - dayNumber(referenceTask.start)) * dayWidth;
            const period = requestedPeriod();
            let bounds = timelineBounds([...original.querySelectorAll('.bar-wrapper .bar')].map(bar => ({
                x: Number(bar.getAttribute('x')), width: Number(bar.getAttribute('width')),
            })), originalWidth, columnWidth);
            if (period && reference) {
                bounds = periodBounds(period.start, period.end, referenceTask.start, referenceX, dayWidth, originalWidth);
            }
            periodLabel = starts.length || period
                ? `Du ${dateLabel(period ? period.start : fullStart)} au ${dateLabel(period ? period.end : fullEnd)}`
                : 'Aucune période datée';

            // Task table (always the name, then the selected columns), measured with the printed font.
            const font = fontStacks[settings.font_family] || fontStacks.arial;
            const nameFont = bold => `${bold ? 'bold' : 'normal'} ${baseFont}px ${font}`;
            const cellFont = `12px ${font}`;
            const headFont = `bold 11px ${font}`;
            const padding = 8;
            const indent = row => 14 + Math.min(row.level || 0, 10) * 12;
            const label = row => taskLabel(row, settings.col_code) + (row.undated ? ' (sans barre)' : '');
            const active = columns.filter(column => settings[column.field]).map(column => {
                const natural = Math.max(measure(column.label, headFont),
                    ...rows.map(row => measure(cellText(row, column.key), cellFont)));
                return { ...column, natural: Math.ceil(Math.min(column.max || Infinity, natural)) + padding * 2 };
            });
            const naturalName = Math.ceil(Math.max(active.length ? 220 : 320, ...rows.map(row =>
                indent(row) + measure(label(row), nameFont(row.type === 'GROUPE')) + 12)));

            let master = null;
            if (gridRows.length) {
                master = original.cloneNode(true);
                master.removeAttribute('id');
                master.setAttribute('preserveAspectRatio', 'none');
                master.querySelectorAll('[id]').forEach(element => element.removeAttribute('id'));
                master.querySelectorAll('[tabindex]').forEach(element => element.removeAttribute('tabindex'));
                master.querySelectorAll('.gantt-selected').forEach(element => element.classList.remove('gantt-selected'));
                if (settings.show_labels_on_bars) {
                    master.querySelectorAll('.bar-label').forEach(barLabel => {
                        barLabel.classList.remove('big');
                        barLabel.style.display = 'block';
                    });
                }
                if (!settings.show_links) master.querySelectorAll('.gantt-links').forEach(element => element.remove());
                if (!settings.show_nonworking) {
                    master.querySelectorAll('.gantt-calendar-bands').forEach(element => element.remove());
                }
                if (!settings.show_grid) {
                    master.querySelectorAll('.tick, .row-line').forEach(element => element.remove());
                }
                master.querySelectorAll('.grid-row, .grid-background').forEach(element => {
                    element.style.fill = settings.background_color;
                });
                master.querySelectorAll('.bar-wrapper').forEach(wrapper => {
                    const progress = wrapper.querySelector('.bar-progress');
                    if (!progress) return;
                    if (!settings.show_progress) {
                        progress.remove();
                        return;
                    }
                    // CSS filters rasterize SVG progress bars in Chromium's PDF output.
                    const color = wrapper.style.getPropertyValue('--goplan-task-color');
                    if (/^#[0-9a-f]{6}$/i.test(color)) {
                        progress.style.filter = 'none';
                        progress.style.fill = progressColor(color);
                    }
                });
            }

            let statusOffset = null;
            if (settings.show_status_date && planContext.date_etat && reference) {
                const x = dateX(planContext.date_etat) + dayWidth - bounds.start;
                if (x >= 0 && x <= bounds.width) statusOffset = x;
            }

            model = {
                rows, active, naturalName, nameWidth: naturalName, leftWidth: 0, width: 0, headerHeight, rowHeight,
                bounds, master, statusOffset, font, padding, indent, label, nameFont, cellFont, headFont,
            };
            applyColumns(1);

            const printed = new Set(rows.map(row => row.id));
            const linkCount = data.links.filter(link => printed.has(link.predecessor) && printed.has(link.successor)).length;
            document.querySelector('#print-task-count').textContent =
                `${rows.length} tâche(s) · ${linkCount} liaison(s)`;
            document.querySelector('#print-dates').textContent = periodLabel;
            document.querySelector('#ps-range-summary').textContent = {
                full: 'Période complète du planning.',
                custom: `${periodLabel} : les barres sont limitées à cette période.`,
                relative: `${periodLabel} (date d'état ${dateLabel(planContext.date_etat)}).`,
            }[settings.period_mode] || '';
            chart.classList.toggle('hide-labels', !settings.show_labels_on_bars);
            chart.classList.toggle('show-today', settings.show_today_marker);
            // Computed colours need the timeline in the document.
            if (master) chart.appendChild(master);
            buildLegend(master, statusOffset !== null);
            chart.replaceChildren();
            setPrintEnabled(Boolean(rows.length));
        }

        function renderPage(pageRows, firstIndex) {
            const m = model;
            const width = layout.viewWidth;
            const timelineWidth = width - m.leftWidth;
            const stretch = timelineWidth / m.bounds.width;
            const height = m.headerHeight + Math.max(1, pageRows.length) * m.rowHeight + 1;
            const bodyHeight = height - m.headerHeight;
            const output = svgElement('svg', {
                viewBox: `0 0 ${width} ${height}`, preserveAspectRatio: 'none',
                role: 'img', 'aria-label': 'Planning : tâches et diagramme de Gantt',
                'font-family': m.font,
            });
            output.dataset.height = height;
            output.style.setProperty('--goplan-link-color', appearance.values.gantt_couleur_liaison);
            output.appendChild(svgElement('rect', { width, height, fill: settings.background_color }));
            if (m.master) {
                // The calendar header is repeated on every page above the rows of this page.
                [[0, 0, m.headerHeight], [m.headerHeight, m.headerHeight + firstIndex * m.rowHeight, bodyHeight]]
                    .forEach(([y, sourceY, partHeight]) => {
                        const part = m.master.cloneNode(true);
                        Object.entries({
                            x: m.leftWidth, y, width: timelineWidth, height: partHeight,
                            viewBox: `${m.bounds.start} ${sourceY} ${m.bounds.width} ${partHeight}`,
                        }).forEach(([name, value]) => part.setAttribute(name, value));
                        output.appendChild(part);
                    });
            } else {
                output.appendChild(svgElement('rect', {
                    x: m.leftWidth, width: timelineWidth, height: m.headerHeight, fill: '#e7f1f5', stroke: '#a9cad6',
                }));
                text(output, 'Aucune tâche datée', {
                    x: m.leftWidth + 12, y: m.headerHeight / 2,
                    'font-size': 13, fill: '#24485a', 'dominant-baseline': 'middle',
                });
            }

            const datedOnPage = pageRows.filter(row => !row.undated).length;
            if (m.statusOffset !== null && datedOnPage) {
                const statusX = m.leftWidth + m.statusOffset * stretch;
                const marker = svgElement('g', { class: 'print-status-line' });
                marker.appendChild(svgElement('line', {
                    x1: statusX, x2: statusX, y1: m.headerHeight,
                    y2: m.headerHeight + datedOnPage * m.rowHeight,
                    stroke: '#7c3aed', 'stroke-width': 1.5, 'stroke-dasharray': '6 3',
                }));
                output.appendChild(marker);
            }

            output.appendChild(svgElement('rect', {
                width: m.leftWidth, height: m.headerHeight, fill: '#e7f1f5', stroke: '#8eb6c7',
            }));
            const headText = (value, x, end, room) => text(output, fitText(value, room, `bold 11px ${m.font}`), {
                x, y: m.headerHeight / 2, 'dominant-baseline': 'middle', 'text-anchor': end ? 'end' : 'start',
                'font-size': 11, 'font-weight': 'bold', fill: '#376b82',
            });
            headText('TÂCHES', 12, false, m.nameWidth - 20);
            m.active.forEach(column => headText(
                column.label, column.end ? column.x + column.width - m.padding : column.x + m.padding, column.end,
                column.width - m.padding * 2,
            ));
            pageRows.forEach((row, index) => {
                const y = m.headerHeight + index * m.rowHeight;
                output.appendChild(svgElement('rect', {
                    x: 0, y, width: row.undated ? width : m.leftWidth, height: m.rowHeight,
                    fill: settings.background_color,
                    stroke: settings.show_grid ? '#a9cad6' : 'none', 'stroke-width': 0.6,
                }));
                const bold = row.type === 'GROUPE';
                const fullName = m.label(row);
                const name = text(output, fitText(fullName, m.nameWidth - m.indent(row) - 12, m.nameFont(bold)), {
                    x: m.indent(row), y: y + m.rowHeight / 2, 'dominant-baseline': 'middle',
                    fill: row.undated ? '#617786' : '#24485a', 'font-size': baseFont,
                    'font-weight': bold ? 'bold' : 'normal',
                    'font-style': row.undated ? 'italic' : 'normal',
                });
                const title = svgElement('title');
                title.textContent = fullName;
                name.appendChild(title);
                m.active.forEach(column => {
                    const value = fitText(cellText(row, column.key), column.width - m.padding * 2, m.cellFont);
                    text(output, value, {
                        x: column.end ? column.x + column.width - m.padding : column.x + m.padding,
                        y: y + m.rowHeight / 2, 'dominant-baseline': 'middle',
                        'text-anchor': column.end ? 'end' : 'start',
                        fill: '#24485a', 'font-size': 12,
                    });
                });
            });
            m.active.forEach(column => output.appendChild(svgElement('line', {
                x1: column.x, x2: column.x, y1: 0, y2: settings.show_grid ? height : m.headerHeight,
                stroke: '#a9cad6', 'stroke-width': 0.6,
            })));
            output.appendChild(svgElement('line', {
                x1: m.leftWidth, x2: m.leftWidth, y1: 0, y2: height, stroke: '#8eb6c7', 'stroke-width': 1,
            }));
            return output;
        }

        /*
         * The timeline is only widened horizontally (stretch >= 1). Texts, milestones and arrowheads
         * are narrowed back around their anchor so they keep the shape they have on screen.
         */
        function unstretch(master, stretch) {
            const ratio = 1 / stretch;
            const anchor = element => {
                if (element.tagName === 'text') {
                    return [parseFloat(element.getAttribute('x')) || 0, parseFloat(element.getAttribute('y')) || 0];
                }
                if (element.tagName === 'circle') {
                    return [Number(element.getAttribute('cx')), Number(element.getAttribute('cy'))];
                }
                const numbers = (element.getAttribute(element.tagName === 'polygon' ? 'points' : 'd') || '')
                    .match(/-?\d+(?:\.\d+)?/g)?.map(Number) || [];
                if (element.tagName === 'path') return [numbers[2] || 0, numbers[3] || 0];
                const xs = numbers.filter((_, index) => index % 2 === 0);
                const ys = numbers.filter((_, index) => index % 2 === 1);
                return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
            };
            master.querySelectorAll('text, .gantt-diamond, path.gantt-link-arrow:not(.gantt-link-connector)')
                .forEach(element => {
                    if (element.dataset.printTransform === undefined) {
                        element.dataset.printTransform = element.getAttribute('transform') || '';
                    }
                    const base = element.dataset.printTransform;
                    if (ratio > 0.999) {
                        if (base) element.setAttribute('transform', base);
                        else element.removeAttribute('transform');
                        return;
                    }
                    const [x, y] = anchor(element);
                    element.setAttribute('transform',
                        `translate(${x} ${y}) scale(${ratio} 1) translate(${-x} ${-y}) ${base}`.trim());
                });
        }

        function paperLabel(index, count) {
            return `${settings.format} ${settings.orientation === 'portrait' ? 'portrait' : 'paysage'} · ${index} / ${count}`;
        }

        function applyColumns(scale) {
            const result = columnLayout(model.naturalName, model.active.map(column => column.natural),
                settings.name_max_width, settings.column_max_width, scale);
            model.nameWidth = result.nameWidth;
            model.active.forEach((column, index) => Object.assign(column, result.columns[index]));
            model.leftWidth = result.leftWidth;
            model.width = result.leftWidth + model.bounds.width;
        }

        function layoutPages() {
            pagesHost.querySelectorAll('.print-sheet-copy').forEach(copy => copy.remove());
            chart.replaceChildren();
            layout = null;
            document.querySelector('#print-paper-label').textContent = paperLabel(1, 1);
            if (!model) return;
            // Millimetre column limits depend on the scale, which depends on the width: settle in a few passes.
            let scale = 1;
            for (let pass = 0; pass < 6; pass += 1) {
                applyColumns(scale);
                layout = pageLayout({
                    width: model.width, headerHeight: model.headerHeight, rowHeight: model.rowHeight,
                    rowCount: model.rows.length, chartWidth: chart.clientWidth, chartHeight: chart.clientHeight,
                    pages: settings.vertical_pages, minPoints: settings.min_font_size,
                    maxPoints: rowFontPoints(settings.max_row_height),
                });
                if (Math.abs(layout.scale - scale) < 1e-4 || !(settings.name_max_width || settings.column_max_width)) break;
                scale = layout.scale;
            }
            if (model.master) unstretch(model.master, (layout.viewWidth - model.leftWidth) / model.bounds.width);
            const pages = [];
            for (let index = 0; index < layout.pages; index += 1) {
                const first = index * layout.rowsPerPage;
                const page = renderPage(model.rows.slice(first, first + layout.rowsPerPage), first);
                page.style.height = `${Number(page.dataset.height) * layout.scale}px`;
                pages.push(page);
            }
            chart.appendChild(pages[0] || renderPage([], 0));
            document.querySelector('#print-paper-label').textContent = paperLabel(1, layout.pages);
            pages.slice(1).forEach((page, offset) => {
                const copy = sheet.cloneNode(true);
                copy.removeAttribute('id');
                copy.classList.add('print-sheet-copy');
                copy.querySelectorAll('[id]').forEach(element => element.removeAttribute('id'));
                copy.querySelector('.print-chart').replaceChildren(page);
                copy.querySelector('.print-paper-label').textContent = paperLabel(offset + 2, layout.pages);
                pagesHost.appendChild(copy);
            });
        }

        function buildLegend(timeline, statusLine) {
            const legend = document.querySelector('#print-legend');
            legend.replaceChildren();
            const items = [];
            const find = selector => (timeline ? timeline.querySelector(selector) : null);
            const style = element => getComputedStyle(element);
            const add = (label, shape, attributes) => items.push({ label, shape, attributes });
            const plainBar = timeline && [...timeline.querySelectorAll('.bar-wrapper')]
                .find(wrapper => !wrapper.style.getPropertyValue('--goplan-task-color')
                    && !wrapper.querySelector('.gantt-summary, .gantt-diamond'));
            if (plainBar) add('Tâche', 'rect', { fill: style(plainBar.querySelector('.bar')).fill });
            const summary = find('.gantt-summary');
            if (summary) add('Groupe', 'rect', { fill: style(summary).fill, height: 5, y: 2.5 });
            const diamond = find('.gantt-diamond');
            if (diamond) add('Jalon', 'diamond', { fill: style(diamond).fill });
            const progress = [...(timeline ? timeline.querySelectorAll('.bar-progress') : [])]
                .find(element => Number(element.getAttribute('width')) > 0);
            if (progress) add('Avancement', 'rect', { fill: style(progress).fill });
            const connector = settings.show_links && find('.gantt-link-connector');
            if (connector) add('Liaison', 'line', { stroke: style(connector).stroke });
            const band = settings.show_nonworking && find('.gantt-calendar-bands rect');
            if (band) {
                const opacity = Number(style(band).opacity) * Number(style(band.parentNode).opacity) *
                    Number(style(band).fillOpacity || 1);
                add('Jour non travaillé', 'rect', { fill: style(band).fill, 'fill-opacity': opacity });
            }
            const today = settings.show_today_marker && find('.today-highlight');
            if (today) add("Aujourd'hui", 'rect', { fill: style(today).fill, 'fill-opacity': style(today).fillOpacity });
            if (statusLine) add("Date d'état", 'line', { stroke: '#7c3aed', 'stroke-dasharray': '3 2' });
            items.forEach(item => {
                const entry = document.createElement('span');
                entry.className = 'print-legend-item';
                const swatch = svgElement('svg', { width: 16, height: 10, viewBox: '0 0 16 10', 'aria-hidden': 'true' });
                if (item.shape === 'line') {
                    swatch.appendChild(svgElement('line', { x1: 0, x2: 16, y1: 5, y2: 5, 'stroke-width': 1.5, ...item.attributes }));
                } else if (item.shape === 'diamond') {
                    swatch.appendChild(svgElement('polygon', { points: '8,0 13,5 8,10 3,5', ...item.attributes }));
                } else {
                    swatch.appendChild(svgElement('rect', { x: 0, y: 1, width: 16, height: 8, rx: 1.5, ...item.attributes }));
                }
                const name = document.createElement('span');
                name.textContent = item.label;
                entry.append(swatch, name);
                legend.appendChild(entry);
            });
            legend.hidden = !settings.show_legend || !items.length;
        }

        function textValues() {
            const [width, height] = papers[settings.format][settings.orientation];
            return {
                plan: planContext.plan,
                description: planContext.description,
                date_impression: printDate,
                date_etat: dateLabel(planContext.date_etat),
                periode: periodLabel,
                format: `${settings.format} ${settings.orientation === 'portrait' ? 'portrait' : 'paysage'} (${width} × ${height} mm)`,
                calendrier: planContext.calendrier,
            };
        }

        function updateTexts() {
            const values = textValues();
            textFields.forEach(([field, id]) => {
                const target = document.getElementById(id);
                target.textContent = substituteVariables(settings[field], values);
                target.hidden = !target.textContent.trim();
            });
            const header = sheet.querySelector('.print-document-header');
            header.classList.toggle('has-center', !document.getElementById('print-header-center').hidden);
            const typography = {
                '--print-font': fontStacks[settings.font_family] || fontStacks.arial,
                '--print-title-size': `${settings.title_font_size || 15}pt`,
                '--print-title-weight': settings.title_bold ? '700' : '400',
                '--print-title-color': /^#[0-9a-f]{6}$/i.test(settings.title_color) ? settings.title_color : '#19394a',
                '--print-subtitle-size': `${settings.subtitle_font_size || 9}pt`,
                '--print-center-size': `${settings.header_center_font_size || 11}pt`,
                '--print-center-weight': settings.header_center_bold ? '700' : '400',
                '--print-footer-size': `${settings.footer_font_size || 8}pt`,
            };
            Object.entries(typography).forEach(([name, value]) => sheet.style.setProperty(name, value));
            const printedOn = document.querySelector('#print-printed-on');
            printedOn.textContent = `Imprimé le ${printDate}`;
            printedOn.hidden = !settings.show_print_date;
            const statusDate = document.querySelector('#print-status-date');
            statusDate.textContent = `Date d'état : ${values.date_etat}`;
            statusDate.hidden = !settings.show_status_date || !planContext.date_etat;
            document.querySelector('#print-footer').hidden = !settings.show_footer;
            document.querySelector('#print-warnings').hidden = !settings.show_warnings;
        }

        function applyLayout() {
            const margin = value => `${Number.isFinite(value) ? Math.min(30, Math.max(0, value)) : 8}mm`;
            ['top', 'right', 'bottom', 'left'].forEach(side => {
                sheet.style.setProperty(`--print-margin-${side}`, margin(settings[`margin_${side}`]));
            });
            sheet.classList.toggle('is-centered', Boolean(settings.center_vertically));
            form.querySelectorAll('[data-period]').forEach(element => {
                element.hidden = element.dataset.period !== settings.period_mode;
            });
        }

        let suggestedPages = null;

        function reportFit() {
            suggestedPages = null;
            fitAlert.hidden = true;
            const rowFont = document.querySelector('#ps-row-font');
            if (rowFont) {
                rowFont.textContent = `${settings.max_row_height} mm ≈ `
                    + `${rowFontPoints(settings.max_row_height).toFixed(1).replace('.', ',')} pt`;
            }
            if (!layout) return;
            const points = layout.fontPoints.toFixed(1).replace('.', ',');
            const minimum = settings.min_font_size;
            const sheets = `${layout.pages} feuille${layout.pages > 1 ? 's' : ''} ${settings.format} ${settings.orientation === 'portrait' ? 'portrait' : 'paysage'}`;
            let message = `${sheets} · texte des tâches : ${points} pt (minimum ${minimum} pt)`
                + ` · jusqu'à ${layout.rowsPerPage} lignes par feuille.`;
            if (layout.pages < layout.requestedPages) {
                message += ` ${layout.requestedPages} pages demandées : ${layout.pages} suffisent, pages remplies en hauteur.`;
            }
            let warning = '';
            if (layout.fontPoints < minimum - 0.05) {
                const pagesHelp = layout.neededPages > layout.pages && layout.neededPages <= maxAutoPages;
                if (pagesHelp) suggestedPages = layout.neededPages;
                if (layout.widthLimited) {
                    const widthPoints = layout.widthPoints.toFixed(1).replace('.', ',');
                    warning = `Texte des tâches à ${points} pt, sous le minimum lisible de ${minimum} pt. `
                        + `La largeur le limite à ${widthPoints} pt : choisissez un papier plus grand, l'échelle Mois, `
                        + 'une période plus courte ou moins de colonnes'
                        + (pagesHelp ? `, ou imprimez sur ${suggestedPages} pages en hauteur pour atteindre ${widthPoints} pt.` : '.');
                } else if (layout.neededPages > maxAutoPages) {
                    warning = `Texte des tâches à ${points} pt (minimum ${minimum} pt) même sur ${maxAutoPages} pages : `
                        + 'choisissez un papier plus grand ou un niveau hiérarchique.';
                } else {
                    warning = `Texte des tâches à ${points} pt, sous le minimum lisible de ${minimum} pt. `
                        + `Pour le respecter, imprimez sur ${suggestedPages} pages en hauteur.`;
                }
                message = `Attention : ${warning}`;
            }
            status.textContent = message;
            fitAlertText.textContent = warning;
            fitAlertButton.hidden = !suggestedPages;
            fitAlertButton.textContent = suggestedPages ? `Ajuster à ${suggestedPages} pages` : '';
            fitAlert.hidden = !warning;
        }

        // Header heights depend on the texts: lay pages out again whenever texts or paper change.
        function render() {
            updateTexts();
            try {
                layoutPages();
            } catch (err) {
                console.error('[GoPlan/Impression]', err);
                error.textContent = `Aperçu indisponible : ${err.message}`;
                layout = null;
                setPrintEnabled(false);
            }
            reportFit();
            fitScreen();
        }

        function setPaper() {
            const [width, height] = papers[settings.format][settings.orientation];
            document.body.style.setProperty('--paper-width', `${width}mm`);
            document.body.style.setProperty('--paper-height', `${height}mm`);
            document.querySelector('#print-page-size').textContent = `@page { size: ${width}mm ${height}mm; margin: 0; }`;
        }

        function updatePaper() {
            setPaper();
            render();
        }

        function fitScreen() {
            const style = getComputedStyle(previewStage);
            const available = previewStage.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
            const result = previewScale(sheet.offsetWidth, available, requestedScale);
            fitScale = result.fit;
            screenScale = result.scale;
            pagesHost.style.transform = `scale(${screenScale})`;
            stage.style.width = `${pagesHost.offsetWidth * screenScale}px`;
            stage.style.height = `${pagesHost.offsetHeight * screenScale}px`;
            zoomInput.min = Math.floor(fitScale * 100);
            zoomInput.value = Math.round(screenScale * 100);
            zoomLabel.textContent = `${Math.round(screenScale * 100)} %`;
            zoomInput.setAttribute('aria-valuetext', zoomLabel.textContent);
            zoomOut.disabled = screenScale <= fitScale + 0.001;
            zoomIn.disabled = screenScale >= 1.099;
            pagesHost.classList.toggle('is-max-zoom', zoomIn.disabled);
        }

        function zoomTo(value, anchor) {
            const rect = pagesHost.getBoundingClientRect();
            const point = anchor || {
                x: previewStage.getBoundingClientRect().left + previewStage.clientWidth / 2,
                y: previewStage.getBoundingClientRect().top + previewStage.clientHeight / 2,
            };
            const x = (point.x - rect.left) / screenScale;
            const y = (point.y - rect.top) / screenScale;
            requestedScale = value;
            fitScreen();
            const next = pagesHost.getBoundingClientRect();
            previewStage.scrollLeft += next.left + x * screenScale - point.x;
            previewStage.scrollTop += next.top + y * screenScale - point.y;
        }

        function build() {
            try {
                makeModel();
            } catch (err) {
                console.error('[GoPlan/Impression]', err);
                error.textContent = `Aperçu indisponible : ${err.message}`;
                model = null;
                setPrintEnabled(false);
            }
            render();
        }

        function syncSegments() {
            for (const [key, field] of [['format', 'format'], ['orientation', 'orientation'], ['view', 'timescale']]) {
                dialog.querySelectorAll(`[data-${key}]`).forEach(button => {
                    button.setAttribute('aria-pressed', String(button.dataset[key] === settings[field]));
                });
            }
        }

        function refreshAll() {
            writeForm();
            syncSegments();
            applyLayout();
            applyView();
            setPaper();
            build();
            updateSaveStatus();
        }

        zoomInput.addEventListener('input', () => zoomTo(Number(zoomInput.value) / 100));
        zoomIn.addEventListener('click', () => zoomTo(screenScale + 0.1));
        zoomOut.addEventListener('click', () => zoomTo(screenScale - 0.1));
        document.querySelector('#print-zoom-fit').addEventListener('click', () => {
            requestedScale = null;
            fitScreen();
            previewStage.scrollTo(0, 0);
        });
        pagesHost.addEventListener('click', event => {
            if (window.getSelection().toString()) return;
            zoomTo(screenScale >= 1.099 ? null : screenScale + 0.25, { x: event.clientX, y: event.clientY });
        });
        fitAlertButton.addEventListener('click', () => {
            if (!suggestedPages) return;
            settings.vertical_pages = suggestedPages;
            writeForm();
            render();
            updateSaveStatus();
        });

        for (const [key, field] of [['format', 'format'], ['orientation', 'orientation'], ['view', 'timescale']]) {
            dialog.querySelectorAll(`[data-${key}]`).forEach(button => button.addEventListener('click', () => {
                settings[field] = button.dataset[key];
                syncSegments();
                if (key === 'view') {
                    applyView();
                    build();
                } else updatePaper();
                updateSaveStatus();
            }));
        }
        const isText = target => textFields.some(([field]) => field === target.name);
        form.addEventListener('input', event => {
            event.target.removeAttribute('aria-invalid');
            if (lastErrors && Object.hasOwn(lastErrors, event.target.name)) {
                lastErrors = { ...lastErrors };
                delete lastErrors[event.target.name];
                updateTabs();
            }
        });
        form.addEventListener('input', event => {
            if (!isText(event.target)) return;
            readForm();
            render();
            updateSaveStatus();
        });
        form.addEventListener('change', event => {
            if (isText(event.target)) return;
            if (event.target.name === 'period_mode' && event.target.value === 'custom'
                && !startInput.value && !endInput.value) {
                startInput.value = fullStart;
                endInput.value = fullEnd;
            }
            readForm();
            applyLayout();
            build();
            updateSaveStatus();
        });
        form.addEventListener('submit', event => event.preventDefault());
        saveButton.addEventListener('click', () => send(form.dataset.saveUrl, true));
        resetButton.addEventListener('click', () => {
            if (window.confirm("Supprimer les réglages d'impression enregistrés pour ce planning et revenir aux réglages par défaut ?")) {
                send(form.dataset.resetUrl, false);
            }
        });

        const openSettings = document.querySelector('#print-open-settings');
        openSettings.addEventListener('click', () => {
            if (!dialog.open) dialog.show();
            document.querySelector('#print-close-settings').focus();
        });
        function closeSettings() {
            dialog.close();
            openSettings.focus();
        }
        ['print-close-settings', 'print-done-settings'].forEach(id =>
            document.getElementById(id).addEventListener('click', closeSettings));
        dialog.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                event.preventDefault();
                closeSettings();
            }
        });
        [printButton, mainPrintButton].forEach(button => button.addEventListener('click', () => {
            if (layout && !button.disabled) window.print();
        }));
        window.addEventListener('beforeprint', updatePaper);
        window.addEventListener('resize', fitScreen);
        refreshAll();
        document.fonts.ready.then(build);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
    else initialize();
})();
