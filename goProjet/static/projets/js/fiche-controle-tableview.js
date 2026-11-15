(function () {
    'use strict';

    const helpDialog = document.getElementById('fiche-help-dialog');
    document.getElementById('fiche-help-open')?.addEventListener('click', () => helpDialog.showModal());
    document.getElementById('fiche-info-open')?.addEventListener('click', () => helpDialog.showModal());
    document.getElementById('fiche-help-close')?.addEventListener('click', () => helpDialog.close());

    const host = document.getElementById('fiche-tableview');
    if (!host) return;

    const errorBox = document.getElementById('fiche-tableview-error');
    const expandAllButton = document.getElementById('fiche-toggle-expanded-all');
    const selectionDisplay = document.getElementById('selectionSumDisplay');
    const printTable = document.querySelector('.fiche-print-table .table-fiche');
    const showError = message => {
        errorBox.textContent = message;
        errorBox.hidden = false;
    };

    try {
        if (!window.TableView || !printTable) {
            throw new Error('Le tableau de contrôle est indisponible.');
        }

        const keys = [
            'numero', 'designation', 'unite', 'quantite_marche', 'montant_marche',
            'quantite_s1', 'quantite_partiel', 'montant_partiel', 'quantite_s',
            'montant_s', 'delta_quantite', 'delta_montant', 'pourcentage_realise',
        ];
        const number = cell => {
            const text = cell.textContent.trim().replace(/[\s\u00a0\u202f%]/g, '').replace(',', '.');
            if (!text) return null;
            const value = Number(text);
            if (!Number.isFinite(value)) throw new Error(`Valeur numérique invalide : ${cell.textContent.trim()}`);
            return value;
        };
        let lotId = null;
        let lotNumber = 0;
        let rows = Array.from(printTable.tBodies[0].rows, tr => {
            const cells = Array.from(tr.cells);
            if (tr.classList.contains('lot-header')) {
                lotId = `lot:${++lotNumber}`;
                return { id: lotId, kind: 'lot', designation: cells[0].textContent.trim(), level: 0 };
            }
            if (tr.classList.contains('sous-total') || tr.classList.contains('total-general')) {
                const isTotal = tr.classList.contains('total-general');
                return {
                    id: isTotal ? 'total' : `subtotal:${lotNumber}`,
                    parent: isTotal ? null : lotId,
                    kind: isTotal ? 'total' : 'subtotal',
                    designation: cells[0].textContent.trim(),
                    level: isTotal ? 0 : 1,
                    montant_marche: number(cells[1]),
                    montant_partiel: number(cells[2]),
                    montant_s: number(cells[3]),
                    delta_montant: number(cells[4]),
                    pourcentage_realise: number(cells[5]),
                };
            }
            if (!tr.dataset.ligneId) throw new Error('Une ligne du bordereau ne possède pas d’identifiant.');
            const row = {
                id: `ligne:${tr.dataset.ligneId}`,
                parent: tr.dataset.parentId ? `ligne:${tr.dataset.parentId}` : lotId,
                kind: tr.classList.contains('is_title') ? 'title' : 'line',
                level: Number(tr.dataset.niveau || 0) + (lotId ? 1 : 0),
            };
            keys.forEach((key, index) => {
                row[key] = index < 3 ? cells[index].textContent.trim() : number(cells[index]);
            });
            return row;
        });

        const collapsed = new Set();
        const manuallyHidden = new Set();
        const heights = new Map();
        const groupIds = () => {
            const parents = new Set(rows.map(row => row.parent));
            return new Set(rows.filter(row => row.kind !== 'subtotal' && row.kind !== 'total'
                && parents.has(row.id)).map(row => row.id));
        };
        let groups = groupIds();
        let table;
        const updateSelectionSummary = () => {
            if (!table || !selectionDisplay) return;
            const cells = table.getSelectedCellValues({ structured: true }).cells.filter(cell =>
                cell.row.kind === 'line' && cell.column.type === 'number'
                && typeof cell.value === 'number' && Number.isFinite(cell.value));
            const sum = cells.reduce((total, cell) => total + cell.value, 0);
            const format = value => new Intl.NumberFormat('fr-FR', {
                minimumFractionDigits: 2, maximumFractionDigits: 2,
            }).format(value);
            selectionDisplay.style.display = cells.length > 1 ? 'block' : 'none';
            selectionDisplay.textContent = cells.length > 1
                ? `Somme : ${format(sum)} | Moyenne : ${format(sum / cells.length)} | (${cells.length} cellules)`
                : '';
        };
        const updateHidden = () => {
            const byId = new Map(rows.map(row => [row.id, row]));
            const hidden = [];
            rows.forEach((row, index) => {
                let parent = row.parent;
                const seen = new Set();
                while (parent && !seen.has(parent)) {
                    if (collapsed.has(parent)) break;
                    seen.add(parent);
                    parent = byId.get(parent)?.parent;
                }
                if (manuallyHidden.has(row.id) || (parent && collapsed.has(parent))) hidden.push(index);
            });
            table.setHiddenRows(hidden);
            if (expandAllButton) {
                const expand = collapsed.size > 0;
                const label = expand ? 'Développer toutes les lignes filles' : 'Réduire toutes les lignes filles';
                expandAllButton.disabled = groups.size === 0;
                expandAllButton.title = label;
                expandAllButton.setAttribute('aria-label', label);
                expandAllButton.querySelector('i').className = expand ? 'fas fa-expand-alt' : 'fas fa-compress-alt';
            }
            updateSelectionSummary();
        };
        const selectedRows = selection => (selection?.rowIndexes || [])
            .map(index => rows[index]).filter(row => row && row.kind !== 'lot' && row.kind !== 'total');
        const columns = [
            { key: 'numero', label: 'N°', width: 75, group: 'MARCHÉ', align: 'left' },
            {
                key: 'designation', label: 'Désignation des prestations', width: 360,
                group: 'MARCHÉ', align: 'left', className: 'fiche-designation',
                render: value => {
                    const text = document.createElement('span');
                    text.textContent = value || '';
                    text.title = value || '';
                    return text;
                },
            },
            { key: 'unite', label: 'Unité', width: 70, group: 'MARCHÉ', align: 'center' },
            { key: 'quantite_marche', label: 'Qté marché', width: 110, group: 'MARCHÉ' },
            { key: 'montant_marche', label: 'Mt marché', width: 140, group: 'MARCHÉ' },
            { key: 'quantite_s1', label: 'Qté cumul N-1', width: 110, group: 'RÉALISATION' },
            { key: 'quantite_partiel', label: 'Qté part.', width: 110, group: 'RÉALISATION' },
            { key: 'montant_partiel', label: 'Mt part.', width: 140, group: 'RÉALISATION' },
            { key: 'quantite_s', label: 'Qté cumul N', width: 110, group: 'RÉALISATION' },
            { key: 'montant_s', label: 'Mt cumul N', width: 140, group: 'RÉALISATION' },
            { key: 'delta_quantite', label: 'Qté M - Qté N', width: 110, group: 'ÉCARTS' },
            { key: 'delta_montant', label: 'Mt M - Mt N', width: 140, group: 'ÉCARTS' },
            { key: 'pourcentage_realise', label: '% réalisé', width: 90, group: 'ÉCARTS' },
        ].map((column, index) => index < 3 ? column : {
            ...column, type: 'number', align: 'right', decimals: index === 12 ? 0 : 2,
            ...(index === 12 ? {
                format: value => value == null ? '' : `${new Intl.NumberFormat('fr-FR', {
                    maximumFractionDigits: 0,
                }).format(value)} %`,
            } : {}),
        });

        table = new window.TableView(host, {
            label: 'Fiche de contrôle des attachements',
            data: rows,
            rowKey: 'id',
            locale: 'fr-FR',
            editable: false,
            selectionMode: 'multi',
            resizableHeader: true,
            headerResizeLabel: 'Ajuster la hauteur des en-têtes',
            appearance: { rowHeight: 36, headerHeight: 48, fontSize: 13 },
            clipboard: { copy: true, paste: false },
            onSelectionChange: updateSelectionSummary,
            columns,
            hierarchy: {
                columnKey: 'designation',
                getLevel: row => row.level,
                isGroup: row => groups.has(row.id),
                isExpanded: row => !collapsed.has(row.id),
                onToggle: (index, row) => {
                    if (collapsed.has(row.id)) collapsed.delete(row.id);
                    else collapsed.add(row.id);
                    table.refreshRow(index);
                    updateHidden();
                },
            },
            rowClassName: row => [
                row.kind === 'lot' ? 'fiche-lot' : '',
                row.kind === 'title' ? 'fiche-titre' : '',
                row.kind === 'subtotal' ? 'fiche-sous-total' : '',
                row.kind === 'total' ? 'fiche-total' : '',
                heights.get(row.id) || '',
            ].filter(Boolean).join(' '),
            cellClassName: ({ column, row }) => {
                if (['montant_marche', 'montant_partiel', 'montant_s'].includes(column.key)) {
                    return 'montant';
                }
                const value = row[column.key];
                if (value == null) return '';
                if (column.key === 'delta_quantite' || column.key === 'delta_montant') {
                    return value < 0 ? 'delta-negatif' : 'delta-positif';
                }
                if (column.key === 'pourcentage_realise') {
                    return value < 100 ? 'delta-positif' : value > 100 ? 'delta-negatif' : '';
                }
                return '';
            },
            rowActions: {
                contextMenu: true,
                items: [
                    { id: 'hide', label: 'Masquer les lignes' },
                    { id: 'show', label: 'Afficher les lignes masquées' },
                    { id: 'delete', label: 'Supprimer les lignes de l’affichage' },
                    { id: 'copy', label: 'Copier le contenu des lignes' },
                    { id: 'compact', label: 'Hauteur compacte', group: 'height' },
                    { id: 'normal', label: 'Hauteur normale', group: 'height' },
                    { id: 'large', label: 'Hauteur large', group: 'height' },
                ],
                onAction: (action, { selection }) => {
                    const selected = selectedRows(selection);
                    if (action === 'show') {
                        manuallyHidden.clear();
                        updateHidden();
                    } else if (action === 'hide') {
                        selected.forEach(row => manuallyHidden.add(row.id));
                        updateHidden();
                    } else if (action === 'delete' && selected.length
                        && window.confirm(`Supprimer ${selected.length} ligne(s) de l’affichage ?`)) {
                        const ids = new Set(selected.map(row => row.id));
                        rows = rows.filter(row => !ids.has(row.id));
                        groups = groupIds();
                        table.setData(rows, true);
                        updateHidden();
                    } else if (action === 'copy' && selected.length) {
                        const text = selected.map(row => keys.map((key, index) => {
                            const cell = table.getCell(rows.indexOf(row), index);
                            return (cell.querySelector('.tv-hierarchy-content') || cell).textContent.trim();
                        }).join('\t')).join('\n');
                        if (!navigator.clipboard?.writeText) {
                            showError('La copie est indisponible dans ce navigateur.');
                        } else {
                            navigator.clipboard.writeText(text).catch(error => showError(`Copie impossible : ${error.message}`));
                        }
                    } else if (['compact', 'normal', 'large'].includes(action)) {
                        const height = action === 'compact' ? 'fiche-hauteur-compacte'
                            : action === 'large' ? 'fiche-hauteur-large' : '';
                        selected.forEach(row => heights.set(row.id, height));
                        selected.forEach(row => table.refreshRow(rows.indexOf(row)));
                    }
                },
            },
        });
        updateHidden();
        expandAllButton?.addEventListener('click', () => {
            const expand = collapsed.size > 0;
            collapsed.clear();
            if (!expand) groups.forEach(id => collapsed.add(id));
            table.render();
            updateHidden();
        });
    } catch (error) {
        console.error('Initialisation de la fiche de contrôle impossible.', error);
        showError(`Impossible de charger le tableau : ${error.message}`);
    }
})();
