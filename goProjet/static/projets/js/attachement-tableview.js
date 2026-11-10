(function () {
    'use strict';

    function init() {
        const container = document.getElementById('attachement-tableview');
        if (!container || container.dataset.initialized) return;
        const form = document.getElementById('attachement-form');
        const errorBox = document.getElementById('attachement-tableview-error');
        const saveButton = document.getElementById('save-btn');
        const transmitButton = document.getElementById('transmettre-btn');
        const editable = container.dataset.editable === 'true';
        const correction = container.dataset.correction === 'true';
        let confirmation = '';
        let correctionPending = false;
        let confirming = false;
        let revision = 0;
        const modified = new Set();
        const quantityError = 'Saisissez un cumul positif ou nul, avec au plus trois décimales (12 chiffres entiers maximum).';
        const format = (value, decimals = 2) => new Intl.NumberFormat('en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        }).format(value);
        const showError = message => {
            errorBox.textContent = message;
            errorBox.hidden = false;
        };
        let table;

        try {
            const data = JSON.parse(JSON.parse(
                document.getElementById('attachement-tableview-data').textContent
            ));
            const initialQuantities = new Map(data.map(row => [row.id, Number(row.quantite_realisee)]));
            const updateModified = row => {
                if (Number(row.quantite_realisee) === initialQuantities.get(row.id)) {
                    modified.delete(row.id);
                } else {
                    modified.add(row.id);
                }
            };
            const numberColumn = (key, label, decimals, width) => ({
                key, label, type: 'number', decimals, width,
                editable: false, hideZero: true, locale: 'en-US',
                getValue: row => row.is_title ? null : row[key],
            });
            table = new window.TableView(container, {
                label: "Détail des lignes d'attachement",
                data,
                rowKey: 'id',
                locale: 'fr-FR',
                editable,
                selectionMode: 'multi',
                rowHeaders: false,
                clipboard: { copy: true, paste: editable, parseTsv: true },
                appearance: { rowHeight: 40, headerHeight: 48, fontSize: 13 },
                columns: [
                    { key: 'numero', label: 'N°', width: 80, editable: false },
                    {
                        key: 'designation', label: 'Désignation', width: 400, editable: false,
                        render: (value, row) => {
                            const text = document.createElement('span');
                            text.textContent = value;
                            text.style.paddingLeft = `${(row.niveau || 0) * 8}px`;
                            return text;
                        },
                    },
                    { key: 'unite', label: 'Unité', width: 100, align: 'center', editable: false },
                    numberColumn('quantite_prevue', 'Quantité marché', 3, 120),
                    numberColumn('prix_unitaire', 'PU', 2, 120),
                    numberColumn('quantite_deja_realisee', 'Cumul précédent', 3, 100),
                    {
                        ...numberColumn('quantite_realisee', 'Nouveau cumul', 3, 140),
                        editable: true,
                        className: 'attachment-quantity',
                        parse: raw => String(raw).trim() === '' ? 0
                            : table.parseNumber(raw, { locale: 'fr-FR' }),
                        validate: value => (
                            Number.isFinite(value) && value >= 0
                            && value < 1e12
                            && Math.abs(value * 1000 - Math.round(value * 1000)) < 0.000001
                        ) || quantityError,
                    },
                    {
                        ...numberColumn('montant', 'Montant attaché (HT)', 2, 140),
                        getValue: row => row.is_title ? null
                            : row.quantite_realisee * row.prix_unitaire,
                        className: 'attachment-amount',
                    },
                ],
                isRowEditable: row => !row.is_title,
                rowClassName: row => row.is_title ? 'attachment-title' : '',
                cellClassName: ({ row, column }) => (
                    column.key === 'quantite_realisee' && modified.has(row.id)
                        ? 'modified-cell' : ''
                ),
                onDataChange: event => {
                    if (event.phase === 'paste') {
                        event.changes.forEach(({ row }) => updateModified(row));
                        event.changes.forEach(({ rowIndex }) => table.refreshRow(rowIndex));
                    } else if (event.phase === 'commit') {
                        updateModified(event.row);
                        table.refreshRow(event.rowIndex);
                    }
                    updateTotal();
                    displaySelection();
                    errorBox.hidden = true;
                    if (correction) clearConfirmation();
                },
                onPaste: ({ newRows }) => {
                    if (newRows.length) {
                        throw new Error("Le collage ne peut pas ajouter de lignes au bordereau.");
                    }
                },
                onValidationError: () => showError(quantityError),
                onClipboardError: error => {
                    container.querySelector('[data-tv-clipboard-status]').hidden = true;
                    showError(error.message === 'Enter a finite number.' ? quantityError : error.message);
                },
                onSelectionChange: () => displaySelection(),
            });
            container.dataset.initialized = 'true';
            updateTotal();
        } catch (error) {
            console.error('Initialisation du formulaire TableView impossible.', error);
            showError(`Impossible de charger le tableau : ${error.message}`);
            if (saveButton) saveButton.disabled = true;
            if (transmitButton) transmitButton.disabled = true;
            form.addEventListener('submit', event => event.preventDefault());
            return;
        }

        function updateTotal() {
            const total = table.getData().reduce((sum, row) => (
                row.is_title ? sum : sum + row.quantite_realisee * row.prix_unitaire
            ), 0);
            const totalElement = document.getElementById('total_attachement');
            totalElement.textContent = `${format(total)} DH`;
            totalElement.style.color = '#22d3ee';
        }

        function displaySelection() {
            if (!table) return;
            const { cells } = table.getSelectedCellValues({ structured: true, omitNullValues: true });
            const numbers = cells.filter(cell => cell.column.type === 'number'
                && Number.isFinite(cell.value) && cell.value !== 0).map(cell => cell.value);
            const display = document.getElementById('selectionSumDisplay');
            if (numbers.length > 1) {
                const sum = numbers.reduce((total, value) => total + value, 0);
                display.textContent = `Somme : ${format(sum)} | Moyenne : ${format(sum / numbers.length)} | (${numbers.length} cellules)`;
                display.style.display = 'block';
            } else {
                display.style.display = 'none';
            }
        }

        function prepareSubmission() {
            if (!editable || !table.finishEdit()) return false;
            if (!form.reportValidity()) return false;
            if (!correction && !table.getData().some(row => !row.is_title && row.quantite_realisee > 0)) {
                showError('Veuillez saisir au moins une quantité à attacher.');
                return false;
            }
            let input = form.querySelector('[name="lignes_attachement"]');
            if (!input) {
                input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'lignes_attachement';
                form.appendChild(input);
            }
            input.value = JSON.stringify(table.getData().map(row => ({
                id: row.id,
                quantite_realisee: row.is_title ? 0 : row.quantite_realisee,
            })));
            return true;
        }

        function loading(button, text) {
            if (!button) return;
            button.disabled = true;
            button.replaceChildren();
            const icon = document.createElement('i');
            icon.className = 'fa-solid fa-spinner fa-spin';
            button.append(icon, document.createTextNode(` ${text}`));
        }

        function clearConfirmation() {
            revision += 1;
            confirmation = '';
            document.getElementById('correction-impact-panel').hidden = true;
        }

        async function submitCorrection(approvedToken) {
            if (correctionPending) return;
            correctionPending = true;
            const submittedRevision = revision;
            loading(saveButton, 'Vérification...');
            const confirmButton = document.getElementById('confirm-correction-btn');
            confirmButton.disabled = true;
            try {
                const payload = new FormData(form);
                payload.set('confirmation_correction', approvedToken);
                const response = await fetch(window.location.href, {
                    method: 'POST', body: payload, credentials: 'same-origin',
                });
                if (!response.headers.get('content-type')?.includes('application/json')) {
                    throw new Error(`Le serveur a refusé la correction (HTTP ${response.status}). Rechargez la page.`);
                }
                const result = await response.json();
                if (!response.ok) throw new Error(result.erreur || `Erreur HTTP ${response.status}`);
                if (result.enregistre) {
                    window.location.href = result.redirect;
                    return;
                }
                if (revision !== submittedRevision) {
                    throw new Error("La saisie a changé pendant la vérification. Vérifiez à nouveau les impacts.");
                }
                confirmation = result.confirmation;
                const rows = document.getElementById('correction-impact-rows');
                rows.replaceChildren();
                result.impacts.forEach(impact => {
                    const row = document.createElement('tr');
                    ['objet', 'champ', 'avant', 'apres'].forEach(key => {
                        const cell = document.createElement('td');
                        cell.textContent = impact[key];
                        row.appendChild(cell);
                    });
                    rows.appendChild(row);
                });
                const panel = document.getElementById('correction-impact-panel');
                panel.hidden = false;
                panel.scrollIntoView({ block: 'center', behavior: 'smooth' });
            } catch (error) {
                clearConfirmation();
                showError(error.message);
            } finally {
                correctionPending = false;
                if (saveButton) {
                    saveButton.disabled = false;
                    saveButton.textContent = "Vérifier la correction";
                }
                confirmButton.disabled = false;
            }
        }

        form.addEventListener('submit', event => {
            if (event.submitter?.name === 'action' && event.submitter.value === 'valider') {
                document.getElementById('statut').value = 'VALIDE';
            }
            if (correction && correctionPending) {
                event.preventDefault();
                return;
            }
            if (!prepareSubmission()) {
                event.preventDefault();
                return;
            }
            if (correction) {
                event.preventDefault();
                const approvedToken = confirming ? confirmation : '';
                if (!confirming) clearConfirmation();
                submitCorrection(approvedToken);
                return;
            }
            loading(saveButton, 'Sauvegarde...');
        });
        if (correction) {
            form.addEventListener('input', clearConfirmation);
            form.addEventListener('change', clearConfirmation);
            document.getElementById('confirm-correction-btn').addEventListener('click', () => {
                if (!confirmation || correctionPending) return;
                confirming = true;
                try {
                    form.requestSubmit();
                } finally {
                    confirming = false;
                }
            });
            if (saveButton) saveButton.textContent = "Vérifier la correction";
        }
        if (saveButton) saveButton.addEventListener('click', () => {
            if (correction) clearConfirmation();
            form.requestSubmit();
        });
        if (transmitButton) transmitButton.addEventListener('click', () => {
            if (!prepareSubmission()) return;
            if (!confirm("Êtes-vous sûr de vouloir transmettre cet attachement pour validation ?\n\nCette action sauvegardera les modifications et changera le statut à Transmis.")) return;
            document.getElementById('statut').value = 'TRANSMIS';
            form.requestSubmit();
        });
        const deleteButton = document.getElementById('delete-btn');
        if (deleteButton) deleteButton.addEventListener('click', () => {
            if (!confirm('Êtes-vous sûr de vouloir supprimer cet attachement ? Cette action est irréversible.')) return;
            const deleteForm = document.createElement('form');
            deleteForm.method = 'POST';
            deleteForm.action = container.dataset.deleteUrl;
            deleteForm.appendChild(form.querySelector('[name="csrfmiddlewaretoken"]').cloneNode(true));
            document.body.appendChild(deleteForm);
            deleteForm.requestSubmit();
        });
        const reopenButton = document.getElementById('reouvrir-btn');
        if (reopenButton) {
            reopenButton.removeAttribute('onclick');
            reopenButton.addEventListener('click', () => {
                if (confirm("Réouvrir cet attachement et réinitialiser ses validations ?")) {
                    loading(reopenButton, 'Réouverture...');
                    window.location.href = container.dataset.reopenUrl;
                }
            });
        }
        const fileInput = document.getElementById('fichier');
        fileInput.removeAttribute('onchange');
        fileInput.addEventListener('change', () => {
            document.getElementById('original_filename').value = fileInput.files[0]?.name || '';
        });
        document.addEventListener('pointerdown', event => {
            if (!container.contains(event.target)) {
                document.getElementById('selectionSumDisplay').style.display = 'none';
            }
        });
        setTimeout(() => {
            document.querySelectorAll('.alert-auto-dismiss').forEach(alert => {
                alert.style.display = 'none';
            });
        }, 5000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }
})();
