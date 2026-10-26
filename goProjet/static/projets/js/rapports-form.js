/* static/projets/js/rapports-form.js */
(function () {
    'use strict';

    if (window.__rapportFormInitialized) return;
    window.__rapportFormInitialized = true;

    /* ═══════════════════════════════════════════════════════════
       UPLOAD DE DOCUMENT
       ═══════════════════════════════════════════════════════════ */
    function initUpload() {
        const dropZone = document.getElementById('rapportDropZone');
        const fileInput = document.getElementById('rapportFileInput');
        const fileInfo = document.getElementById('rapportFileInfo');
        const fileName = document.getElementById('rapportFileName');
        const fileSize = document.getElementById('rapportFileSize');

        if (!dropZone || !fileInput || !fileInfo || dropZone.dataset.initialized === 'true') return;

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault(); e.stopPropagation();
            dropZone.classList.add('border-cyan-400', 'bg-cyan-400/10');
        });
        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault(); e.stopPropagation();
            dropZone.classList.remove('border-cyan-400', 'bg-cyan-400/10');
        });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault(); e.stopPropagation();
            dropZone.classList.remove('border-cyan-400', 'bg-cyan-400/10');
            if (e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                handleFileSelect(e.dataTransfer.files[0]);
            }
        });

        fileInput.addEventListener('change', function () {
            if (this.files.length > 0) handleFileSelect(this.files[0]);
        });

        function handleFileSelect(file) {
            if (file.size > 10 * 1024 * 1024) {
                showWarningMessage('Le fichier est trop volumineux (max 10 Mo).');
                removeFile(); return;
            }
            const validExt = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.gif'];
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            if (!validExt.includes(ext)) {
                showWarningMessage('Type de fichier non supporté.');
                removeFile(); return;
            }
            fileName.textContent = file.name;
            fileSize.textContent = '(' + (file.size / 1024 / 1024).toFixed(2) + ' Mo)';
            fileInfo.classList.remove('hidden');
            dropZone.classList.add('hidden');
        }

        window.removeRapportFile = function () {
            fileInput.value = '';
            fileInfo.classList.add('hidden');
            dropZone.classList.remove('hidden');
        };

        dropZone.dataset.initialized = 'true';
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

        function ligneMontant(row) {
            const q = parseFloat(row.querySelector('input[name$="-quantite"]')?.value) || 0;
            const p = parseFloat(row.querySelector('input[name$="-prix_unitaire"]')?.value) || 0;
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

        tbody.querySelectorAll('tr').forEach(attachRow);

        if (!addBtn.dataset.bound) {
            addBtn.dataset.bound = 'true';
            addBtn.addEventListener('click', addRow);
        }

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

    /* ═══════════════════════════════════════════════════════════
       INIT
       ═══════════════════════════════════════════════════════════ */
    function initAll() {
        initUpload();
        fixDateInputs();
        initDepenses();
        initStocks();
    }

    document.addEventListener('DOMContentLoaded', initAll);
    document.addEventListener('rapportFormLoaded', () => setTimeout(initAll, 100));

    window.reinitRapportForm = initAll;

})();