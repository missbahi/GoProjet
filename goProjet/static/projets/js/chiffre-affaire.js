(() => {
    function init() {
        const host = document.getElementById('ca-table');
        if (!host || host.dataset.initialized) return;
        const form = document.getElementById('ca-form');
        const errorBox = document.getElementById('ca-error');
        const origin = form.querySelector('[name="origine"]');
        const editable = host.dataset.editable === 'true';
        const helpDialog = document.getElementById('ca-help-dialog');
        document.getElementById('ca-help-open')?.addEventListener('click', () => helpDialog.showModal());
        document.getElementById('ca-help-close')?.addEventListener('click', () => helpDialog.close());
        let token = '';
        let action = 'enregistrer';
        let revision = 0;
        let busy = false;
        let table;
        let savedState;
        let saved = form.dataset.existant === 'true';
        let validated = form.dataset.statut === 'VALIDE';
        const state = () => JSON.stringify({
            fields: [...form.querySelectorAll('[name="mois"], [name="origine"], [name="observations"]')]
                .map(field => [field.name, field.value]),
            lignes: table.getData().filter(row => !row.est_titre).map(row => [
                row.id, Number(row.quantite_cumulee), reprise() ? Number(row.cumul_initial) : 0,
            ]),
        });
        const updateActionButtons = () => {
            if (!table || savedState === undefined) return;
            const unchanged = saved && state() === savedState;
            for (const button of form.querySelectorAll('button[type="submit"]')) {
                button.disabled = busy || !editable
                    || (button.value === 'enregistrer' && unchanged)
                    || (button.value === 'valider' && validated);
            }
        };
        const invalidate = () => { token = ''; revision += 1; updateActionButtons(); };
        const showError = error => {
            errorBox.textContent = error.message;
            errorBox.hidden = false;
            errorBox.scrollIntoView({ block: 'start', behavior: 'smooth' });
        };
        const format = value => new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
        const reprise = () => host.dataset.premier === 'true' && origin.value === 'REPRISE';
        const previous = row => reprise() ? Number(row.cumul_initial) : Number(row.cumul_precedent);
        const initial = new Map();
        const collapsed = new Set();
        const parentIds = new Set();
        const expandAllButton = document.getElementById('toggle-expanded-all-btn');
        const updateExpandAllButton = () => {
            if (!expandAllButton) return;
            const expand = collapsed.size > 0;
            const label = expand ? 'Développer toutes les lignes filles' : 'Réduire toutes les lignes filles';
            expandAllButton.title = label;
            expandAllButton.setAttribute('aria-label', label);
            expandAllButton.disabled = busy || parentIds.size === 0;
            expandAllButton.querySelector('i').className = expand ? 'fas fa-expand-alt' : 'fas fa-compress-alt';
        };
        const updateHiddenRows = () => {
            const hidden = [];
            let collapsedLevel = null;
            table.getData().forEach((row, index) => {
                if (collapsedLevel !== null && row.niveau > collapsedLevel) hidden.push(index);
                else {
                    collapsedLevel = collapsed.has(row.id) ? row.niveau : null;
                }
            });
            table.setHiddenRows(hidden);
            updateExpandAllButton();
            selectionSummary();
        };
        const validQuantity = value => Number.isFinite(value) && value >= 0 && value < 1e12
            && Math.abs(value * 1000 - Math.round(value * 1000)) < 0.000001;
        const selectionSummary = () => {
            const display = document.getElementById('selectionSumDisplay');
            if (!table || !display) return;
            const cells = table.getSelectedCellValues({ structured: true }).cells.filter(cell =>
                !cell.row.est_titre && cell.column.type === 'number'
                && typeof cell.value === 'number' && Number.isFinite(cell.value));
            const sum = cells.reduce((value, cell) => value + cell.value, 0);
            display.style.display = cells.length > 1 ? 'block' : 'none';
            display.textContent = cells.length > 1
                ? `Somme : ${format(sum)} | Moyenne : ${format(sum / cells.length)} | (${cells.length} cellule${cells.length > 1 ? 's' : ''})`
                : '';
        };
        const total = () => {
            document.getElementById('ca-total').textContent = format(table.getData().reduce((s, row) =>
                s + (row.est_titre ? 0 : (Number(row.quantite_cumulee) - previous(row)) * Number(row.prix_unitaire)), 0));
        };
        const numeric = (key, label, decimals = 3) => ({
            key, label, type: 'number', decimals, editable: false, hideZero: true, width: 140,
            getValue: row => row.est_titre ? null : Number(row[key]),
        });
        const quantity = (key, label) => ({
            ...numeric(key, label), editable: true,
            parse: raw => String(raw).trim() === '' ? 0 : table.parseNumber(raw, { locale: 'fr-FR' }),
            validate: value => validQuantity(value)
                || 'Saisissez un cumul positif ou nul avec au plus trois décimales.',
        });
        const initialColumn = { ...quantity('cumul_initial', 'Cumul initial (reprise)'), editable: undefined };
        try {
            const data = JSON.parse(JSON.parse(document.getElementById('ca-data').textContent));
            data.forEach(row => initial.set(row.id, Number(row.quantite_cumulee)));
            data.forEach((row, index) => {
                if (data[index + 1]?.niveau > row.niveau) parentIds.add(row.id);
            });
            table = new window.TableView(host, {
                label: 'Production mensuelle cumulée', data, rowKey: 'id', editable, locale: 'fr-FR',
                rowHeaders: false, selectionMode: 'multi', clipboard: { copy: true, paste: editable, parseTsv: true },
                appearance: { selectionColor: '#e7ece9' },
                hierarchy: {
                    columnKey: 'designation',
                    isGroup: row => parentIds.has(row.id),
                    getLevel: row => Math.max(0, row.niveau - 1),
                    isExpanded: row => !collapsed.has(row.id),
                    onToggle: (rowIndex, row) => {
                        if (collapsed.has(row.id)) collapsed.delete(row.id);
                        else collapsed.add(row.id);
                        table.render();
                        updateHiddenRows();
                    },
                },
                isRowEditable: row => !row.est_titre,
                isCellEditable: ({ column }) => column.key !== 'cumul_initial' || reprise(),
                columns: [
                    { key: 'numero', label: 'N°', editable: false, width: 80 },
                    { key: 'designation', label: 'Désignation', editable: false, width: 350, className: 'ca-designation',
                        render: (value, row) => {
                            const span = document.createElement('span');
                            span.append(document.createTextNode(String(value ?? '').replace(/\s+/g, ' ')));
                            return span;
                        } },
                    { key: 'unite', label: 'Unité', editable: false, width: 80, align: 'center' },
                    numeric('quantite_marche', 'Quantité marché'),
                    numeric('prix_unitaire', 'PU HT', 2),
                    ...(reprise() ? [initialColumn] : []),
                    { ...numeric('cumul_precedent', 'Cumul N−1'), getValue: row => row.est_titre ? null : previous(row) },
                    quantity('quantite_cumulee', 'Cumul N'),
                    { ...numeric('partielle', 'Quantité du mois'), getValue: row => row.est_titre ? null : Number(row.quantite_cumulee) - previous(row) },
                    { ...numeric('montant', 'Montant du mois HT', 2), className: 'is-amount', getValue: row => row.est_titre ? null : (Number(row.quantite_cumulee) - previous(row)) * Number(row.prix_unitaire) },
                ],
                cellClassName: ({ row, column }) => {
                    if (row.est_titre) return '';
                    const classes = [];
                    if (column.key === 'quantite_cumulee' && Number(row.quantite_cumulee) !== initial.get(row.id)) classes.push('modified-cell');
                    if (['quantite_cumulee', 'cumul_initial'].includes(column.key)) {
                        const value = Number(row[column.key]);
                        if (!validQuantity(value) || value > Number(row.quantite_marche)) classes.push('ca-quantity-error');
                    }
                    if (['quantite_cumulee', 'partielle', 'montant'].includes(column.key)
                        && Number(row.quantite_cumulee) < previous(row)) classes.push('ca-regularisation');
                    return classes.join(' ');
                },
                rowClassName: row => row.est_titre ? `native-bdp-title-row title-row-level-${Math.min(row.niveau, 4)}` : '',
                onSelectionChange: selectionSummary,
                onDataChange: () => { invalidate(); total(); selectionSummary(); },
                onPaste: ({ newRows }) => { if (newRows.length) throw new Error('Le collage ne peut pas ajouter de lignes.'); },
                onValidationError: () => showError(new Error('Quantité invalide : cumul positif ou nul, trois décimales maximum.')),
                onClipboardError: showError,
            });
            host.dataset.initialized = 'true';
            savedState = state();
            updateActionButtons();
            total();
            selectionSummary();
            updateExpandAllButton();
        } catch (error) {
            showError(error);
            form.addEventListener('submit', event => event.preventDefault());
            return;
        }
        expandAllButton?.addEventListener('click', () => {
            if (!table.finishEdit()) return;
            const expand = collapsed.size > 0;
            collapsed.clear();
            if (!expand) parentIds.forEach(id => collapsed.add(id));
            table.render();
            updateHiddenRows();
        });
        form.addEventListener('input', invalidate);
        form.addEventListener('change', () => {
            invalidate();
            if (table.columns.some(column => column.key === 'cumul_initial') !== reprise()) {
                const columns = table.columns.filter(column => column.key !== 'cumul_initial');
                if (reprise()) columns.splice(5, 0, initialColumn);
                table.setColumns(columns);
            } else table.render();
            total();
            selectionSummary();
        });
        async function submit(confirming) {
            if (busy || !editable || !table.finishEdit() || !form.reportValidity()) return;
            if (action === 'valider' && validated
                || action === 'enregistrer' && saved && state() === savedState) return;
            if (confirming && !token) return;
            busy = true;
            let confirmed = false;
            const sentRevision = revision;
            errorBox.hidden = true;
            form.querySelectorAll('button').forEach(button => { button.disabled = true; });
            try {
                const payload = new FormData(form);
                payload.set('action', action);
                payload.set('confirmation', confirming ? token : '');
                payload.set('lignes', JSON.stringify(table.getData().map(row => ({
                    id: row.id, quantite_cumulee: row.quantite_cumulee,
                    cumul_initial: reprise() ? row.cumul_initial : 0,
                }))));
                const response = await fetch(window.location.href, { method: 'POST', credentials: 'same-origin', body: payload });
                if (!response.headers.get('content-type')?.includes('application/json')) {
                    throw new Error(`Le serveur a refusé la demande (HTTP ${response.status}). Rechargez la page.`);
                }
                const result = await response.json();
                if (!response.ok) throw new Error(result.erreur || `Erreur HTTP ${response.status}`);
                if (result.enregistre) {
                    saved = true;
                    savedState = state();
                    if (action === 'valider') validated = true;
                    if (action === 'devalider') validated = false;
                    window.location.href = result.redirect;
                    return;
                }
                if (revision !== sentRevision) throw new Error('La saisie a changé pendant la vérification. Vérifiez à nouveau.');
                token = result.confirmation;
                if (confirming) throw new Error('Le serveur n’a pas confirmé l’enregistrement.');
                confirmed = window.confirm('Confirmer cette opération sur le CA et la mise à jour des situations concernées ?');
            } catch (error) {
                invalidate(); showError(error);
            } finally {
                busy = false;
                form.querySelectorAll('button').forEach(button => { button.disabled = false; });
                updateExpandAllButton();
                updateActionButtons();
            }
            if (confirmed) await submit(true);
            else token = '';
        }
        form.addEventListener('submit', event => {
            event.preventDefault();
            if (busy) return;
            action = event.submitter?.value || 'enregistrer';
            invalidate();
            submit(false);
        });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
    else init();
})();
