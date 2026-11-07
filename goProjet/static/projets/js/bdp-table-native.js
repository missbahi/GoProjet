class NativeBordereauTable {
    constructor(container, callbacks = {}) {
        this.container = container;
        this.callbacks = callbacks;
        this.rows = [];
        this.appearance = {};
        this.hiddenRows = new Set();
        this.ranges = [];
        this.anchorCell = null;
        this.activeCell = null;
        this.contextMenu = null;

        this.container.addEventListener('click', event => this.handleClick(event));
        this.container.addEventListener('input', event => this.handleInput(event));
        this.container.addEventListener('change', event => this.handleChange(event));
        this.container.addEventListener('focusin', event => this.handleFocusIn(event));
        this.container.addEventListener('focusout', event => this.handleFocusOut(event));
        this.container.addEventListener('keydown', event => this.handleKeyDown(event));
        this.container.addEventListener('contextmenu', event => this.handleContextMenu(event));
        document.addEventListener('pointerdown', event => {
            if (this.contextMenu && !this.contextMenu.contains(event.target)) {
                this.closeContextMenu();
            }
        });
        document.addEventListener('keydown', event => {
            if (this.contextMenu && event.key === 'Escape') {
                event.preventDefault();
                this.closeContextMenu(true);
            }
        });
        document.addEventListener('scroll', event => {
            if (this.contextMenu && !this.contextMenu.contains(event.target)) {
                this.closeContextMenu();
            }
        }, true);
        window.addEventListener('resize', () => this.closeContextMenu());
    }

    setRows(rows) {
        const previousRows = this.rows;
        const previousRanges = this.ranges.map(range => ({
            lineIds: previousRows
                .slice(range.startRow, range.endRow + 1)
                .map(row => row.id),
            startCol: range.startCol,
            endCol: range.endCol,
        }));
        const anchorId = previousRows[this.anchorCell?.row]?.id;
        const activeId = previousRows[this.activeCell?.row]?.id;
        this.rows = rows;
        const rowIndexes = new Map(rows.map((row, index) => [row.id, index]));
        this.ranges = previousRanges.flatMap(range => {
            const indexes = Array.from(new Set(range.lineIds
                .map(id => rowIndexes.get(id))
                .filter(index => index !== undefined))).sort((left, right) => left - right);
            const groups = [];
            indexes.forEach(index => {
                const current = groups[groups.length - 1];
                if (current && index === current.endRow + 1) {
                    current.endRow = index;
                } else {
                    groups.push({ startRow: index, endRow: index });
                }
            });
            return groups.map(group => ({
                ...group,
                startCol: range.startCol,
                endCol: range.endCol,
                isSingleCell: group.startRow === group.endRow && range.startCol === range.endCol,
                nbRows: group.endRow - group.startRow + 1,
            }));
        });
        this.anchorCell = anchorId && rowIndexes.has(anchorId)
            ? { ...this.anchorCell, row: rowIndexes.get(anchorId) } : null;
        this.activeCell = activeId && rowIndexes.has(activeId)
            ? { ...this.activeCell, row: rowIndexes.get(activeId) } : null;
        this.render();
    }

    setAppearance(appearance) {
        this.appearance = { ...this.appearance, ...appearance };
        this.render();
    }

    setHiddenRows(rows) {
        this.hiddenRows = new Set(rows);
        this.rows.forEach((row, index) => {
            const element = this.container.querySelector(`[data-row="${index}"]`);
            if (element) element.hidden = this.hiddenRows.has(index);
        });
    }

    getSelection() {
        if (this.ranges.length === 0) return null;
        const lineIds = new Set();
        this.ranges.forEach(range => {
            for (let row = range.startRow; row <= range.endRow; row++) {
                const lineId = this.rows[row]?.id;
                if (lineId) lineIds.add(lineId);
            }
        });
        return {
            ranges: this.ranges.map(range => ({ ...range })),
            lineIds: Array.from(lineIds),
            activeCell: this.activeCell ? { ...this.activeCell } : null,
        };
    }

    getSelectedCellValues() {
        const properties = {
            3: 'numero',
            4: 'designation',
            5: 'unite',
            6: 'quantite',
            7: 'prix_unitaire',
            8: 'montant',
        };
        const values = [];
        const visited = new Set();
        this.ranges.forEach(range => {
            for (let row = range.startRow; row <= range.endRow; row++) {
                for (let column = range.startCol; column <= range.endCol; column++) {
                    const property = properties[column];
                    const key = `${row}:${column}`;
                    if (!property || visited.has(key)) continue;
                    visited.add(key);
                    values.push(this.rows[row]?.[property]);
                }
            }
        });
        return values;
    }

    selectCell(row, column) {
        this.ranges = [this.createRange({ row, column }, { row, column })];
        this.anchorCell = { row, column };
        this.activeCell = { row, column };
        this.applySelection();
        this.callbacks.onSelectionChange?.();

        const input = this.getCell(row, column)?.querySelector('input');
        input?.focus({ preventScroll: true });
    }

    scrollToRow(row) {
        this.container.querySelector(`[data-row="${row}"]`)?.scrollIntoView({ block: 'nearest' });
    }

    captureViewport() {
        const scroll = this.container.querySelector('.native-bdp-scroll');
        if (!scroll) return null;
        const top = scroll.getBoundingClientRect().top
            + (scroll.querySelector('thead')?.getBoundingClientRect().height || 0);
        const anchor = Array.from(scroll.querySelectorAll('tbody tr:not([hidden])'))
            .find(row => row.getBoundingClientRect().bottom > top);
        const lineIds = [];
        if (anchor) {
            let index = Number(anchor.dataset.row);
            let level = this.rows[index].niveau;
            lineIds.push(anchor.dataset.lineId);
            for (index--; index >= 0; index--) {
                if (this.rows[index].niveau < level) {
                    lineIds.push(this.rows[index].id);
                    level = this.rows[index].niveau;
                }
            }
        }
        return {
            lineIds,
            offset: anchor ? anchor.getBoundingClientRect().top - top : 0,
            scrollTop: scroll.scrollTop,
            scrollLeft: scroll.scrollLeft,
            pageX: window.scrollX,
            pageY: window.scrollY,
        };
    }

    restoreViewport(viewport) {
        if (!viewport) return;
        const scroll = this.container.querySelector('.native-bdp-scroll');
        if (!scroll) return;
        const visibleRows = new Map(Array.from(scroll.querySelectorAll('tbody tr:not([hidden])'),
            row => [row.dataset.lineId, row]));
        const anchor = viewport.lineIds.map(id => visibleRows.get(id)).find(Boolean);
        scroll.scrollTop = viewport.scrollTop;
        if (anchor) {
            const top = scroll.getBoundingClientRect().top
                + (scroll.querySelector('thead')?.getBoundingClientRect().height || 0);
            scroll.scrollTop += anchor.getBoundingClientRect().top - top - viewport.offset;
        }
        scroll.scrollLeft = viewport.scrollLeft;
        window.scrollTo(viewport.pageX, viewport.pageY);
    }

    setCellValue(row, property, value) {
        if (this.rows[row]) this.rows[row][property] = value;
        if (property === 'montant') {
            const cell = this.container.querySelector(`[data-row="${row}"][data-property="montant"]`);
            if (cell) cell.textContent = this.formatNumber(value, 2);
        }
    }

    refreshAmounts(rows) {
        rows.forEach((row, index) => {
            if (!this.rows[index]) return;
            this.rows[index].montant = row.montant;
            const cell = this.container.querySelector(`[data-row="${index}"][data-property="montant"]`);
            if (cell) cell.textContent = Number(row.montant) === 0 ? '' : this.formatNumber(row.montant, 2);
        });
    }

    render() {
        this.closeContextMenu();
        const scroll = this.container.querySelector('.native-bdp-scroll') || document.createElement('div');
        scroll.className = 'native-bdp-scroll';
        const table = document.createElement('table');
        table.className = 'native-bdp-table';
        table.setAttribute('aria-label', 'Détail des prix unitaires');
        const widths = [
            this.appearance.width_numero,
            this.appearance.width_designation,
            this.appearance.width_unite,
            this.appearance.width_quantite,
            this.appearance.width_prix_unitaire,
            this.appearance.width_montant,
            this.appearance.width_actions,
        ];
        const widthTotal = widths.reduce((total, width) => total + (Number(width) || 0), 0);
        if (widthTotal > 0) table.style.width = `${widthTotal}px`;
        table.style.setProperty('--native-bdp-row-color', this.appearance.row_color || '');
        table.style.setProperty('--native-bdp-header-color', this.appearance.header_color || '');
        const rowColor = this.appearance.row_color || '#f8f6ef';
        const activeColor = this.appearance.active_color || '#7baec1';
        const selectedBackground = this.blendColor(activeColor, rowColor, 0.14);
        const activeBackground = this.blendColor(activeColor, rowColor, 0.22);
        table.style.setProperty('--native-bdp-selection-background', selectedBackground);
        table.style.setProperty('--native-bdp-active-background', activeBackground);
        table.style.setProperty('--native-bdp-row-ink', this.getContrastingInk(
            rowColor, selectedBackground, activeBackground,
        ));
        table.style.setProperty('--native-bdp-header-ink', this.getContrastingInk(this.appearance.header_color));
        table.style.setProperty('--native-bdp-title-color', this.appearance.title_color || '');
        table.style.setProperty('--native-bdp-active-color', this.appearance.active_color || '');
        table.style.setProperty('--native-bdp-amount-color', this.appearance.amount_color || '');

        const colgroup = document.createElement('colgroup');
        widths.forEach(width => {
            const column = document.createElement('col');
            if (Number(width) > 0) column.style.width = `${Number(width)}px`;
            colgroup.appendChild(column);
        });
        table.appendChild(colgroup);

        const head = document.createElement('thead');
        const headerRow = document.createElement('tr');
        ['N°', 'Désignation', 'Unité', 'Quantité', 'PU (DH)', 'Montant (DH)', ''].forEach(label => {
            const cell = document.createElement('th');
            cell.scope = 'col';
            if (Number(this.appearance.header_height) > 0) {
                cell.style.height = `${Number(this.appearance.header_height)}px`;
            }
            cell.textContent = label;
            // Centrer le texte et aligner verticalement au milieu
            cell.style.textAlign = 'center';
            cell.style.verticalAlign = 'middle';
            // Format Gras
            cell.style.fontWeight = 'bold';
            headerRow.appendChild(cell);
        });
        head.appendChild(headerRow);
        table.appendChild(head);

        const body = document.createElement('tbody');
        this.rows.forEach((row, index) => body.appendChild(this.renderRow(row, index)));
        table.appendChild(body);
        scroll.replaceChildren(table);
        if (scroll.parentElement !== this.container) this.container.replaceChildren(scroll);
        this.applySelection();
        this.setHiddenRows(Array.from(this.hiddenRows));
    }

    renderRow(row, index) {
        const tr = document.createElement('tr');
        tr.dataset.row = String(index);
        tr.dataset.lineId = row.id;
        tr.hidden = this.hiddenRows.has(index);
        if (Number(this.appearance.row_height) > 0) {
            tr.style.height = `${Number(this.appearance.row_height)}px`;
        }
        if (row.est_titre) {
            tr.classList.add('native-bdp-title-row', `title-row-level-${Math.min(row.niveau, 4)}`);
        }

        // numero (N°)
        this.appendInputCell(tr, index, 3, 'numero', row.numero, 'N°', false);

        // designation (Désignation)
        const designation = document.createElement('td');
        designation.dataset.row = String(index);
        designation.dataset.column = '4';
        designation.className = 'native-bdp-designation';
        const nameWrap = document.createElement('div');
        nameWrap.className = 'native-bdp-name-wrap';
        const hierarchy = document.createElement('span');
        hierarchy.className = 'native-bdp-hierarchy';
        hierarchy.style.marginInlineStart = `${Math.max(0, row.niveau - 1) * 16}px`;

        // fold button or spacer for hierarchy indentation
        if (row.est_titre) {
            const fold = document.createElement('button');
            fold.type = 'button';
            fold.className = 'native-bdp-fold';
            fold.dataset.action = 'fold';
            fold.dataset.row = String(index);
            fold.title = row._expanded ? 'Réduire les lignes filles' : 'Développer les lignes filles';
            fold.setAttribute('aria-label', fold.title);
            fold.setAttribute('aria-expanded', String(Boolean(row._expanded)));
            const icon = document.createElement('i');
            icon.className = row._expanded ? 'fas fa-chevron-down' : 'fas fa-chevron-right';
            fold.appendChild(icon);
            hierarchy.appendChild(fold);
        } else {
            const spacer = document.createElement('span');
            spacer.className = 'native-bdp-fold-spacer';
            hierarchy.appendChild(spacer);
        }
        nameWrap.appendChild(hierarchy);
        this.appendInput(nameWrap, index, 'designation', row.designation, 'Désignation');
        designation.appendChild(nameWrap);
        tr.appendChild(designation);

        // unite
        this.appendInputCell(tr, index, 5, 'unite', row.unite, 'Unité', false);
        // quantite (Quantité)
        this.appendInputCell(tr, index, 6, 'quantite', row.quantite, 'Quantité', true);
        // prix unitaire (Prix unitaire)
        this.appendInputCell(tr, index, 7, 'prix_unitaire', row.prix_unitaire, 'Prix unitaire', true);
        
        // montant (Montant)
        const amount = document.createElement('td');
        amount.dataset.row = String(index);
        amount.dataset.column = '8';
        amount.dataset.property = 'montant';
        amount.className = 'native-bdp-amount';
        amount.tabIndex = -1;
        amount.textContent = Number(row.montant) === 0 ? '' : this.formatNumber(row.montant, 2);
        tr.appendChild(amount);
        
        // actions (Actions)
        const actions = document.createElement('td');
        actions.className = 'native-bdp-actions';
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'native-bdp-delete';
        remove.dataset.action = 'delete';
        remove.dataset.row = String(index);
        remove.title = 'Supprimer la ligne sélectionnée';
        remove.setAttribute('aria-label', remove.title);
        const trash = document.createElement('i');
        trash.className = 'fas fa-trash';
        remove.appendChild(trash);
        actions.appendChild(remove);
        tr.appendChild(actions);
        return tr;
    }

    appendInputCell(row, rowIndex, column, property, value, label, numeric) {
        const cell = document.createElement('td');
        cell.dataset.row = String(rowIndex);
        cell.dataset.column = String(column);
        this.appendInput(cell, rowIndex, property, value, label, numeric);
        row.appendChild(cell);
    }

    appendInput(cell, rowIndex, property, value, label, numeric = false) {
        const input = document.createElement('input');
        input.type = 'text';
        input.value = numeric
            ? this.formatEditableNumber(value, property)
            : value == null ? '' : String(value);
        input.dataset.row = String(rowIndex);
        input.dataset.property = property;
        input.setAttribute('aria-label', `${label}, ligne ${rowIndex + 1}`);
        if (numeric) {
            input.inputMode = 'decimal';
            input.classList.add('native-bdp-number');
        }
        if (property === 'unite') input.classList.add('native-bdp-unite');

        cell.appendChild(input);
    }

    handleClick(event) {
        const fold = event.target.closest('[data-action="fold"]');
        if (fold) {
            event.preventDefault();
            this.callbacks.onToggleExpansion?.(Number(fold.dataset.row));
            return;
        }

        const remove = event.target.closest('[data-action="delete"]');
        if (remove) {
            const row = Number(remove.dataset.row);
            if (!this.getSelection()?.lineIds.includes(this.rows[row]?.id)) {
                this.selectCell(row, 4);
            }
            this.callbacks.onDelete?.();
            return;
        }

        const cell = event.target.closest('td[data-row][data-column]');
        if (!cell) return;
        this.selectFromClick(Number(cell.dataset.row), Number(cell.dataset.column), event);
    }

    handleChange(event) {
        const input = event.target.closest('input[data-row][data-property]');
        if (!input) return;
        if (input.dataset.committedValue === input.value) return;
        this.commitInput(input);
    }

    handleInput(event) {
        const input = event.target.closest('input[data-row][data-property]');
        if (input) this.commitInput(input);
    }

    commitInput(input) {
        const row = Number(input.dataset.row);
        const property = input.dataset.property;
        const numeric = property === 'quantite' || property === 'prix_unitaire';
        let value = input.value;
        if (numeric) {
            value = this.callbacks.parseNumber?.(input.value);
            if (value === null || value === undefined) {
                input.dataset.invalidInput = 'true';
                return;
            }
        }

        const normalized = this.callbacks.onCellChange?.(row, property, value);
        if (normalized === false) {
            input.dataset.invalidInput = 'true';
            input.setAttribute('aria-invalid', 'true');
            return;
        }
        delete input.dataset.invalidInput;
        input.removeAttribute('aria-invalid');
        this.rows[row][property] = normalized === undefined ? value : normalized;
        input.dataset.committedValue = input.value;
        this.callbacks.onSelectionChange?.();
    }

    handleFocusIn(event) {
        const input = event.target.closest('input[data-row][data-property]');
        if (!input) return;
        const row = Number(input.dataset.row);
        const column = Number(input.closest('td')?.dataset.column);
        if (!Number.isInteger(column)) return;

        this.activeCell = { row, column };
        this.applySelection();
        this.callbacks.onSelectionChange?.();

        if (input.dataset.property === 'quantite' || input.dataset.property === 'prix_unitaire') {
            if (input.value.trim() === '') return;
            const value = this.callbacks.parseNumber?.(input.value);
            if (value !== null && value !== undefined) {
                input.value = String(value).replace('.', ',');
                input.dataset.committedValue = input.value;
                input.select();
            }
        }
    }

    handleFocusOut(event) {
        const input = event.target.closest('input[data-row][data-property]');
        if (!input || (input.dataset.property !== 'quantite' && input.dataset.property !== 'prix_unitaire')) return;

        const property = input.dataset.property;
        const row = Number(input.dataset.row);
        const value = this.callbacks.parseNumber?.(input.value);
        const invalid = input.dataset.invalidInput === 'true' || value === null || value === undefined || value < 0;
        if (invalid) {
            input.value = this.formatEditableNumber(this.rows[row]?.[property], property);
            delete input.dataset.invalidInput;
            input.removeAttribute('aria-invalid');
        } else {
            input.value = this.formatEditableNumber(value, property);
            this.rows[row][property] = value;
        }
        input.dataset.committedValue = input.value;
    }

    handleKeyDown(event) {
        const vertical = ['ArrowUp', 'ArrowDown'].includes(event.key);
        const horizontal = event.key === 'Tab';
        if ((!vertical && !horizontal) || event.altKey || event.ctrlKey || event.metaKey
            || (event.shiftKey && !horizontal) || event.isComposing) return;

        const source = event.target;
        if (!source.matches('input:not([type="hidden"]), select, button, td.native-bdp-amount')) return;
        const row = source.closest('tr[data-row]');
        const cell = source.closest('td[data-row][data-column]');
        if (!row || !cell) return;

        const column = Number(cell.dataset.column);
        const visibleRows = Array.from(this.container.querySelectorAll('tbody tr[data-row]:not([hidden])'));
        const columns = [3, 4, 5, 6, 7, 8];
        let destinationRowIndex = visibleRows.indexOf(row);
        let destinationColumn = column;

        if (horizontal) {
            const columnIndex = columns.indexOf(column);
            const direction = event.shiftKey ? -1 : 1;
            const nextColumnIndex = columnIndex + direction;
            if (nextColumnIndex >= 0 && nextColumnIndex < columns.length) {
                destinationColumn = columns[nextColumnIndex];
            } else {
                destinationRowIndex += direction;
                if (destinationRowIndex < 0 || destinationRowIndex >= visibleRows.length) return;
                destinationColumn = direction > 0 ? columns[0] : columns[columns.length - 1];
            }
        } else {
            destinationRowIndex += event.key === 'ArrowUp' ? -1 : 1;
            if (destinationRowIndex < 0 || destinationRowIndex >= visibleRows.length) {
                event.preventDefault();
                return;
            }
        }

        const destinationCell = visibleRows[destinationRowIndex]
            ?.querySelector(`td[data-column="${destinationColumn}"]`);
        if (!destinationCell) return;

        const destination = destinationCell.querySelector(
            'input:not([type="hidden"]):not(:disabled), select:not(:disabled), button:not(:disabled):not([data-action="fold"])'
        ) || (destinationCell.matches('.native-bdp-amount') ? destinationCell : null);
        if (!destination) return;

        event.preventDefault();
        const start = source.selectionStart;
        const end = source.selectionEnd;
        const destinationRow = Number(visibleRows[destinationRowIndex].dataset.row);
        this.ranges = [this.createRange(
            { row: destinationRow, column: destinationColumn },
            { row: destinationRow, column: destinationColumn },
        )];
        this.anchorCell = { row: destinationRow, column: destinationColumn };
        this.activeCell = { row: destinationRow, column: destinationColumn };
        this.applySelection();
        this.callbacks.onSelectionChange?.();
        destination.focus({ preventScroll: true });
        if (typeof start === 'number' && typeof end === 'number'
            && typeof destination.selectionStart === 'number') {
            destination.setSelectionRange(start, end);
        }
        destination.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }

    handleContextMenu(event) {
        const rowElement = event.target.closest('tr[data-row]');
        if (!rowElement) return;
        event.preventDefault();
        const cell = event.target.closest('td[data-row][data-column]');
        const row = Number(rowElement.dataset.row);
        const column = cell ? Number(cell.dataset.column) : 4;
        this.closeContextMenu();
        this.selectCell(row, column);
        this.openContextMenu(event.clientX, event.clientY);
    }

    openContextMenu(x, y) {
        const menu = document.createElement('div');
        menu.className = 'native-bdp-context-menu';
        menu.setAttribute('role', 'menu');
        menu.setAttribute('aria-label', 'Actions sur la ligne du bordereau');
        let previousGroup;
        (this.callbacks.getRowActions?.() || []).forEach(action => {
            if (previousGroup !== undefined && action.group !== previousGroup) {
                const separator = document.createElement('div');
                separator.className = 'native-bdp-context-separator';
                separator.setAttribute('role', 'separator');
                menu.appendChild(separator);
            }
            previousGroup = action.group;
            const button = document.createElement('button');
            button.type = 'button';
            button.dataset.action = action.id;
            button.setAttribute('role', 'menuitem');
            button.disabled = !action.enabled;
            button.setAttribute('aria-disabled', String(!action.enabled));
            const icon = document.createElement('i');
            icon.className = action.icon;
            icon.setAttribute('aria-hidden', 'true');
            button.appendChild(icon);
            const label = document.createElement('span');
            label.textContent = action.label;
            button.appendChild(label);
            button.addEventListener('click', () => {
                this.closeContextMenu(true);
                this.callbacks.onRowAction?.(action.id);
            });
            menu.appendChild(button);
        });
        menu.addEventListener('contextmenu', event => event.preventDefault());
        menu.addEventListener('keydown', event => {
            if (event.key === 'Tab') {
                this.closeContextMenu(true);
                return;
            }
            if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
            event.preventDefault();
            const buttons = Array.from(menu.querySelectorAll('button:not(:disabled)'));
            if (!buttons.length) return;
            const current = buttons.indexOf(document.activeElement);
            const index = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
                : (current + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length;
            buttons[index].focus();
        });
        document.body.appendChild(menu);
        this.contextMenu = menu;
        const rect = menu.getBoundingClientRect();
        const cellRect = this.activeCell
            ? this.getCell(this.activeCell.row, this.activeCell.column)?.getBoundingClientRect() : null;
        const left = x || cellRect?.left || 8;
        const top = y || cellRect?.bottom || 8;
        menu.style.left = `${Math.max(8, Math.min(left, window.innerWidth - rect.width - 8))}px`;
        menu.style.top = `${Math.max(8, Math.min(top, window.innerHeight - rect.height - 8))}px`;
        menu.querySelector('button:not(:disabled)')?.focus();
    }

    closeContextMenu(restoreFocus = false) {
        if (!this.contextMenu) return;
        this.contextMenu.remove();
        this.contextMenu = null;
        if (restoreFocus && this.activeCell) {
            this.selectCell(this.activeCell.row, this.activeCell.column);
        }
    }

    selectFromClick(row, column, event) {
        const target = { row, column };
        if (event.shiftKey && this.anchorCell) {
            this.ranges = [this.createRange(this.anchorCell, target)];
        } else if (event.ctrlKey || event.metaKey) {
            this.ranges.push(this.createRange(target, target));
            this.anchorCell = target;
        } else {
            this.ranges = [this.createRange(target, target)];
            this.anchorCell = target;
        }
        this.activeCell = target;
        this.applySelection();
        this.callbacks.onSelectionChange?.();
    }

    createRange(start, end) {
        return {
            startRow: Math.min(start.row, end.row),
            startCol: Math.min(start.column, end.column),
            endRow: Math.max(start.row, end.row),
            endCol: Math.max(start.column, end.column),
            isSingleCell: start.row === end.row && start.column === end.column,
            nbRows: Math.abs(end.row - start.row) + 1,
        };
    }

    applySelection() {
        this.container.querySelectorAll('td[data-row][data-column]').forEach(cell => {
            const row = Number(cell.dataset.row);
            const column = Number(cell.dataset.column);
            const selected = this.ranges.some(range =>
                row >= range.startRow && row <= range.endRow
                && column >= range.startCol && column <= range.endCol
            );
            cell.classList.toggle('is-selected', selected);
            cell.classList.toggle('is-active', this.activeCell?.row === row && this.activeCell?.column === column);
        });
        this.container.querySelectorAll('tr[data-row]').forEach(row => {
            const rowIndex = Number(row.dataset.row);
            const selected = this.ranges.some(range =>
                rowIndex >= range.startRow && rowIndex <= range.endRow
            );
            row.setAttribute('aria-selected', String(selected));
            row.classList.toggle('is-current', this.activeCell?.row === rowIndex);
        });
    }

    getCell(row, column) {
        return this.container.querySelector(`td[data-row="${row}"][data-column="${column}"]`);
    }

    formatNumber(value, decimals) {
        const number = Number(value);
        if (!Number.isFinite(number)) return '';
        return number.toLocaleString('fr-FR', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        });
    }

    formatEditableNumber(value, property) {
        const number = Number(value);
        if (!Number.isFinite(number) || number === 0) return '';
        return this.formatNumber(number, property === 'quantite' ? 3 : 2);
    }

    getContrastingInk(color) {
        const backgrounds = color.flat ? color : [color];
        const parsed = backgrounds.map(value => {
            const match = /^#([0-9a-f]{6})$/i.exec(String(value || ''));
            return match ? [0, 2, 4].map(index => parseInt(match[1].slice(index, index + 2), 16)) : null;
        }).filter(Boolean);
        if (parsed.length === 0) return '#24485a';

        const luminance = channels => channels
            .map(channel => {
                channel /= 255;
                return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
            })
            .reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0);
        const contrast = (foreground, background) => {
            const first = luminance(foreground);
            const second = luminance(background);
            return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
        };
        const darkInk = [36, 72, 90];
        const lightInk = [248, 246, 239];
        const minimumContrast = ink => Math.min(...parsed.map(background => contrast(ink, background)));
        return minimumContrast(darkInk) >= minimumContrast(lightInk) ? '#24485a' : '#f8f6ef';
    }

    blendColor(foreground, background, opacity) {
        const parse = color => {
            const match = /^#([0-9a-f]{6})$/i.exec(String(color || ''));
            return match ? [0, 2, 4].map(index => parseInt(match[1].slice(index, index + 2), 16)) : null;
        };
        const foregroundRgb = parse(foreground);
        const backgroundRgb = parse(background);
        if (!foregroundRgb || !backgroundRgb) return background || '#f8f6ef';
        return `#${foregroundRgb.map((channel, index) => Math.round(
            channel * opacity + backgroundRgb[index] * (1 - opacity),
        ).toString(16).padStart(2, '0')).join('')}`;
    }
}

window.NativeBordereauTable = NativeBordereauTable;