/* static/projets/js/rapports-form.js */
(function () {
    'use strict';

    if (window.__rapportFormInitialized) return;
    window.__rapportFormInitialized = true;

    /* ═══════════════════════════════════════════════════════════
       UPLOAD DE DOCUMENT
       ═══════════════════════════════════════════════════════════ */
    function initUpload() {
        const fileInput = document.getElementById('rapportFileInput');
        const cameraInput = document.getElementById('rapportCameraInput');
        const fileInfo = document.getElementById('rapportFileInfo');
        const fileName = document.getElementById('rapportFileName');
        const fileSize = document.getElementById('rapportFileSize');

        if (!fileInput || !fileInfo || fileInput.dataset.initialized === 'true') return;

        fileInput.addEventListener('change', function () {
            if (cameraInput) cameraInput.value = '';
            if (this.files.length > 0) handleFileSelection(this.files);
        });
        cameraInput?.addEventListener('change', function () {
            fileInput.value = '';
            if (this.files.length > 0) handleFileSelection(this.files);
        });

        function clearFile() {
            fileInput.value = '';
            if (cameraInput) cameraInput.value = '';
            fileInfo.classList.add('hidden');
        }

        function handleFileSelection(files) {
            const selection = Array.from(files);
            const validExt = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.gif'];
            for (const file of selection) {
                if (file.size > 10 * 1024 * 1024) {
                    showWarningMessage('Un fichier est trop volumineux (max 10 Mo).');
                    clearFile();
                    return;
                }
                const ext = '.' + file.name.split('.').pop().toLowerCase();
                if (!validExt.includes(ext)) {
                    showWarningMessage('Type de fichier non supporté.');
                    clearFile();
                    return;
                }
            }
            fileName.textContent = selection.length === 1
                ? selection[0].name
                : `${selection.length} fichiers sélectionnés`;
            const total = selection.reduce((sum, file) => sum + file.size, 0);
            fileSize.textContent = `(${(total / 1024 / 1024).toFixed(2)} Mo au total)`;
            fileInfo.classList.remove('hidden');
        }

        window.removeRapportFile = clearFile;

        fileInput.dataset.initialized = 'true';
    }

    /* ═══════════════════════════════════════════════════════════
       CORRECTION DES DATES (formats FR → ISO)
       ═══════════════════════════════════════════════════════════ */
    function fixDateInputs() {
        document.querySelectorAll('input[type="date"]').forEach((input) => {
            const v = input.value;
            if (!v) return;
            if (v.match(/^\d{2}\/\d{2}\/\d{4}$/) || v.match(/^\d{2}-\d{2}-\d{4}$/) || v.match(/^\d{2}\.\d{2}\.\d{4}$/)) {
                const sep = v.includes('/') ? '/' : (v.includes('-') ? '-' : '.');
                const [d, m, y] = v.split(sep);
                input.value = `${y}-${m.padStart(2, '0')}-${d.padStart(2, '0')}`;
            }
        });
    }

    /* ═══════════════════════════════════════════════════════════
       DÉPENSES (dynamique par catégorie)
       ═══════════════════════════════════════════════════════════ */
    function initDepenses() {
        const root = document.getElementById('depenses-categories');
        if (!root) return;
        const totalForms = document.getElementById(root.dataset.totalFormsId);
        if (!totalForms) return;

        const fmt = (n) => n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' DH';

        const nombre = (valeur) => Number.parseFloat(
            String(valeur || '').replace(/\s/g, '').replace(',', '.'),
        ) || 0;

        function ligneMontant(row) {
            const q = nombre(row.querySelector('input[name$="-quantite"]')?.value);
            const p = nombre(row.querySelector('input[name$="-prix_unitaire"]')?.value);
            return q * p;
        }

        function updateCount(cat) {
            const tbody = document.getElementById('depense-tbody-' + cat);
            const countEl = document.querySelector(`.depense-count[data-categorie="${cat}"]`);
            const totalEl = document.querySelector(`.depense-total[data-categorie="${cat}"]`);
            if (!tbody) return;
            const visible = Array.from(tbody.querySelectorAll('tr')).filter(r => r.style.display !== 'none');
            if (countEl) countEl.textContent = visible.length;
            if (totalEl) totalEl.textContent = fmt(visible.reduce((s, r) => s + ligneMontant(r), 0));
        }

        function attachRow(row, cat) {
            // Référentiel
            const select = row.querySelector('.depense-ref-select');
            if (select && !select.dataset.bound) {
                select.dataset.bound = 'true';
                select.addEventListener('change', function () {
                    const opt = select.options[select.selectedIndex];
                    const d = row.querySelector('input[name$="-designation"]');
                    const u = row.querySelector('input[name$="-unite"]');
                    const p = row.querySelector('input[name$="-prix_unitaire"]');
                    if (d) d.value = opt ? opt.value : '';
                    if (u) u.value = opt && opt.value ? (opt.dataset.unite || '') : '';
                    if (p) p.value = opt && opt.value ? (opt.dataset.prix || '') : '';
                    const m = row.querySelector('.depense-montant');
                    if (m) m.textContent = fmt(ligneMontant(row));
                    updateCount(cat);
                });
            }

            // Inputs quantité/prix
            ['input[name$="-quantite"]', 'input[name$="-prix_unitaire"]'].forEach(sel => {
                const input = row.querySelector(sel);
                if (input && !input.dataset.bound) {
                    input.dataset.bound = 'true';
                    input.addEventListener('input', () => {
                        const m = row.querySelector('.depense-montant');
                        if (m) m.textContent = fmt(ligneMontant(row));
                        updateCount(cat);
                    });
                }
            });
            // Suppression
            const trigger = row.querySelector('.depense-delete-trigger');
            if (trigger && !trigger.dataset.bound) {
                trigger.dataset.bound = 'true';
                trigger.addEventListener('click', (e) => {
                    e.preventDefault();
                    const cb = row.querySelector('input[name$="-DELETE"]');
                    if (cb) { cb.checked = true; row.style.display = 'none'; }
                    else row.remove();
                    updateCount(cat);
                });
            }
        }

        function addRow(cat) {
            const tpl = document.getElementById('depense-empty-form-template-' + cat);
            const tbody = document.getElementById('depense-tbody-' + cat);
            if (!tpl || !tbody) return;
            const idx = parseInt(totalForms.value, 10);
            const html = tpl.innerHTML.replace(/__prefix__/g, idx);
            const wrapper = document.createElement('tbody');
            wrapper.innerHTML = html;
            const row = wrapper.querySelector('tr');
            tbody.appendChild(row);
            totalForms.value = idx + 1;
            attachRow(row, cat);
            updateCount(cat);
        }

        document.querySelectorAll('tbody[id^="depense-tbody-"]').forEach(tbody => {
            const cat = tbody.id.replace('depense-tbody-', '');
            tbody.querySelectorAll('tr').forEach(r => attachRow(r, cat));
            updateCount(cat);
        });

        document.querySelectorAll('.depense-add-btn').forEach(btn => {
            if (btn.dataset.bound) return;
            btn.dataset.bound = 'true';
            btn.addEventListener('click', () => addRow(btn.dataset.categorie));
        });

        // Toggle catégories
        document.querySelectorAll('.categorie-toggle').forEach(btn => {
            if (btn.dataset.bound) return;
            btn.dataset.bound = 'true';
            btn.addEventListener('click', () => {
                const target = document.getElementById(btn.dataset.target);
                if (!target) return;
                target.classList.toggle('hidden');
                btn.querySelector('.toggle-icon')?.classList.toggle('rotate-90');
            });
        });
    }

    function initTravaux() {
        const container = document.getElementById('travaux-container');
        if (!container) return;
        const totalForms = document.getElementById(container.dataset.totalFormsId);
        const template = document.getElementById('travail-empty-form-template');
        const tbody = document.getElementById('travaux-tbody');
        const addButton = container.querySelector('.travaux-add-btn');
        const countEl = container.querySelector('.travaux-count');
        if (!totalForms || !template || !tbody || !addButton) return;

        function updateCount() {
            if (!countEl) return;
            const visible = Array.from(tbody.querySelectorAll('tr'))
                .filter(r => !r.hidden && r.style.display !== 'none');
            countEl.textContent = visible.length;
        }

        function syncOrder() {
            Array.from(tbody.querySelectorAll('tr')).forEach((row, index) => {
                const ordre = row.querySelector('input[name$="-ordre"]');
                if (ordre) ordre.value = index;
            });
        }

        function bindRow(row) {
            const remove = row.querySelector('.travail-delete-btn');
            if (!remove || remove.dataset.bound) return;
            remove.dataset.bound = 'true';
            remove.addEventListener('click', () => {
                const deleteField = row.querySelector('input[name$="-DELETE"]');
                if (deleteField) {
                    deleteField.checked = true;
                    row.hidden = true;
                } else {
                    row.remove();
                }
                syncOrder();
                updateCount();
            });
        }

        function addRow() {
            const index = Number.parseInt(totalForms.value, 10);
            const holder = document.createElement('tbody');
            holder.innerHTML = template.innerHTML.replace(/__prefix__/g, String(index));
            const row = holder.querySelector('tr');
            if (!row) return;
            tbody.appendChild(row);
            totalForms.value = String(index + 1);
            bindRow(row);
            syncOrder();
            updateCount();
            row.querySelector('input:not([type="hidden"]), textarea, select')?.focus();
        }

        tbody.querySelectorAll('tr').forEach(bindRow);
        if (!addButton.dataset.bound) {
            addButton.dataset.bound = 'true';
            addButton.addEventListener('click', addRow);
        }
        container.addTravailRow = addRow;

        // Toggle accordéon
        const toggleBtn = container.querySelector('.categorie-toggle');
        if (toggleBtn && !toggleBtn.dataset.bound) {
            toggleBtn.dataset.bound = 'true';
            toggleBtn.addEventListener('click', () => {
                const target = document.getElementById(toggleBtn.dataset.target);
                if (!target) return;
                target.classList.toggle('hidden');
                toggleBtn.querySelector('.toggle-icon')?.classList.toggle('rotate-90');
            });
        }

        syncOrder();
        updateCount();
    }

    function initRapportGrid() {
        if (window.__rapportGridInitialized) return;
        window.__rapportGridInitialized = true;
        const rootSelector = '#depenses-categories, #travaux-container';
        const fieldSelector = (
            'input:not([type="hidden"]):not([type="file"]):not([type="checkbox"]),'
            + ' select, textarea'
        );

        function visibleFields(row) {
            return Array.from(row.querySelectorAll(fieldSelector)).filter(
                field => !field.disabled && field.offsetParent !== null,
            );
        }

        function focusField(field) {
            if (!field) return false;
            field.focus();
            if (typeof field.select === 'function') field.select();
            return true;
        }

        function visibleRows(table) {
            return Array.from(table.querySelectorAll('tbody tr')).filter(
                row => !row.hidden && row.style.display !== 'none'
                    && visibleFields(row).length,
            );
        }

        function moveVertical(field, offset) {
            const row = field.closest('tr');
            const table = field.closest('table');
            if (!row || !table) return;
            const rows = visibleRows(table);
            const rowIndex = rows.indexOf(row);
            const columnIndex = visibleFields(row).indexOf(field);
            const target = rows[rowIndex + offset];
            if (!target) return;
            const fields = visibleFields(target);
            focusField(fields[Math.min(columnIndex, fields.length - 1)]);
        }

        function caretAtBoundary(field, direction) {
            if (!(field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement)) {
                return true;
            }
            const start = field.selectionStart;
            const end = field.selectionEnd;
            if (start === null || end === null || start !== end) return false;
            return direction < 0 ? start === 0 : end === field.value.length;
        }

        function moveHorizontal(field, offset) {
            const fields = visibleFields(field.closest('tr'));
            focusField(fields[fields.indexOf(field) + offset]);
        }

        function ensureNextRow(row) {
            if (row.nextElementSibling && !row.nextElementSibling.hidden) {
                return row.nextElementSibling;
            }
            const category = row.closest('[data-depense-categorie]');
            if (category) {
                category.querySelector('.depense-add-btn')?.click();
            } else {
                row.closest('#travaux-container')
                    ?.querySelector('.travaux-add-btn')?.click();
            }
            const next = row.nextElementSibling;
            return next && !next.hidden ? next : null;
        }

        function setValue(field, value) {
            field.value = value;
            field.dispatchEvent(new Event('input', {bubbles: true}));
            field.dispatchEvent(new Event('change', {bubbles: true}));
        }

        document.addEventListener('keydown', (event) => {
            const field = event.target;
            if (
                !(field instanceof HTMLElement)
                || !field.matches(fieldSelector)
                || !field.closest(rootSelector)
                || event.altKey
                || event.metaKey
            ) return;
            if (event.key === 'Enter') {
                event.preventDefault();
                moveVertical(field, event.shiftKey ? -1 : 1);
            } else if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
                event.preventDefault();
                moveVertical(field, event.key === 'ArrowUp' ? -1 : 1);
            } else if (
                (event.key === 'ArrowLeft' || event.key === 'ArrowRight')
                && caretAtBoundary(field, event.key === 'ArrowLeft' ? -1 : 1)
            ) {
                event.preventDefault();
                moveHorizontal(field, event.key === 'ArrowLeft' ? -1 : 1);
            }
        });

        document.addEventListener('paste', (event) => {
            const field = event.target;
            const text = event.clipboardData?.getData('text/plain');
            if (
                !(field instanceof HTMLElement)
                || !field.matches(fieldSelector)
                || !field.closest(rootSelector)
                || !text
                || (!text.includes('\t') && !text.includes('\n'))
            ) return;
            event.preventDefault();
            let row = field.closest('tr');
            const startColumn = visibleFields(row).indexOf(field);
            const matrix = text
                .replace(/\r\n/g, '\n')
                .replace(/\r/g, '\n')
                .replace(/\n$/, '')
                .split('\n')
                .map(line => line.split('\t'));
            let lastField = field;
            matrix.forEach((values, rowOffset) => {
                if (rowOffset > 0) row = ensureNextRow(row);
                if (!row) return;
                const fields = visibleFields(row);
                values.forEach((value, columnOffset) => {
                    const target = fields[startColumn + columnOffset];
                    if (!target) return;
                    setValue(target, value);
                    lastField = target;
                });
            });
            focusField(lastField);
        });
    }

    /* ═══════════════════════════════════════════════════════════
    DOCUMENTS JOINTS — Toggle accordéon
    ═══════════════════════════════════════════════════════════ */
    function initDocumentsToggle() {
        const container = document.getElementById('documents-container');
        if (!container) return;

        const toggleBtn = container.querySelector('.categorie-toggle');
        if (toggleBtn && !toggleBtn.dataset.bound) {
            toggleBtn.dataset.bound = 'true';
            toggleBtn.addEventListener('click', () => {
                const target = document.getElementById(toggleBtn.dataset.target);
                if (!target) return;
                target.classList.toggle('hidden');
                toggleBtn.querySelector('.toggle-icon')?.classList.toggle('rotate-90');
            });
        }

        // Met à jour le compteur quand un fichier est sélectionné
        const countEl = container.querySelector('.documents-count');
        const fileInput = document.getElementById('rapportFileInput');
        const cameraInput = document.getElementById('rapportCameraInput');
        const existing = container.querySelectorAll('.rapport-existing-document').length;

        function refreshCount() {
            if (!countEl) return;
            const files = (fileInput?.files?.length || 0) + (cameraInput?.files?.length || 0);
            countEl.textContent = existing + files;
        }

        if (fileInput && !fileInput.dataset.boundCount) {
            fileInput.dataset.boundCount = 'true';
            fileInput.addEventListener('change', refreshCount);
        }
        if (cameraInput && !cameraInput.dataset.boundCount) {
            cameraInput.dataset.boundCount = 'true';
            cameraInput.addEventListener('change', refreshCount);
        }
    }

    /* ═══════════════════════════════════════════════════════════
       STOCKS
       ═══════════════════════════════════════════════════════════ */
    function initStocks() {
        const container = document.getElementById('stocks-container');
        if (!container) return;
        const totalForms = document.getElementById(container.dataset.totalFormsId);
        const tpl = document.getElementById('stock-empty-form-template');
        const addBtn = document.getElementById('stock-add-btn');
        const tbody = document.getElementById('stock-tbody');
        const countEl = document.querySelector('.stock-count');

        if (!totalForms || !tpl || !addBtn || !tbody) return;

        function updateCount() {
            const visible = Array.from(tbody.querySelectorAll('tr')).filter(r => r.style.display !== 'none');
            if (countEl) countEl.textContent = visible.length;
        }

        function attachRow(row) {
            const trigger = row.querySelector('.stock-delete-trigger');
            if (!trigger || trigger.dataset.bound) return;
            trigger.dataset.bound = 'true';
            trigger.addEventListener('click', (e) => {
                e.preventDefault();
                const cb = row.querySelector('input[name$="-DELETE"]');
                if (cb) { cb.checked = true; row.style.display = 'none'; }
                else row.remove();
                updateCount();
            });
        }

        function addRow() {
            const idx = parseInt(totalForms.value, 10);
            const html = tpl.innerHTML.replace(/__prefix__/g, idx);
            const wrapper = document.createElement('tbody');
            wrapper.innerHTML = html;
            const row = wrapper.querySelector('tr');
            tbody.appendChild(row);
            totalForms.value = idx + 1;
            attachRow(row);
            updateCount();
        }

        container.addStockRow = addRow;
        tbody.querySelectorAll('tr').forEach(attachRow);

        const toggleBtn = container.querySelector('.categorie-toggle');
        if (toggleBtn && !toggleBtn.dataset.bound) {
            toggleBtn.dataset.bound = 'true';
            toggleBtn.addEventListener('click', () => {
                const target = document.getElementById(toggleBtn.dataset.target);
                if (!target) return;
                target.classList.toggle('hidden');
                toggleBtn.querySelector('.toggle-icon')?.classList.toggle('rotate-90');
            });
        }
    }

    document.addEventListener('click', (event) => {
        const addButton = event.target.closest('#stock-add-btn');
        if (!addButton) return;
        event.preventDefault();
        initStocks();
        document.getElementById('stocks-container')?.addStockRow?.();
    });

    /* ═══════════════════════════════════════════════════════════
       INIT
       ═══════════════════════════════════════════════════════════ */
    function initAll() {
        initUpload();
        fixDateInputs();
        initDepenses();
        initTravaux();
        initRapportGrid();
        initStocks();
        initDocumentsToggle();   // ← ajout
    }

    document.addEventListener('DOMContentLoaded', initAll);
    document.addEventListener('rapportFormLoaded', () => setTimeout(initAll, 100));

    window.reinitRapportForm = initAll;

})();