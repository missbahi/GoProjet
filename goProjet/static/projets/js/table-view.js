/**
 * TableView: a dependency-free browser table prototype exposed as window.TableView.
 * Configure columns with key, label, width bounds, editable, and optional rendering,
 * parsing, validation, or editor callbacks. Options provide data and change callbacks.
 * Row objects are shared with the caller and updated in place; persistence and
 * application-specific rules remain the caller's responsibility.
 * With liveEdit enabled, onDataChange receives preview, commit, and rollback phases.
 * Configuration is serializable and memory-only; no storage or network is used.
 * Optional rowKey preserves identity across setData; selectionMode is single, range,
 * or multi. Hidden rows are excluded from navigation and selection values.
 * Hierarchy and rowActions are opt-in hooks; domain calculations remain outside.
 * Previews mutate shared rows; only the edited row refreshes automatically.
 * The application refreshes dependent rows. coalescePreview batches refresh/notification
 * once per animation frame, not mutation; commit flushes and rollback discards the batch.
 *
 * @typedef {Object} TableViewAppearance
 * @property {string} [rowColor='#f8f6ef'] Six-digit hex row background.
 * @property {string} [textColor='#24485a'] Cell text.
 * @property {string} [headerColor='#f0ede5'] Header background.
 * @property {string} [headerTextColor='#24485a'] Header text.
 * @property {string} [titleColor='#24485a'] Hierarchy group text.
 * @property {string} [amountColor='#15803d'] Amount text.
 * @property {string} [activeColor='#7baec1'] Active cell border.
 * @property {string} [selectionColor='#d8e2e4'] Selection background.
 * @property {string} [borderColor='#a9cad6'] Grid border.
 * @property {number} [rowHeight=26] Pixels, 22..80 when applying configuration.
 * @property {number} [headerHeight=42] Pixels, 28..100.
 * @property {number} [fontSize=13] Pixels, 10..24.
 * @property {boolean} [stickyHeader=true] Keep headers visible vertically.
 *
 * @typedef {Object} TableViewColumn
 * @property {string} key Unique row property name.
 * @property {string} [label] Header text; defaults to key.
 * @property {'text'|'number'} [type='text'] Built-in display/parser type.
 * @property {number} [width=160] Initial width, clamped to bounds.
 * @property {number} [minWidth=40] Positive minimum width.
 * @property {number} [maxWidth=1200] Maximum width >= minWidth.
 * @property {boolean} [editable] True opts in, false always forbids editing.
 * @property {boolean} [resizable=true] Enable pointer/keyboard resize and auto-size.
 * @property {boolean} [sortable=false] Enable stable header sorting.
 * @property {string} [group] Contiguous column group label.
 * @property {'left'|'center'|'right'} [align] Defaults to right for numbers, else left.
 * @property {string} [color] Cell foreground override.
 * @property {string} [background] Cell background override.
 * @property {string} [className] Space-separated CSS classes.
 * @property {number} [decimals=2] Display precision (0..10 in configuration).
 * @property {string} [locale] Overrides table locale.
 * @property {boolean} [useGrouping=true] Display thousands separators.
 * @property {boolean} [hideZero=false] Render zero as empty text.
 * @property {boolean} [allowEmpty=true] Accept empty editor values.
 * @property {function(Object, number): *} [getValue] Computed display/copy/sort value.
 * @property {function(*, Object, number): (Node|string)} [render] Custom display content.
 * @property {function(*, Object, number): *} [format] Display formatter if render absent.
 * @property {function(Object): HTMLElement} [editor] Receives {value,row,rowIndex,column}.
 * @property {function(HTMLElement): *} [getEditorValue] Read custom editor value.
 * @property {function(*): *} [parse] Synchronous parser for edits and pasted values.
 * @property {function(*, Object): (boolean|string|undefined)} [validate] Accept true/undefined,
 * reject false/message; context contains row, rowIndex, column, columnIndex, oldValue, value.
 *
 * @typedef {Object} TableViewHierarchy
 * @property {string} columnKey Column containing hierarchy controls.
 * @property {function(Object, number): boolean} isGroup Identify group rows.
 * @property {function(Object, number): number} [getLevel] Zero-based indentation;
 * required for hierarchy sorting, which expects a preorder flat list.
 * @property {function(Object, number): boolean} [isExpanded] Expansion state, defaults true.
 * @property {function(number, Object, TableView): void} [onToggle] Adapter owns descendant masks.
 *
 * @typedef {Object} TableViewAction
 * @property {string} id Unique action identifier.
 * @property {string} label Nonempty accessible label.
 * @property {string} [symbol] Inline button text, defaults to label.
 * @property {boolean} [enabled=true] Enable action.
 * @property {boolean} [inline=true] Show an inline button.
 * @property {string|number} [group] Context menu separator group.
 *
 * @typedef {Object} TableViewRowActions
 * @property {string} [columnKey] Inline action column; omit for menu-only actions.
 * @property {boolean} [contextMenu=false] Enable context menu.
 * @property {TableViewAction[]|function(Object): TableViewAction[]} [items=[]]
 * Context: {row,rowIndex,table,selection}.
 * @property {function(string, Object): void} [onAction] Action id and same context.
 *
 * @typedef {Object} TableViewClipboard
 * @property {boolean} [copy=false] Enable native copy on grid cells, not editors.
 * @property {boolean} [paste=false] Enable native paste on grid cells, not editors.
 * @property {boolean} [parseTsv=false] Parse quoted TSV rather than one raw cell.
 * @property {boolean} [includeHiddenRows=false] Paste through all flat-list rows.
 *
 * @typedef {Object} TableViewOptions
 * @property {TableViewColumn[]} columns Nonempty column definitions.
 * @property {Object[]} [data=[]] Shared, mutable row objects.
 * @property {string} [rowKey] Unique string/finite-number identity property.
 * @property {'single'|'range'|'multi'} [selectionMode='single'] Selection behavior.
 * @property {string} [label] Accessible grid label.
 * @property {string} [className] Classes added to scroll wrapper.
 * @property {string} [locale='en-US'] Default number/sort locale.
 * @property {boolean} [editable=true] Global edit permission.
 * @property {boolean} [editOnClick] Deprecated, ignored: click activates, double-click edits.
 * @property {boolean} [resizable=true] Global resize permission.
 * @property {boolean} [resizableHeader=false] Allow direct header height resizing.
 * @property {string} [headerResizeLabel] Accessible label for header resize handles.
 * @property {boolean} [liveEdit=false] Valid drafts immediately mutate shared rows.
 * @property {'none'|'raf'|boolean} [coalescePreview='none'] undefined/false/'none'
 * notify immediately; true/'raf' batch edited-row refresh and notification per frame.
 * @property {boolean} [omitNullValues=false] Exclude null/undefined from selected values.
 * @property {boolean} [viewport=true] Preserve scroll anchor on rebuild.
 * @property {number} [freezeColumns=0] Non-negative number of leading sticky columns.
 * @property {boolean|function(Object, number): string} [rowHeaders=false] Row position
 * numbers or custom text. Click selects the entire row; Shift extends, Ctrl/Cmd adds.
 * @property {number} [rowHeaderWidth=44] Positive row header width in pixels.
 * @property {boolean} [freezeRowHeaders=false] Freeze row headers horizontally,
 * independently of freezeColumns. Row headers are excluded from data/clipboard indexes.
 * @property {TableViewAppearance} [appearance] Presentation defaults/overrides.
 * @property {TableViewHierarchy} [hierarchy] Disabled with warning if columnKey is absent.
 * @property {TableViewRowActions} [rowActions] Disabled with warning if referenced column absent.
 * @property {TableViewClipboard} [clipboard] Clipboard permissions and parsing.
 * @property {function(Object, number): string} [rowClassName] Row CSS classes.
 * @property {function(Object): string} [cellClassName] {column,row,rowIndex} -> CSS classes.
 * @property {function(Object, number): boolean} [isRowEditable] False vetoes all row editing.
 * @property {function(Object): boolean} [isCellEditable] Opt-in for columns without editable;
 * receives {column,row,rowIndex}; never overrides explicit false.
 * @property {function(Object): boolean} [renderCell] {cell,column,row,rowIndex,table};
 * return true to replace content, core keeps styles and selection metadata.
 * @property {function(Object): *} [onCellChange] Synchronous final edit guard: false rejects,
 * undefined accepts, other values normalize. Must not mutate external state on rejection.
 * @property {function(Object): void} [onDataChange] Synchronous notification: preview/commit/rollback
 * use cell context; paste uses {changes,newRows,data,source,table}. Not a validation hook.
 * Exceptions are logged and alerted; accepted data is not rolled back.
 * @property {function(Object): void} [onDataChangeError] {error,event,table} after notification
 * failure; throwing here is logged without breaking editing.
 * @property {function(Object): void} [onValidationError] Cell context plus message.
 * @property {function(Object|null): void} [onSelectionChange] Active selected cell or null.
 * @property {function(Object): void} [onColumnResize] {column,columnIndex,width}, end of gesture.
 * @property {function(Object): void} [onHeaderResize] {height}, end of gesture.
 * @property {function(TableViewAppearance): void} [onAppearanceChange] Only actual global
 * appearance changes via setAppearance/applyConfiguration; excludes resize/columns.
 * @property {function(Object): void} [onConfigurationChange] Configuration snapshot after
 * applyConfiguration, setColumns, or resize; general persistence hook.
 * @property {function(Object): (void|boolean)} [onSort] Synchronous pre-apply order mirror:
 * {column,direction,rows}. TableView alone sorts. Mirror exact order in existing model;
 * do not sort/reparent/rebuild or call setData/sortBy. False rejects, exception propagates;
 * adapter must leave its model unchanged on rejection.
 * @property {function(Object): Object} [createRow] {rowIndex,table} -> fresh complete row
 * template including unique rowKey, hierarchy fields, numeric defaults and all properties
 * required by renderers/validators/getValue. No external side effects. Without it only
 * a minimal object (plus UUID rowKey) is supplied, suitable for simple sparse tables.
 * @property {function(Object): (void|boolean)} [onPaste] Atomic synchronous batch guard;
 * {changes,newRows,data,source,table}. No mutation on rejection; false/exception rejects.
 * @property {function(Error): void} [onClipboardError] Clipboard event failure notification.
 */
(function (global) {
    'use strict';

    const STYLE_ID = 'table-view-base-styles';
    let configurationSequence = 0;
    const APPEARANCE_DEFAULTS = {
        rowColor: '#f8f6ef', textColor: '#24485a', headerColor: '#f0ede5',
        headerTextColor: '#24485a', titleColor: '#24485a', amountColor: '#15803d',
        activeColor: '#7baec1', selectionColor: '#d8e2e4', borderColor: '#a9cad6',
        rowHeight: 26, headerHeight: 42, fontSize: 13, stickyHeader: true,
    };
    const COLOR_FIELDS = {
        rowColor: 'Row background', textColor: 'Cell text', headerColor: 'Header background',
        headerTextColor: 'Header text', titleColor: 'Title text', amountColor: 'Amount text',
        activeColor: 'Active cell border', selectionColor: 'Selected row background',
        borderColor: 'Grid borders',
    };
    const SIZE_FIELDS = {
        rowHeight: { label: 'Row height (px)', min: 22, max: 80 },
        headerHeight: { label: 'Header height (px)', min: 28, max: 100 },
        fontSize: { label: 'Font size (px)', min: 10, max: 24 },
    };

    // Install shared, class-scoped styles once for all TableView instances.
    function installBaseStyles() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = `
            .table-view-scroll { overflow: auto; max-width: 100%; }
            .table-view-table {
                border-collapse: collapse; table-layout: fixed;
                font-size: var(--tv-font-size); color: var(--tv-text-color);
            }
            .table-view-table th, .table-view-table td {
                box-sizing: border-box;
                border: 1px solid var(--tv-border-color);
                padding: 2px 6px;
                text-align: left;
                vertical-align: middle;
            }
            .table-view-table td { background: var(--tv-row-color); height: var(--tv-row-height); }
            .table-view-table td { user-select: none; }
            .table-view-table input, .table-view-table textarea { user-select: text; }
            .table-view-sort {
                border: 0; background: transparent; color: inherit; font: inherit;
                font-weight: inherit; cursor: pointer; padding: 0 12px 0 0;
            }
            .table-view-table .tv-frozen { position: sticky; }
            .table-view-table td.tv-frozen { z-index: 1; }
            .table-view-table th.tv-frozen { z-index: 4; }
            .table-view-table th {
                position: relative; height: var(--tv-header-height);
                background: var(--tv-header-color); color: var(--tv-header-text-color);
                font-weight: 700; text-align: center;
            }
            .table-view-table.has-sticky-header thead th { position: sticky; top: 0; z-index: 2; }
            .table-view-table tbody th.tv-row-header {
                height: var(--tv-row-height); user-select: none;
            }
            .table-view-table .tv-row-header button {
                border: 0; padding: 0; width: 100%; background: transparent;
                color: inherit; font: inherit; cursor: pointer;
            }
            .table-view-table .tv-row-header.is-selected { background: var(--tv-selection-color); }
            .table-view-table thead th.tv-frozen { z-index: 4; }
            .table-view-table tr.is-current > td { background: var(--tv-selection-color); }
            .table-view-table tr.is-title > td { color: var(--tv-title-color); font-weight: 700; }
            .table-view-table tr > td.is-amount { color: var(--tv-amount-color); font-weight: 600; }
            .table-view-table td.is-numeric {
                font-variant-numeric: tabular-nums; white-space: nowrap;
                overflow: hidden; text-overflow: ellipsis;
            }
            .table-view-table td.is-active {
                box-shadow: inset 0 0 0 2px var(--tv-active-color);
            }
            .table-view-table td.is-selected {
                background: var(--tv-selection-color);
                box-shadow: inset 0 0 0 1px var(--tv-active-color);
            }
            .table-view-table td.is-selected.is-active {
                box-shadow: inset 0 0 0 2px var(--tv-active-color);
            }
            .tv-hierarchy { display: flex; align-items: center; gap: 2px; min-width: 0; }
            .tv-hierarchy-content { flex: 1; min-width: 0; }
            .tv-fold, .tv-row-action {
                display: inline-grid; place-items: center; flex: 0 0 auto;
                width: 22px; height: 22px; padding: 0; border: 0; border-radius: 3px;
                background: transparent; color: var(--tv-active-color); cursor: pointer;
            }
            .tv-fold:hover, .tv-row-action:hover { background: rgba(14,165,233,.14); }
            .tv-fold-spacer { flex: 0 0 22px; }
            .tv-row-actions { display: inline-flex; gap: 2px; }
            .tv-context-menu {
                position: fixed; z-index: 10000; min-width: 220px;
                max-width: calc(100vw - 16px); max-height: calc(100dvh - 16px);
                overflow: auto; padding: 5px; border: 1px solid var(--tv-border-color);
                border-radius: 8px; background: var(--tv-row-color); color: var(--tv-text-color);
                box-shadow: 0 8px 24px rgba(0,0,0,.25);
            }
            .tv-context-menu button {
                display: flex; align-items: center; gap: 8px; width: 100%;
                padding: 8px 10px; border: 0; border-radius: 4px;
                background: transparent; color: inherit; font: inherit; text-align: left;
            }
            .tv-context-menu button:disabled { opacity: .4; }
            .tv-context-menu button:not(:disabled):hover,
            .tv-context-menu button:focus-visible {
                background: var(--tv-selection-color); outline: 2px solid var(--tv-active-color);
            }
            .tv-context-separator { margin: 4px 0; border-top: 1px solid var(--tv-border-color); }
            .table-view-resize-handle {
                position: absolute;
                z-index: 1;
                top: 0;
                right: 0;
                width: 10px;
                height: 100%;
                padding: 0;
                border: 0;
                background: transparent;
                cursor: col-resize;
                touch-action: none;
            }
            .table-view-resize-handle:focus-visible {
                outline: 2px solid #2563eb;
                outline-offset: -2px;
            }
            .table-view-header-resize-handle {
                position: absolute; z-index: 1; bottom: 0; left: 0; right: 10px;
                width: calc(100% - 10px); height: 8px; padding: 0; border: 0;
                background: transparent; cursor: row-resize; touch-action: none;
            }
            .table-view-header-resize-handle:focus-visible {
                outline: 2px solid #2563eb; outline-offset: -2px;
            }
            .table-view-editor {
                box-sizing: border-box; width: 100%; min-width: 0;
                padding: 3px 4px; border: 0; border-radius: 0;
                background: transparent; color: inherit; font: inherit; text-align: inherit;
            }
            .table-view-editor:focus { outline: none; }
            .table-view-editor[aria-invalid="true"] { outline: 2px solid #b91c1c; }
            .table-view-config { max-width: 760px; margin: 0 auto; color: #24485a; }
            .table-view-config fieldset {
                min-width: 0; margin: 0 0 24px; padding: 0;
                border: 1px solid #a9cad6; border-radius: 8px; background: #fff;
            }
            .table-view-config legend { padding: 0 8px; font-weight: 700; }
            .table-view-config .tv-config-tabs {
                display: flex; gap: 4px; overflow-x: auto; margin-bottom: 16px; padding: 4px;
            }
            .table-view-config .tv-config-tabs button {
                flex: 0 0 auto; padding: 7px 12px; border: 1px solid #a9cad6;
                border-radius: 5px; background: #f0ede5; color: inherit; font-size: 13px;
            }
            .table-view-config .tv-config-tabs button[aria-selected="true"] {
                background: #0369a1; color: #fff; border-color: #0369a1;
            }
            .table-view-config .tv-config-tabs button.is-modified::after { content: ' *'; }
            .table-view-config .tv-config-description {
                margin: 8px 14px; font-size: 13px; color: #527889;
            }
            .table-view-config .tv-config-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
            .table-view-config .tv-config-row td { padding: 10px 14px; border-top: 1px solid #eaebec; vertical-align: middle; }
            .table-view-config .tv-config-row td:first-child { width: 45%; border-left: 3px solid transparent; }
            .table-view-config .tv-config-row.is-modified td:first-child { border-left-color: #0ea5e9; }
            .table-view-config .tv-config-row.is-modified { border-left-color: #0ea5e9; }
            .table-view-config label {
                padding: 0; margin: 0; font-size: 13px; font-weight: 500;
                color: inherit; text-transform: none; letter-spacing: normal;
            }
            .table-view-config .tv-config-control {
                display: flex; flex-wrap: wrap; align-items: center; gap: 6px; min-width: 0;
            }
            .table-view-config input:not([type="checkbox"]), .table-view-config select {
                box-sizing: border-box; flex: 0 1 240px; min-width: 0; width: 240px; max-width: 100%;
                padding: 6px 8px; border: 1px solid #a9cad6; border-radius: 5px;
                background: #fffdf8; color: inherit; font: inherit; font-size: 13px;
            }
            .table-view-config input[type="number"] { flex-basis: 90px; width: 90px; }
            .table-view-config select,
            .table-view-config input[name$=".locale"],
            .table-view-config input[name$=".color"],
            .table-view-config input[name$=".background"] { flex-basis: 140px; width: 140px; }
            .table-view-config input[type="color"] {
                flex: 0 0 36px; width: 36px; height: 28px; padding: 2px; cursor: pointer;
            }
            .table-view-config input.tv-config-hex { flex: 0 0 auto; width: calc(7ch + 18px); font-family: Consolas, monospace; }
            .table-view-config input.tv-config-hex { color: #527889; }
            [data-theme="dark"] .table-view-config input.tv-config-hex { background: #243341; color: #aecbd6; }
            [data-theme="dark"] .table-view-config { color: #d5e4eb; }
            [data-theme="dark"] .table-view-config fieldset { background: #243341; border-color: #527889; }
            .table-view-config legend { color: inherit; }
            [data-theme="dark"] .table-view-config .tv-config-description { color: #aecbd6; }
            [data-theme="dark"] .table-view-config .tv-config-row td { border-top-color: #527889; }
            [data-theme="dark"] .table-view-config input:not([type="checkbox"]),
            [data-theme="dark"] .table-view-config select { background: #1c2935; color: #d5e4eb; }
            [data-theme="dark"] .table-view-config input.tv-config-hex { color: #aecbd6; }
            [data-theme="dark"] .table-view-config .tv-config-tabs button:not([aria-selected="true"]) { background: #243341; }
            .table-view-config [aria-invalid="true"] { outline: 2px solid #b91c1c; }
            .table-view-config button { font: inherit; cursor: pointer; }
            .table-view-config button:disabled { opacity: .5; cursor: not-allowed; }
            .table-view-config .tv-config-reset {
                flex: 0 0 28px; height: 28px; padding: 0; border: 0;
                border-radius: 5px; background: #f0ede5; color: #24485a;
            }
            .table-view-config [hidden] { display: none !important; }
            .table-view-config .tv-config-error {
                flex: 1 1 100%; margin: 0; font-size: 12px; color: #b91c1c;
            }
            .table-view-config .tv-config-error:empty { display: none; }
            .table-view-config .tv-config-actions {
                display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
                padding-top: 14px; border-top: 1px solid #a9cad6;
            }
            .table-view-config .tv-config-feedback { flex: 1 1 100%; margin: 0; font-size: 13px; }
            .table-view-config .tv-config-feedback.is-error { color: #b91c1c; }
            .table-view-config .tv-config-feedback.is-success { color: #15803d; }
            .table-view-config .tv-config-actions button {
                padding: 8px 14px; border: 1px solid #a9cad6; border-radius: 6px;
                background: #f0ede5; color: inherit;
            }
            .table-view-config .tv-config-actions button[type="submit"] {
                background: #0369a1; border-color: #0369a1; color: #fff;
            }
            @media (max-width: 600px) {
                .table-view-config .tv-config-row { grid-template-columns: minmax(0, 1fr); gap: 6px; }
                .table-view-config label { padding-top: 0; }
            }
        `;
        document.head.appendChild(style);
    }

    class TableView {
        handleContextMenu(event) {
            if (!this.options.rowActions?.contextMenu) return;
            const cell = event.target.closest('td[data-row][data-column], th[data-row-header]');
            if (!cell || !this.wrapper.contains(cell)) return;
            event.preventDefault();
            const rowIndex = Number(cell.dataset.row ?? cell.dataset.rowHeader);
            const columnIndex = Number(cell.dataset.column ?? 0);
            if (!this.finishEdit()) return;
            if (cell.dataset.rowHeader !== undefined) {
                if (!this.columns.every((column, index) => this.isSelected(rowIndex, index))) {
                    this.selectRowFromHeader(rowIndex, {});
                }
            } else if (!this.isSelected(rowIndex, columnIndex)) this.selectCell(rowIndex, columnIndex);
            this.openContextMenu(event.clientX, event.clientY, rowIndex);
        }
    
        // The floating menu receives this instance's CSS variables and owns its keyboard navigation.
        openContextMenu(x, y, rowIndex) {
            if (!Number.isInteger(rowIndex) || !this.data[rowIndex] || this.hiddenRows.has(rowIndex)) {
                throw new RangeError('A context menu requires a visible row.');
            }
            if (!this.finishEdit()) return;
            this.closeContextMenu();
            const actions = this.getRowActions(rowIndex);
            if (!actions.length) return;
            const menu = document.createElement('div');
            menu.className = 'tv-context-menu';
            menu.setAttribute('role', 'menu');
            menu.setAttribute('aria-label', 'Row actions');
            const styles = this.wrapper.querySelector('table').style;
            for (const key of styles) {
                if (key.startsWith('--tv-')) menu.style.setProperty(key, styles.getPropertyValue(key));
            }
            let previousGroup;
            actions.forEach(action => {
                if (previousGroup !== undefined && action.group !== previousGroup) {
                    const separator = document.createElement('div');
                    separator.className = 'tv-context-separator';
                    separator.setAttribute('role', 'separator');
                    menu.appendChild(separator);
                }
                previousGroup = action.group;
                const button = document.createElement('button');
                button.type = 'button';
                button.setAttribute('role', 'menuitem');
                button.textContent = action.label;
                button.disabled = action.enabled === false;
                button.addEventListener('click', () => {
                    const context = this.rowActionContext(rowIndex);
                    this.closeContextMenu(true);
                    this.options.rowActions.onAction?.(action.id, context);
                });
                menu.appendChild(button);
            });
            menu.addEventListener('contextmenu', event => event.preventDefault());
            menu.addEventListener('keydown', event => {
                if (event.key === 'Escape' || event.key === 'Tab') {
                    event.preventDefault();
                    event.stopPropagation();
                    this.closeContextMenu(true);
                    return;
                }
                if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
                event.preventDefault();
                const buttons = [...menu.querySelectorAll('button:not(:disabled)')];
                if (!buttons.length) return;
                const current = buttons.indexOf(document.activeElement);
                const index = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
                    : (current + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length;
                buttons[index].focus();
            });
            document.body.appendChild(menu);
            this.contextMenu = menu;
            const rect = menu.getBoundingClientRect();
            menu.style.left = `${Math.max(8, Math.min(x, window.innerWidth - rect.width - 8))}px`;
            menu.style.top = `${Math.max(8, Math.min(y, window.innerHeight - rect.height - 8))}px`;
            menu.querySelector('button:not(:disabled)')?.focus();
        }
    
        closeContextMenu(restoreFocus = false) {
            if (!this.contextMenu) return;
            this.contextMenu.remove();
            this.contextMenu = null;
            if (restoreFocus && this.activeCell) {
                this.getCell(this.activeCell.rowIndex, this.activeCell.columnIndex)?.focus({ preventScroll: true });
            }
        }
    
        // Validate column definitions, bind delegated events, and mount the initial table.
        /**
         * @param {HTMLElement} container Mounted table host.
         * @param {TableViewOptions} options Table configuration and synchronous hooks.
         */
        constructor(container, options = {}) {
            // Validate container and options before proceeding.
            if (!container || typeof container.replaceChildren !== 'function') {
                throw new TypeError('TableView requires a valid container element.');
            }
            if (!Array.isArray(options.columns) || options.columns.length === 0) {
                throw new TypeError('TableView requires at least one column.');
            }
            if (options.data !== undefined && !Array.isArray(options.data)) {
                throw new TypeError('TableView requires a data array.');
            }
            if (options.rowKey !== undefined
                && (typeof options.rowKey !== 'string' || !options.rowKey)) {
                throw new TypeError('rowKey must be a non-empty property name.');
            }
            if (options.selectionMode !== undefined
                && !['single', 'range', 'multi'].includes(options.selectionMode)) {
                throw new TypeError('selectionMode must be single, range, or multi.');
            }
            if (options.hierarchy && (typeof options.hierarchy.columnKey !== 'string'
                || typeof options.hierarchy.isGroup !== 'function')) {
                throw new TypeError('Hierarchy requires columnKey and isGroup.');
            }
            if (options.freezeColumns !== undefined
                && (!Number.isInteger(options.freezeColumns) || options.freezeColumns < 0)) {
                throw new TypeError('freezeColumns must be a non-negative integer.');
            }
            if (options.rowHeaders !== undefined && typeof options.rowHeaders !== 'boolean'
                && typeof options.rowHeaders !== 'function') {
                throw new TypeError('rowHeaders must be a boolean or a function.');
            }
            if (options.rowHeaderWidth !== undefined
                && (!Number.isFinite(options.rowHeaderWidth) || options.rowHeaderWidth <= 0)) {
                throw new TypeError('rowHeaderWidth must be a positive finite number.');
            }
            if (options.freezeRowHeaders !== undefined && typeof options.freezeRowHeaders !== 'boolean') {
                throw new TypeError('freezeRowHeaders must be a boolean.');
            }
            // Initialize instance properties with validated and defaulted values.
            this.container = container;
            this.columns = this.validateColumns(options.columns);
            this.data = options.data || [];
            const coalescePreview = options.coalescePreview;
            if (![undefined, false, true, 'none', 'raf'].includes(coalescePreview)) {
                throw new TypeError('coalescePreview must be "none", "raf", or a boolean.');
            }
            this.featureOptions = { hierarchy: options.hierarchy, rowActions: options.rowActions };
            this.rowHeaderRenderer = typeof options.rowHeaders === 'function' ? options.rowHeaders : null;
            this.options = this.optionsForColumns(this.columns, {
                ...options,
                coalescePreview: coalescePreview === true || coalescePreview === 'raf' ? 'raf' : 'none',
            });
            this.rowKey = options.rowKey || null;
            this.selectionMode = options.selectionMode || 'single';
            this.validateRows(this.data);
            this.appearance = { ...APPEARANCE_DEFAULTS, ...options.appearance };
            this.activeCell = this.data.length ? { rowIndex: 0, columnIndex: 0 } : null;
            this.anchorCell = this.activeCell ? { ...this.activeCell } : null;
            this.ranges = this.activeCell ? [this.createRange(this.activeCell, this.activeCell)] : [];
            this.hiddenRows = new Set();
            this.manualHiddenRows = new Set();
            this.filter = null;
            this.sortState = null;
            this.contextMenu = null;
            this.widths = new Map();
            this.cellClasses = new WeakMap();
            this.editing = null;
            this.previewFrame = null;
            this.pendingPreview = null;
            this.wrapper = document.createElement('div');
            this.wrapper.className = 'table-view-scroll';
            this.wrapper.classList.add(...String(options.className || '')
                .split(/\s+/).filter(Boolean));
            this.wrapper.addEventListener('click', event => this.handleClick(event));
            this.wrapper.addEventListener('pointerdown', event => {
                // Avoid a blur/change rebuild swallowing the click on a control in the edited row.
                if (this.editing && event.target.closest('[data-tv-action]')) event.preventDefault();
                this.startSelectionDrag(event);
            });
            this.wrapper.addEventListener('copy', event => this.handleCopy(event));
            this.wrapper.addEventListener('paste', event => this.handlePaste(event));
            this.wrapper.addEventListener('dblclick', event => this.handleDoubleClick(event));
            this.wrapper.addEventListener('keydown', event => this.handleKeyDown(event));
            this.wrapper.addEventListener('change', event => this.handleEditorChange(event));
            this.wrapper.addEventListener('contextmenu', event => this.handleContextMenu(event));
            this.wrapper.addEventListener('input', event => {
                const editor = event.target.closest('[data-table-view-editor]');
                if (editor && this.options.liveEdit) this.previewEdit(editor);
            });

            this.columns.forEach(column => {
                const width = Number(column.width);
                this.widths.set(column.key, this.clampWidth(
                    column, Number.isFinite(width) && width > 0 ? width : 160,
                ));
            });

            installBaseStyles();
            // Keep named listeners so destroy can remove them; register only after mounting succeeds.
            this._closeOutside = event => {
                if (this.contextMenu && !this.contextMenu.contains(event.target)) this.closeContextMenu();
            };
            this._closeOnScroll = event => {
                if (this.contextMenu && !this.contextMenu.contains(event.target)) this.closeContextMenu();
            };
            this._closeOnResize = () => this.closeContextMenu();
            this._closeOnEscape = event => {
                if (this.contextMenu && event.key === 'Escape') {
                    event.preventDefault();
                    this.closeContextMenu(true);
                }
            };
            this.container.replaceChildren(this.wrapper);
            this.render();
            document.addEventListener('pointerdown', this._closeOutside);
            document.addEventListener('scroll', this._closeOnScroll, true);
            document.addEventListener('keydown', this._closeOnEscape);
            window.addEventListener('resize', this._closeOnResize);
        }

        // Rebuild the table from current data, column widths, selection, and editing state.
        render() {
            this.stopSelectionDrag();
            this.closeContextMenu();
            const viewport = this.captureViewport();
            const oldEditor = this.wrapper.querySelector('[data-table-view-editor]');
            const draft = oldEditor && {
                editor: oldEditor,
                focused: document.activeElement === oldEditor,
            };
            const table = document.createElement('table');
            table.className = 'table-view-table';
            table.setAttribute('role', 'grid');
            const grouped = this.columns.some(column => column.group);
            const headerCount = grouped ? 2 : 1;
            table.setAttribute('aria-rowcount', String(this.data.length + headerCount));
            const rowHeaders = Boolean(this.options.rowHeaders);
            table.setAttribute('aria-colcount', String(this.columns.length + Number(rowHeaders)));
            if (this.selectionMode !== 'single') table.setAttribute('aria-multiselectable', 'true');
            table.classList.toggle('has-sticky-header', this.appearance.stickyHeader);
            Object.entries(this.appearance).forEach(([key, value]) => {
                if (key === 'stickyHeader') return;
                const name = key.replace(/[A-Z]/g, match => `-${match.toLowerCase()}`);
                table.style.setProperty(`--tv-${name}`, key in SIZE_FIELDS ? `${value}px` : value);
            });
            if (this.options.label) table.setAttribute('aria-label', this.options.label);
            const totalWidth = this.columns.reduce((total, column) =>
                total + this.getColumnWidth(column), rowHeaders ? this.options.rowHeaderWidth ?? 44 : 0);
            table.style.width = `${totalWidth}px`;

            const colgroup = document.createElement('colgroup');
            if (rowHeaders) {
                const col = document.createElement('col');
                col.style.width = `${this.options.rowHeaderWidth ?? 44}px`;
                colgroup.appendChild(col);
            }
            this.columns.forEach(column => {
                const col = document.createElement('col');
                col.style.width = `${this.getColumnWidth(column)}px`;
                colgroup.appendChild(col);
            });
            table.appendChild(colgroup);

            const thead = document.createElement('thead');
            if (grouped) {
                const groups = document.createElement('tr');
                groups.setAttribute('aria-rowindex', '1');
                if (rowHeaders) groups.appendChild(this.createRowHeaderCorner());
                this.columns.forEach((column, index) => {
                    const previous = this.columns[index - 1];
                    const boundary = index === (this.options.freezeColumns || 0);
                    if (index && !boundary && previous.group === column.group) {
                        groups.lastElementChild.colSpan++;
                    } else {
                        const th = document.createElement('th');
                        th.scope = 'colgroup';
                        th.dataset.groupStart = String(index);
                        th.textContent = column.group || '';
                        groups.appendChild(th);
                    }
                });
                thead.appendChild(groups);
            }
            const headerRow = document.createElement('tr');
            headerRow.setAttribute('aria-rowindex', String(headerCount));
            if (rowHeaders) headerRow.appendChild(this.createRowHeaderCorner());
            this.columns.forEach((column, index) => {
                const th = document.createElement('th');
                th.scope = 'col';
                th.dataset.column = String(index);
                th.setAttribute('aria-colindex', String(index + 1 + Number(rowHeaders)));
                const label = column.label == null ? column.key : String(column.label);
                if (column.sortable) {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'table-view-sort';
                    const direction = this.sortState?.key === column.key ? this.sortState.direction : null;
                    th.setAttribute('aria-sort', direction === 'asc' ? 'ascending'
                        : direction === 'desc' ? 'descending' : 'none');
                    button.textContent = label + (direction === 'asc' ? ' ▲' : direction === 'desc' ? ' ▼' : '');
                    th.appendChild(button);
                    th.addEventListener('click', event => {
                        if (!event.target.closest('.table-view-resize-handle, .table-view-header-resize-handle')) {
                            this.sortBy(column.key);
                        }
                    });
                } else th.textContent = label;
                if (column.resizable !== false && this.options.resizable !== false) {
                    th.appendChild(this.createResizeHandle(column, index));
                }
                if (this.options.resizableHeader) {
                    th.appendChild(this.createHeaderResizeHandle());
                }
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);

            const tbody = document.createElement('tbody');
            this.data.forEach((row, rowIndex) => {
                const tr = document.createElement('tr');
                tr.dataset.row = String(rowIndex);
                this.styleRow(tr, row, rowIndex);
                tr.hidden = this.hiddenRows.has(rowIndex);
                tr.setAttribute('aria-rowindex', String(rowIndex + headerCount + 1));
                if (rowHeaders) {
                    const header = document.createElement('th');
                    header.scope = 'row';
                    header.setAttribute('role', 'rowheader');
                    header.setAttribute('aria-colindex', '1');
                    header.dataset.rowHeader = String(rowIndex);
                    header.className = 'tv-row-header';
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.textContent = this.rowHeaderLabel(row, rowIndex);
                    button.setAttribute('aria-label', `Select row ${button.textContent}`);
                    button.addEventListener('click', event => this.selectRowFromHeader(rowIndex, event));
                    button.addEventListener('keydown', event => event.stopPropagation());
                    header.appendChild(button);
                    tr.appendChild(header);
                }
                this.columns.forEach((column, columnIndex) => {
                    const td = document.createElement('td');
                    td.dataset.row = String(rowIndex);
                    td.dataset.column = String(columnIndex);
                    td.tabIndex = this.isActive(rowIndex, columnIndex) ? 0 : -1;
                    td.setAttribute('role', 'gridcell');
                    td.setAttribute('aria-colindex', String(columnIndex + 1 + Number(rowHeaders)));
                    if (this.editing?.rowIndex === rowIndex
                        && this.editing.columnKey === column.key) {
                        if (draft) {
                            this.styleCell(td, column, row, rowIndex);
                            this.editorContainer(td, column, row, rowIndex).appendChild(draft.editor);
                        } else this.renderEditor(td, column, row, rowIndex);
                    } else {
                        this.renderCell(td, column, row, rowIndex);
                    }
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });
            table.appendChild(tbody);
            this.wrapper.replaceChildren(table);
            this.updateStickyColumns();
            this.applySelection();
            if (draft?.focused) draft.editor.focus({ preventScroll: true });
            this.restoreViewport(viewport);
        }

        styleRow(element, row, rowIndex) {
            element.className = this.options.rowClassName?.(row, rowIndex) || '';
            element.classList.toggle('is-current', this.activeCell?.rowIndex === rowIndex);
            if (this.options.hierarchy?.isGroup?.(row, rowIndex)) element.classList.add('is-title');
        }

        rowHeaderLabel(row, rowIndex) {
            return String(typeof this.options.rowHeaders === 'function'
                ? this.options.rowHeaders(row, rowIndex) : rowIndex + 1);
        }

        createRowHeaderCorner() {
            const corner = document.createElement('th');
            corner.className = 'tv-row-header-corner';
            corner.setAttribute('aria-colindex', '1');
            corner.setAttribute('aria-label', 'Row headers');
            return corner;
        }

        selectRowFromHeader(rowIndex, event) {
            if (this.hiddenRows.has(rowIndex) || !this.data[rowIndex] || !this.finishEdit()) return;
            const target = { rowIndex, columnIndex: 0 };
            const start = event.shiftKey && this.selectionMode !== 'single' && this.anchorCell
                ? this.anchorCell.rowIndex : rowIndex;
            const range = {
                startRow: Math.min(start, rowIndex), endRow: Math.max(start, rowIndex),
                startCol: 0, endCol: this.columns.length - 1,
            };
            this.ranges = this.selectionMode === 'multi' && (event.ctrlKey || event.metaKey)
                ? [...this.ranges, range] : [range];
            if (!event.shiftKey || this.selectionMode === 'single' || !this.anchorCell) {
                this.anchorCell = { ...target };
            }
            this.activeCell = target;
            this.applySelection();
            this.focusCell(rowIndex, 0);
            this.options.onSelectionChange?.(this.getSelectedCell());
        }

        // Prefer a custom renderer over formatting; strings are inserted as text, not HTML.
        renderCell(cell, column, row, rowIndex) {
            // Custom renderers replace content only; selection, styles and ARIA remain core-owned.
            cell.replaceChildren();
            const custom = this.options.renderCell?.({ cell, column, row, rowIndex, table: this });
            if (custom === true) {
                this.styleCell(cell, column, row, rowIndex);
                return;
            }
            if (column.key === this.options.rowActions?.columnKey) {
                this.renderRowActions(cell, row, rowIndex);
                this.styleCell(cell, column, row, rowIndex);
                return;
            }
            const value = typeof column.getValue === 'function'
                ? column.getValue(row, rowIndex) : row?.[column.key];
            const rendered = typeof column.render === 'function'
                ? column.render(value, row, rowIndex)
                : typeof column.format === 'function'
                    ? column.format(value, row, rowIndex)
                    : column.type === 'number' ? this.formatNumber(value, column)
                        : value == null ? '' : String(value);
            const content = column.key === this.options.hierarchy?.columnKey
                ? this.renderHierarchy(cell, row, rowIndex) : cell;
            if (rendered instanceof Node) content.appendChild(rendered);
            else content.textContent = rendered == null ? '' : String(rendered);
            if (this.isEditable(column, row, rowIndex)) {
                cell.dataset.editable = 'true';
            }
            this.styleCell(cell, column, row, rowIndex);
        }

        styleCell(cell, column, row, rowIndex) {
            const previous = this.cellClasses.get(cell) || [];
            cell.classList.remove(...previous);
            const cellClass = this.options.cellClassName?.({ column, row, rowIndex });
            const classes = [column.type === 'number' ? 'is-numeric' : '', column.className, cellClass]
                .filter(Boolean).flatMap(value => value.split(/\s+/).filter(Boolean));
            cell.classList.add(...classes);
            this.cellClasses.set(cell, classes);
            cell.style.textAlign = column.align || (column.type === 'number' ? 'right' : 'left');
            cell.style.color = column.color || '';
            cell.style.backgroundColor = column.background || '';
            if (this.isEditable(column, row, rowIndex)) cell.dataset.editable = 'true';
            else delete cell.dataset.editable;
        }

        renderHierarchy(cell, row, rowIndex) {
            const hierarchy = this.options.hierarchy;
            const wrap = document.createElement('div');
            wrap.className = 'tv-hierarchy';
            wrap.style.marginInlineStart =
                `${Math.max(0, hierarchy.getLevel?.(row, rowIndex) || 0) * 16}px`;
            const control = document.createElement(hierarchy.isGroup(row, rowIndex) ? 'button' : 'span');
            if (control.tagName === 'BUTTON') {
                const expanded = hierarchy.isExpanded?.(row, rowIndex) !== false;
                control.type = 'button';
                control.className = 'tv-fold';
                control.dataset.tvAction = 'fold';
                control.textContent = expanded ? '\u25be' : '\u25b8';
                control.setAttribute('aria-expanded', String(expanded));
                control.setAttribute('aria-label', expanded ? 'Collapse row' : 'Expand row');
                control.disabled = typeof hierarchy.onToggle !== 'function';
            } else control.className = 'tv-fold-spacer';
            const content = document.createElement('span');
            content.className = 'tv-hierarchy-content';
            wrap.append(control, content);
            cell.appendChild(wrap);
            return content;
        }

        rowActionContext(rowIndex) {
            return { rowIndex, row: this.data[rowIndex], table: this, selection: this.getSelection() };
        }

        getRowActions(rowIndex) {
            const items = this.options.rowActions?.items;
            const actions = typeof items === 'function' ? items(this.rowActionContext(rowIndex)) : items || [];
            if (!Array.isArray(actions)) throw new TypeError('Row actions must return an array.');
            const ids = new Set();
            actions.forEach(action => {
                if (!action || typeof action.id !== 'string' || !action.id
                    || typeof action.label !== 'string' || !action.label || ids.has(action.id)) {
                    throw new TypeError('Row actions require unique string ids and non-empty labels.');
                }
                ids.add(action.id);
            });
            return actions;
        }

        renderRowActions(cell, row, rowIndex) {
            const wrap = document.createElement('span');
            wrap.className = 'tv-row-actions';
            this.getRowActions(rowIndex).filter(action => action.inline !== false).forEach(action => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'tv-row-action';
                button.dataset.tvAction = 'row-action';
                button.dataset.actionId = action.id;
                button.setAttribute('aria-label', action.label);
                button.title = action.label;
                button.textContent = action.symbol || action.label;
                button.disabled = action.enabled === false;
                wrap.appendChild(button);
            });
            cell.appendChild(wrap);
        }

        // Intl handles grouping and decimal places; numeric editors use ungrouped localized text.
        formatNumber(value, column, editing = false) {
            if (value === null || value === undefined || value === '') return '';
            if (!Number.isFinite(Number(value))) {
                throw new TypeError(`Column "${column.key}" contains a non-finite numeric value.`);
            }
            if (!editing && column.hideZero && Number(value) === 0) return '';
            return new Intl.NumberFormat(column.locale || this.options.locale || 'en-US', {
                useGrouping: !editing && column.useGrouping !== false,
                minimumFractionDigits: editing ? 0 : (column.decimals ?? 2),
                maximumFractionDigits: editing ? 20 : (column.decimals ?? 2),
            }).format(Number(value));
        }

        // Accept locale separators (including French narrow spaces) without accepting partial numbers.
        parseNumber(value, column) {
            const text = String(value).trim();
            if (!text) return '';
            const parts = new Intl.NumberFormat(column.locale || this.options.locale || 'en-US')
                .formatToParts(12345.6);
            const group = parts.find(part => part.type === 'group')?.value;
            const decimal = parts.find(part => part.type === 'decimal')?.value || '.';
            let normalized = text.replace(/[\s\u00a0\u202f]/g, '');
            if (group && !/\s/.test(group)) normalized = normalized.split(group).join('');
            normalized = normalized.split(decimal).join('.');
            return /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(normalized)
                ? Number(normalized) : NaN;
        }

        editorContainer(cell, column, row, rowIndex) {
            return column.key === this.options.hierarchy?.columnKey
                ? this.renderHierarchy(cell, row, rowIndex) : cell;
        }

        // Keep hierarchy controls outside both default and custom editors.
        renderEditor(cell, column, row, rowIndex) {
            this.styleCell(cell, column, row, rowIndex);
            const value = row == null ? '' : row[column.key];
            const context = { value, row, rowIndex, column };
            const editor = typeof column.editor === 'function'
                ? column.editor(context)
                : document.createElement('input');
            if (!(editor instanceof HTMLElement)) {
                throw new TypeError(`The editor for column "${column.key}" must be an HTML element.`);
            }
            if (editor instanceof HTMLInputElement && !column.editor) {
                editor.type = 'text';
                editor.value = column.type === 'number'
                    ? this.formatNumber(value, column, true) : value == null ? '' : String(value);
                if (column.type === 'number') editor.inputMode = 'decimal';
            }
            editor.classList.add('table-view-editor');
            editor.dataset.tableViewEditor = 'true';
            editor.setAttribute('aria-label', column.label || column.key);
            this.editorContainer(cell, column, row, rowIndex).appendChild(editor);
        }

        // Support pointer dragging and 10-pixel keyboard steps within the column's bounds.
        createResizeHandle(column, columnIndex) {
            const handle = document.createElement('button');
            handle.type = 'button';
            handle.className = 'table-view-resize-handle';
            handle.setAttribute('aria-label', `Resize column ${column.label || column.key}`);
            handle.title = 'Drag to resize';
            handle.addEventListener('dblclick', event => {
                event.preventDefault();
                event.stopPropagation();
                this.autoSizeColumn(columnIndex);
            });
            handle.addEventListener('pointerdown', event => {
                if (event.button !== 0) return;
                event.preventDefault();
                const startX = event.clientX;
                const startWidth = this.getColumnWidth(column);
                const onMove = moveEvent => {
                    const nextWidth = this.clampWidth(column, startWidth + moveEvent.clientX - startX);
                    this.widths.set(column.key, nextWidth);
                    this.updateColumnWidth(columnIndex, nextWidth);
                };
                const onUp = () => {
                    handle.removeEventListener('pointermove', onMove);
                    handle.removeEventListener('pointerup', onUp);
                    handle.removeEventListener('pointercancel', onUp);
                    if (typeof this.options.onColumnResize === 'function') {
                        this.options.onColumnResize({
                            column,
                            columnIndex,
                            width: this.getColumnWidth(column),
                        });
                    }
                    this.options.onConfigurationChange?.(this.getConfiguration());
                };
                handle.addEventListener('pointermove', onMove);
                handle.addEventListener('pointerup', onUp);
                handle.addEventListener('pointercancel', onUp);
                handle.setPointerCapture(event.pointerId);
            });
            handle.addEventListener('keydown', event => {
                if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
                event.preventDefault();
                event.stopPropagation();
                const delta = event.key === 'ArrowRight' ? 10 : -10;
                const width = this.clampWidth(column, this.getColumnWidth(column) + delta);
                this.widths.set(column.key, width);
                this.updateColumnWidth(columnIndex, width);
                if (typeof this.options.onColumnResize === 'function') {
                    this.options.onColumnResize({ column, columnIndex, width });
                }
                this.options.onConfigurationChange?.(this.getConfiguration());
            });
            return handle;
        }

        createHeaderResizeHandle() {
            const handle = document.createElement('button');
            handle.type = 'button';
            handle.className = 'table-view-header-resize-handle';
            const label = this.options.headerResizeLabel || 'Resize header height';
            handle.setAttribute('aria-label', label);
            handle.title = label;
            const setHeight = value => {
                const { min, max } = SIZE_FIELDS.headerHeight;
                const height = Math.max(min, Math.min(max, Math.round(value)));
                this.appearance.headerHeight = height;
                this.wrapper.querySelector('table').style.setProperty('--tv-header-height', `${height}px`);
                this.updateStickyColumns();
            };
            const notify = previous => {
                if (previous === this.appearance.headerHeight) return;
                this.options.onHeaderResize?.({ height: this.appearance.headerHeight });
                this.options.onConfigurationChange?.(this.getConfiguration());
            };
            handle.addEventListener('click', event => event.stopPropagation());
            handle.addEventListener('dblclick', event => event.stopPropagation());
            handle.addEventListener('pointerdown', event => {
                if (event.button !== 0) return;
                event.preventDefault();
                event.stopPropagation();
                const startY = event.clientY;
                const previous = this.appearance.headerHeight;
                const onMove = move => setHeight(previous + move.clientY - startY);
                const finish = cancelled => {
                    handle.removeEventListener('pointermove', onMove);
                    handle.removeEventListener('pointerup', onUp);
                    handle.removeEventListener('pointercancel', onCancel);
                    if (cancelled) setHeight(previous);
                    else notify(previous);
                };
                const onUp = () => finish(false);
                const onCancel = () => finish(true);
                handle.addEventListener('pointermove', onMove);
                handle.addEventListener('pointerup', onUp);
                handle.addEventListener('pointercancel', onCancel);
                handle.setPointerCapture(event.pointerId);
            });
            handle.addEventListener('keydown', event => {
                if (!['ArrowUp', 'ArrowDown'].includes(event.key)) return;
                event.preventDefault();
                event.stopPropagation();
                const previous = this.appearance.headerHeight;
                setHeight(previous + (event.key === 'ArrowDown' ? 1 : -1));
                notify(previous);
            });
            return handle;
        }

        // Update layout without rebuilding rows or interrupting the resize gesture.
        updateColumnWidth(columnIndex, width) {
            const table = this.wrapper.querySelector('table');
            const col = table?.querySelectorAll('col')[columnIndex + Number(Boolean(this.options.rowHeaders))];
            if (!table || !col) return;
            col.style.width = `${width}px`;
            table.style.width = `${this.columns.reduce((total, column) =>
                total + this.getColumnWidth(column),
                this.options.rowHeaders ? this.options.rowHeaderWidth ?? 44 : 0)}px`;
            this.updateStickyColumns();
        }

        updateStickyColumns() {
            const offsets = [];
            let left = this.options.rowHeaders && this.options.freezeRowHeaders
                ? this.options.rowHeaderWidth ?? 44 : 0;
            this.wrapper.querySelectorAll('.tv-row-header, .tv-row-header-corner').forEach(cell => {
                cell.classList.toggle('tv-frozen', this.options.freezeRowHeaders === true);
                cell.style.left = this.options.freezeRowHeaders ? '0px' : '';
            });
            this.columns.forEach(column => {
                offsets.push(left);
                left += this.getColumnWidth(column);
            });
            const count = Math.min(this.options.freezeColumns || 0, this.columns.length);
            this.wrapper.querySelectorAll('td[data-column], th[data-column], th[data-group-start]')
                .forEach(cell => {
                    const index = Number(cell.dataset.column ?? cell.dataset.groupStart);
                    cell.classList.toggle('tv-frozen', index < count);
                    cell.style.left = index < count ? `${offsets[index]}px` : '';
                });
            const headers = this.wrapper.querySelectorAll('thead tr');
            if (headers.length === 2) {
                const height = headers[0].getBoundingClientRect().height;
                headers[1].querySelectorAll('th').forEach(cell => {
                    cell.style.top = this.appearance.stickyHeader ? `${height}px` : '';
                });
            }
        }

        autoSizeColumn(columnIndex) {
            const column = this.columns[columnIndex];
            if (!column) throw new RangeError('Unknown column.');
            const probe = document.createElement('div');
            probe.style.cssText = 'position:fixed;left:-100000px;top:0;width:max-content;visibility:hidden;';
            document.body.appendChild(probe);
            let width = 0;
            try {
                this.wrapper.querySelectorAll(`[data-column="${columnIndex}"]`).forEach(cell => {
                    if (cell.closest('tr')?.hidden) return;
                    const clone = cell.cloneNode(true);
                    const style = getComputedStyle(cell);
                    clone.style.cssText = `display:block;position:static;width:max-content;max-width:none;white-space:pre;font:${style.font};padding:${style.padding};border:0;`;
                    clone.querySelectorAll('.table-view-resize-handle').forEach(handle => handle.remove());
                    clone.querySelectorAll('input,textarea,select').forEach(editor => {
                        editor.replaceWith(document.createTextNode(editor.value));
                    });
                    probe.replaceChildren(clone);
                    width = Math.max(width, clone.getBoundingClientRect().width + 12);
                });
            } finally { probe.remove(); }
            const next = this.clampWidth(column, Math.ceil(width));
            this.widths.set(column.key, next);
            this.updateColumnWidth(columnIndex, next);
            this.options.onColumnResize?.({ column, columnIndex, width: next });
            this.options.onConfigurationChange?.(this.getConfiguration());
        }

        startSelectionDrag(event) {
            if (event.button === 0) this.suppressClick = false;
            if (event.button !== 0 || this.selectionMode === 'single'
                || event.target.closest('input,textarea,select,button,[data-table-view-editor]')) return;
            const cell = event.target.closest('td[data-row][data-column]');
            if (!cell) return;
            const start = { rowIndex: Number(cell.dataset.row), columnIndex: Number(cell.dataset.column) };
            event.preventDefault();
            if (!this.finishEdit()) return;
            this.stopSelectionDrag();
            this.suppressClick = false;
            const anchor = event.shiftKey && this.anchorCell ? { ...this.anchorCell } : start;
            const base = (event.ctrlKey || event.metaKey) && this.selectionMode === 'multi'
                ? this.ranges.map(range => ({ ...range })) : [];
            const move = next => {
                if (next.pointerId !== event.pointerId) return;
                if (!this.dragging && Math.hypot(next.clientX - event.clientX, next.clientY - event.clientY) < 4) return;
                const target = document.elementFromPoint(next.clientX, next.clientY)
                    ?.closest('td[data-row][data-column]');
                if (!target || !this.wrapper.contains(target)) return;
                this.dragging = true;
                this.suppressClick = true;
                next.preventDefault();
                this.activeCell = {
                    rowIndex: Number(target.dataset.row), columnIndex: Number(target.dataset.column),
                };
                this.anchorCell = anchor;
                this.ranges = [...base, this.createRange(anchor, this.activeCell)];
                this.applySelection();
                this.getCell(this.activeCell.rowIndex, this.activeCell.columnIndex)?.focus({ preventScroll: true });
                this.options.onSelectionChange?.(this.getSelectedCell());
            };
            const end = next => {
                if (next.pointerId === event.pointerId) this.stopSelectionDrag();
            };
            this.dragCleanup = () => {
                document.removeEventListener('pointermove', move);
                document.removeEventListener('pointerup', end);
                document.removeEventListener('pointercancel', end);
            };
            document.addEventListener('pointermove', move, { passive: false });
            document.addEventListener('pointerup', end);
            document.addEventListener('pointercancel', end);
        }

        stopSelectionDrag() {
            this.dragCleanup?.();
            this.dragCleanup = null;
            this.dragging = false;
        }

        getColumnWidth(column) {
            return this.widths.get(column.key);
        }

        clampWidth(column, width) {
            const min = Number.isFinite(Number(column.minWidth)) ? Number(column.minWidth) : 40;
            const max = Number.isFinite(Number(column.maxWidth)) ? Number(column.maxWidth) : 1200;
            return Math.max(min, Math.min(max, width));
        }

        // Global and column-level read-only flags take priority over editability callbacks.
        isEditable(column, row, rowIndex, includeHidden = false) {
            if (!column || !row || (!includeHidden && this.hiddenRows.has(rowIndex))) return false;
            if (this.options.isRowEditable?.(row, rowIndex) === false) return false;
            if (column.key === this.options.rowActions?.columnKey) return false;
            return this.options.editable !== false
                && column.editable !== false
                && (column.editable === true
                    || typeof column.editor === 'function'
                    || (typeof this.options.isCellEditable === 'function'
                        && this.options.isCellEditable({ column, row, rowIndex })));
        }

        isActive(rowIndex, columnIndex) {
            return this.activeCell?.rowIndex === rowIndex
                && this.activeCell?.columnIndex === columnIndex;
        }

        handleClick(event) {
            if (this.suppressClick) {
                this.suppressClick = false;
                event.preventDefault();
                return;
            }
            if (event.target.closest('[data-table-view-editor]')) return;
            const cell = event.target.closest('td[data-row][data-column]');
            if (!cell || !this.wrapper.contains(cell)) return;
            const rowIndex = Number(cell.dataset.row);
            const columnIndex = Number(cell.dataset.column);
            if (this.editing) {
                const editor = this.wrapper.querySelector('[data-table-view-editor]');
                if (!this.commitEdit(editor)) return;
            }
            const control = event.target.closest('[data-tv-action]');
            if (control) {
                event.preventDefault();
                this.selectCell(rowIndex, columnIndex);
                if (control.dataset.tvAction === 'fold') {
                    this.options.hierarchy.onToggle(rowIndex, this.data[rowIndex], this);
                } else this.options.rowActions.onAction?.(
                    control.dataset.actionId, this.rowActionContext(rowIndex),
                );
                return;
            }
            this.selectFromClick(rowIndex, columnIndex, event);
            this.focusCell(rowIndex, columnIndex);
        }

        handleDoubleClick(event) {
            if (event.target.closest('[data-table-view-editor], [data-tv-action]')) return;
            const cell = event.target.closest('td[data-row][data-column]');
            if (!cell || !this.wrapper.contains(cell)) return;
            const rowIndex = Number(cell.dataset.row);
            const columnIndex = Number(cell.dataset.column);
            if (!this.finishEdit()) return;
            if (this.isEditable(this.columns[columnIndex], this.data[rowIndex], rowIndex)) {
                this.selectCell(rowIndex, columnIndex);
                this.startEdit(rowIndex, columnIndex);
            }
        }

        // Keep editor shortcuts separate from cell navigation and column resize controls.
        handleKeyDown(event) {
            if (event.target.closest('.table-view-resize-handle')) return;
            if (event.target.closest('[data-tv-action]')) return;
            const editor = event.target.closest('[data-table-view-editor]');
            if (editor) {
                if (event.key === 'Escape') {
                    event.preventDefault();
                    this.cancelEdit();
                } else if (event.key === 'Enter' && editor.tagName !== 'TEXTAREA') {
                    event.preventDefault();
                    this.commitEdit(editor);
                } else if (event.key === 'Tab') {
                    event.preventDefault();
                    const { rowIndex, columnKey } = this.editing;
                    const columnIndex = this.columns.findIndex(column => column.key === columnKey);
                    if (this.commitEdit(editor)) {
                        const visible = this.visibleRowIndexes();
                        const next = visible.indexOf(rowIndex) * this.columns.length + columnIndex
                            + (event.shiftKey ? -1 : 1);
                        if (next >= 0 && next < visible.length * this.columns.length) {
                            this.selectCell(visible[Math.floor(next / this.columns.length)],
                                next % this.columns.length, true);
                        }
                    }
                }
                return;
            }

            if (!this.activeCell) return;
            const { rowIndex, columnIndex } = this.activeCell;
            if (event.key === 'ContextMenu' || (event.key === 'F10' && event.shiftKey)) {
                if (this.options.rowActions?.contextMenu) {
                    event.preventDefault();
                    const rect = this.getCell(rowIndex, columnIndex).getBoundingClientRect();
                    this.openContextMenu(rect.left, rect.bottom, rowIndex);
                }
                return;
            }
            const visible = this.visibleRowIndexes();
            const position = visible.indexOf(rowIndex);
            let nextRow = rowIndex;
            let nextColumn = columnIndex;
            if (event.key === 'ArrowUp') nextRow = visible[position - 1];
            else if (event.key === 'ArrowDown') nextRow = visible[position + 1];
            else if (event.key === 'ArrowLeft') nextColumn--;
            else if (event.key === 'ArrowRight') nextColumn++;
            else if (event.key === 'Home') nextColumn = 0;
            else if (event.key === 'End') nextColumn = this.columns.length - 1;
            else if (event.key === 'Enter' || event.key === 'F2') {
                const column = this.columns[columnIndex];
                if (this.isEditable(column, this.data[rowIndex], rowIndex)) {
                    event.preventDefault();
                    this.startEdit(rowIndex, columnIndex);
                }
                return;
            } else if (Array.from(event.key).length === 1
                && !event.ctrlKey && !event.metaKey && !event.altKey && !event.isComposing
                && event.target.closest('td[data-row][data-column]')) {
                const column = this.columns[columnIndex];
                if (!this.isEditable(column, this.data[rowIndex], rowIndex)) return;
                event.preventDefault();
                this.startEdit(rowIndex, columnIndex);
                const input = this.wrapper.querySelector('[data-table-view-editor]');
                if (input instanceof HTMLTextAreaElement
                    || (input instanceof HTMLInputElement
                        && ['text', 'search', 'tel', 'url', 'password'].includes(input.type))) {
                    input.value = event.key;
                    input.setSelectionRange(input.value.length, input.value.length);
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
                return;
            } else return;

            event.preventDefault();
            if (nextRow === undefined || nextRow < 0 || nextRow >= this.data.length
                || nextColumn < 0 || nextColumn >= this.columns.length) return;
            if (event.shiftKey && this.selectionMode !== 'single') {
                this.selectFromClick(nextRow, nextColumn, { shiftKey: true });
                this.focusCell(nextRow, nextColumn);
                return;
            }
            this.selectCell(nextRow, nextColumn, true);
        }

        handleEditorChange(event) {
            const editor = event.target.closest('[data-table-view-editor]');
            if (editor) this.commitEdit(editor);
        }

        // Maintain a single active cell, update keyboard focusability, and notify the caller.
        selectCell(rowIndex, columnIndex, focus = false) {
            if (!this.data[rowIndex] || !this.columns[columnIndex] || this.hiddenRows.has(rowIndex)) return;
            if (this.editing && (rowIndex !== this.editing.rowIndex
                || this.columns[columnIndex].key !== this.editing.columnKey) && !this.finishEdit()) return;
            this.activeCell = { rowIndex, columnIndex };
            this.anchorCell = { ...this.activeCell };
            this.ranges = [this.createRange(this.activeCell, this.activeCell)];
            this.applySelection();
            if (focus) this.focusCell(rowIndex, columnIndex);
            this.options.onSelectionChange?.(this.getSelectedCell());
        }

        createRange(start, end) {
            return {
                startRow: Math.min(start.rowIndex, end.rowIndex),
                endRow: Math.max(start.rowIndex, end.rowIndex),
                startCol: Math.min(start.columnIndex, end.columnIndex),
                endCol: Math.max(start.columnIndex, end.columnIndex),
            };
        }

        isSelected(rowIndex, columnIndex) {
            return !this.hiddenRows.has(rowIndex) && this.ranges.some(range =>
                rowIndex >= range.startRow && rowIndex <= range.endRow
                && columnIndex >= range.startCol && columnIndex <= range.endCol);
        }

        selectFromClick(rowIndex, columnIndex, event = {}) {
            if (!this.data[rowIndex] || !this.columns[columnIndex] || this.hiddenRows.has(rowIndex)) return;
            if (!this.finishEdit()) return;
            if (this.selectionMode === 'single') return this.selectCell(rowIndex, columnIndex);
            const target = { rowIndex, columnIndex };
            if (event.shiftKey && this.anchorCell) {
                this.ranges = [this.createRange(this.anchorCell, target)];
            } else if (this.selectionMode === 'multi' && (event.ctrlKey || event.metaKey)) {
                this.ranges.push(this.createRange(target, target));
                this.anchorCell = target;
            } else {
                this.ranges = [this.createRange(target, target)];
                this.anchorCell = target;
            }
            this.activeCell = target;
            this.applySelection();
            this.options.onSelectionChange?.(this.getSelectedCell());
        }

        applySelection() {
            this.wrapper.querySelectorAll('tbody tr').forEach((row, index) => {
                this.applyRowSelection(row, index);
            });
        }

        applyRowSelection(row, rowIndex) {
            const header = row.querySelector('[data-row-header]');
            if (header) {
                const selected = this.columns.every((column, index) => this.isSelected(rowIndex, index));
                header.setAttribute('aria-selected', String(selected));
                header.classList.toggle('is-selected', selected);
            }
            row.querySelectorAll('td[data-column]').forEach(cell => {
                const active = this.isActive(rowIndex, Number(cell.dataset.column));
                const selected = this.isSelected(rowIndex, Number(cell.dataset.column));
                cell.classList.toggle('is-active', active);
                cell.classList.toggle('is-selected', selected);
                cell.tabIndex = active ? 0 : -1;
                cell.setAttribute('aria-selected', String(selected));
            });
            row.classList.toggle('is-current', rowIndex === this.activeCell?.rowIndex);
        }

        getCell(rowIndex, columnIndex) {
            return this.wrapper.querySelector(
                `td[data-row="${rowIndex}"][data-column="${columnIndex}"]`,
            );
        }

        focusCell(rowIndex, columnIndex) {
            const cell = this.getCell(rowIndex, columnIndex);
            cell?.focus({ preventScroll: true });
            cell?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        }

        finishEdit() {
            return !this.editing || this.commitEdit(this.wrapper.querySelector('[data-table-view-editor]'));
        }

        visibleRowIndexes() {
            return this.data.map((row, index) => index).filter(index => !this.hiddenRows.has(index));
        }

        // Enter edit mode only when the column and application rules allow it.
        startEdit(rowIndex, columnIndex) {
            const column = this.columns[columnIndex];
            const row = this.data[rowIndex];
            if (!this.isEditable(column, row, rowIndex)) return;
            if (this.editing) {
                if (this.editing.rowIndex === rowIndex && this.editing.columnKey === column.key) return;
                if (!this.finishEdit()) return;
            }
            if (!this.isActive(rowIndex, columnIndex)) this.selectCell(rowIndex, columnIndex);
            this.editing = { rowIndex, columnKey: column.key, originalValue: row[column.key] };
            const cell = this.getCell(rowIndex, columnIndex);
            cell.replaceChildren();
            this.renderEditor(cell, column, row, rowIndex);
            const editor = cell.querySelector('[data-table-view-editor]');
            editor.focus({ preventScroll: true });
            if (editor instanceof HTMLInputElement) editor.select();
        }

        // Validate previews without invoking the commit hook or replacing the active editor.
        readEdit(editor) {
            const { rowIndex, columnKey, originalValue } = this.editing;
            const column = this.columns.find(item => item.key === columnKey);
            const row = this.data[rowIndex];
            let value = typeof column.getEditorValue === 'function'
                ? column.getEditorValue(editor) : editor.value;
            if (typeof column.parse === 'function') value = column.parse(value);
            else if (column.type === 'number') value = this.parseNumber(value, column);
            const context = {
                row, rowIndex, column, columnIndex: this.columns.indexOf(column),
                oldValue: originalValue, value,
            };
            const validation = this.validateValue(value, context);
            if (validation !== true && validation !== undefined) {
                this.rejectEdit(editor, context, typeof validation === 'string'
                    ? validation : 'This value is not allowed.');
                return null;
            }
            editor.removeAttribute('aria-invalid');
            editor.removeAttribute('title');
            return context;
        }

        validateValue(value, context) {
            const { column } = context;
            return column.allowEmpty === false && (value === '' || value === null || value === undefined)
                ? 'This value cannot be empty.'
                : column.type === 'number' && value !== '' && !Number.isFinite(value)
                ? 'Enter a finite number.'
                : typeof column.validate === 'function' ? column.validate(value, context) : true;
        }

        rejectEdit(editor, context, message) {
            editor.setAttribute('aria-invalid', 'true');
            editor.setAttribute('title', message);
            this.options.onValidationError?.({ ...context, message });
        }

        // Derived cell renderers and totals see the latest valid preview; invalid text stays editable.
        previewEdit(editor) {
            if (!this.editing) return;
            const context = this.readEdit(editor);
            if (!context) return;
            context.row[context.column.key] = context.value;
            this.pendingPreview = context;
            if (this.options.coalescePreview === 'none') {
                this.flushPreview();
            } else if (this.previewFrame === null) {
                this.previewFrame = global.requestAnimationFrame(() => this.flushPreview());
            }
        }

        discardPreview() {
            if (this.previewFrame !== null) global.cancelAnimationFrame(this.previewFrame);
            this.previewFrame = null;
            this.pendingPreview = null;
        }

        flushPreview() {
            const context = this.pendingPreview;
            this.discardPreview();
            if (!context) return;
            this.refreshRow(context.rowIndex);
            this.notifyDataChange({ ...context, phase: 'preview' });
        }

        // Notification failure cannot undo accepted data or arbitrary external side effects.
        notifyDataChange(event) {
            try {
                this.options.onDataChange?.(event);
                this.container.querySelector('[data-tv-data-status]')?.remove();
            } catch (error) {
                console.error(`TableView onDataChange failed (${event.phase}).`, error);
                let status = this.container.querySelector('[data-tv-data-status]');
                if (!status) {
                    status = document.createElement('p');
                    status.dataset.tvDataStatus = 'true';
                    status.setAttribute('role', 'alert');
                    this.container.appendChild(status);
                }
                status.textContent = `Data notification failed (${event.phase}). The application may be out of sync.`;
                try {
                    this.options.onDataChangeError?.({ error, event, table: this });
                } catch (reportError) {
                    console.error('TableView onDataChangeError failed.', reportError);
                }
            }
        }

        refreshRow(rowIndex) {
            const row = this.data[rowIndex];
            const tr = this.wrapper.querySelector(`tbody tr[data-row="${rowIndex}"]`);
            if (!row || !tr) throw new RangeError('Cannot refresh a missing row.');
            this.styleRow(tr, row, rowIndex);
            const headerButton = tr.querySelector('[data-row-header] button');
            if (headerButton) {
                headerButton.textContent = this.rowHeaderLabel(row, rowIndex);
                headerButton.setAttribute('aria-label', `Select row ${headerButton.textContent}`);
            }
            this.wrapper.querySelectorAll(`td[data-row="${rowIndex}"]`).forEach(cell => {
                const column = this.columns[Number(cell.dataset.column)];
                if (cell.querySelector('[data-table-view-editor]')
                    && this.editing?.rowIndex === rowIndex && this.editing.columnKey === column.key) {
                    this.styleCell(cell, column, row, rowIndex);
                    return;
                }
                this.renderCell(cell, column, this.data[rowIndex], rowIndex);
            });
            this.applyRowSelection(tr, rowIndex);
        }

        /**
         * Parse and validate the editor value before mutating the row.
         * validate returns true/undefined to accept, or false/an error string to reject.
         * onCellChange returns false to reject, undefined to accept, or a normalized value.
         * These hooks are synchronous; onDataChange runs after the accepted update.
         */
        commitEdit(editor) {
            if (!this.editing) return true;
            this.flushPreview();
            const context = this.readEdit(editor);
            if (!context) {
                editor.focus();
                return false;
            }
            const { row, rowIndex, column, value } = context;
            const previousValue = row[column.key];
            let result;
            try {
                result = this.options.onCellChange?.(context);
            } catch (error) {
                row[column.key] = previousValue;
                console.error('TableView onCellChange failed.', error);
                this.rejectEdit(editor, context, 'The change could not be applied. Correct the value or press Escape.');
                editor.focus();
                return false;
            }
            if (result === false) {
                row[column.key] = previousValue;
                this.rejectEdit(editor, context, 'The change was rejected.');
                editor.focus();
                return false;
            }
            row[column.key] = result === undefined ? value : result;
            this.editing = null;
            this.refreshRow(rowIndex);
            this.wrapper.querySelector(
                `td[data-row="${rowIndex}"][data-column="${context.columnIndex}"]`,
            )?.focus();
            this.notifyDataChange({ ...context, value: row[column.key], phase: 'commit' });
            if (this.filter) this.setFilter(this.filter);
            return true;
        }

        // Discard the editor value and return focus to the selected cell.
        cancelEdit() {
            this.discardPreview();
            if (!this.editing) return;
            const { rowIndex: editedRow, columnKey, originalValue } = this.editing;
            const row = this.data[editedRow];
            const previousValue = row[columnKey];
            row[columnKey] = originalValue;
            this.editing = null;
            this.refreshRow(editedRow);
            const { rowIndex, columnIndex } = this.activeCell || {};
            if (Number.isInteger(rowIndex) && Number.isInteger(columnIndex)) {
                this.getCell(rowIndex, columnIndex)?.focus({ preventScroll: true });
            }
            this.notifyDataChange({
                row, rowIndex: editedRow, column: this.columns.find(col => col.key === columnKey),
                columnIndex: this.columns.findIndex(col => col.key === columnKey),
                oldValue: previousValue, value: originalValue, phase: 'rollback',
            });
        }

        // Replace the shared data array and discard any pending edit.
        setData(data, preserveObjects = false) {
            if (!Array.isArray(data)) throw new TypeError('TableView.setData requires an array.');
            this.validateRows(data);
            this.cancelEdit();
            const filtered = this.filterIndexes(data);
            const previous = this.data;
            const identity = (row, index) => this.rowKey ? row[this.rowKey] : preserveObjects ? row : index;
            const selectedRanges = this.ranges.map(range => ({
                ...range,
                identities: previous.slice(range.startRow, range.endRow + 1)
                    .map((row, offset) => identity(row, range.startRow + offset)),
            }));
            const activeId = this.activeCell
                ? identity(previous[this.activeCell.rowIndex], this.activeCell.rowIndex) : undefined;
            const anchorId = this.anchorCell
                ? identity(previous[this.anchorCell.rowIndex], this.anchorCell.rowIndex) : undefined;
            const hiddenIds = [...this.manualHiddenRows].map(index => identity(previous[index], index));
            const viewport = this.captureViewport();
            const indexes = new Map(data.map((row, index) => [identity(row, index), index]));
            this.data = data;
            this.manualHiddenRows = new Set(hiddenIds.filter(id => indexes.has(id)).map(id => indexes.get(id)));
            this.hiddenRows = new Set([...this.manualHiddenRows, ...filtered]);
            this.activeCell = this.activeCell && indexes.has(activeId)
                ? { ...this.activeCell, rowIndex: indexes.get(activeId) } : null;
            this.anchorCell = this.anchorCell && indexes.has(anchorId)
                ? { ...this.anchorCell, rowIndex: indexes.get(anchorId) } : null;
            // A reordered selection may become disjoint; split it instead of selecting unrelated rows.
            this.ranges = selectedRanges.flatMap(range => {
                const rows = range.identities.filter(id => indexes.has(id))
                    .map(id => indexes.get(id)).sort((a, b) => a - b);
                const groups = [];
                rows.forEach(index => {
                    const last = groups[groups.length - 1];
                    if (last && index === last.endRow + 1) last.endRow = index;
                    else groups.push({
                        startRow: index, endRow: index,
                        startCol: range.startCol, endCol: range.endCol,
                    });
                });
                return groups;
            });
            if (!previous.length && data.length) {
                this.activeCell = { rowIndex: 0, columnIndex: 0 };
                this.anchorCell = { ...this.activeCell };
                this.ranges = [this.createRange(this.activeCell, this.activeCell)];
            }
            this.render();
            this.applyHiddenRows();
            this.restoreViewport(viewport);
            this.options.onSelectionChange?.(this.getSelectedCell());
        }

        validateRows(data) {
            const identities = new Set();
            data.forEach(row => {
                if (!row || typeof row !== 'object' || Array.isArray(row)) {
                    throw new TypeError('Each row must be an object.');
                }
                if (!this.rowKey) return;
                const key = row[this.rowKey];
                if ((typeof key !== 'string' || !key) && (typeof key !== 'number' || !Number.isFinite(key))) {
                    throw new TypeError('Each rowKey must be a non-empty string or a finite number.');
                }
                if (identities.has(key)) throw new TypeError(`Duplicate rowKey: ${key}.`);
                identities.add(key);
            });
        }

        // Keep hidden rows mounted, so every mask/unmask sequence works without a full rebuild.
        setHiddenRows(rows) {
            if (!Array.isArray(rows) || rows.some(index =>
                !Number.isInteger(index) || index < 0 || index >= this.data.length)) {
                throw new RangeError('Hidden rows must be valid row indexes.');
            }
            const filtered = this.filterIndexes(this.data);
            this.manualHiddenRows = new Set(rows);
            this.hiddenRows = new Set([...rows, ...filtered]);
            this.applyHiddenRows();
        }

        filterIndexes(data, predicate = this.filter) {
            return predicate ? data.flatMap((row, index) => predicate(row, index) ? [] : [index]) : [];
        }

        setFilter(predicate) {
            if (predicate !== null && typeof predicate !== 'function') {
                throw new TypeError('setFilter requires a predicate or null.');
            }
            const filtered = this.filterIndexes(this.data, predicate);
            this.filter = predicate;
            this.hiddenRows = new Set([...this.manualHiddenRows, ...filtered]);
            this.applyHiddenRows();
        }

        applyHiddenRows() {
            const viewport = this.captureViewport();
            const hidden = this.hiddenRows;
            if (this.editing && hidden.has(this.editing.rowIndex)) this.cancelEdit();
            this.wrapper.querySelectorAll('tbody tr').forEach((row, index) => {
                row.hidden = hidden.has(index);
            });
            if (this.activeCell && hidden.has(this.activeCell.rowIndex)) {
                const visible = this.visibleRowIndexes();
                const index = visible.find(index => index > this.activeCell.rowIndex) ?? visible[visible.length - 1];
                if (index === undefined) {
                    this.activeCell = null;
                    this.anchorCell = null;
                    this.ranges = [];
                } else {
                    const columnIndex = this.activeCell.columnIndex;
                    this.activeCell = { rowIndex: index, columnIndex };
                    this.anchorCell = { ...this.activeCell };
                    this.ranges = [this.createRange(this.activeCell, this.activeCell)];
                    this.getCell(index, columnIndex)?.focus({ preventScroll: true });
                }
            }
            this.closeContextMenu();
            this.applySelection();
            this.restoreViewport(viewport);
            this.options.onSelectionChange?.(this.getSelectedCell());
        }

        sortBy(columnKey, direction) {
            const column = this.columns.find(item => item.key === columnKey);
            if (!column?.sortable) throw new TypeError('Column is not sortable.');
            direction ??= this.sortState?.key === columnKey && this.sortState.direction === 'asc'
                ? 'desc' : 'asc';
            if (!['asc', 'desc'].includes(direction)) throw new TypeError('Invalid sort direction.');
            if (!this.finishEdit()) return false;
            const collator = new Intl.Collator(column.locale || this.options.locale || 'en-US',
                { numeric: true, sensitivity: 'base' });
            const entries = this.data.map((row, index) => ({
                row, index, children: [],
                value: column.getValue ? column.getValue(row, index) : row[column.key],
            }));
            const compare = (a, b) => {
                let result;
                if (a.value == null || b.value == null) {
                    result = a.value == null ? b.value == null ? 0 : 1 : -1;
                } else {
                    result = typeof a.value === 'number' && typeof b.value === 'number'
                        ? a.value - b.value : collator.compare(String(a.value), String(b.value));
                }
                return (direction === 'asc' ? result : -result) || a.index - b.index;
            };
            const roots = [];
            const stack = [];
            const hierarchy = this.options.hierarchy;
            entries.forEach(entry => {
                if (!hierarchy) { roots.push(entry); return; }
                const level = hierarchy.getLevel?.(entry.row, entry.index);
                if (!Number.isInteger(level) || level < 0) {
                    throw new TypeError('Hierarchy sorting requires non-negative integer getLevel values.');
                }
                while (stack.length && stack[stack.length - 1].level >= level) stack.pop();
                entry.level = level;
                (stack.length ? stack[stack.length - 1].children : roots).push(entry);
                stack.push(entry);
            });
            const rows = [];
            const visit = siblings => {
                siblings.sort(compare).forEach(entry => {
                    rows.push(entry.row);
                    visit(entry.children);
                });
            };
            visit(roots);
            this.filterIndexes(rows);
            // TableView alone sorts. The synchronous adapter mirrors this exact order, without
            // sorting again, changing parents, rebuilding data, or calling setData/sortBy.
            const result = this.options.onSort?.({ column, direction, rows: rows.slice() });
            if (result && typeof result.then === 'function') {
                throw new TypeError('onSort must be synchronous.');
            }
            if (result === false) return false;
            this.sortState = { key: columnKey, direction };
            this.setData(rows, true);
            return true;
        }

        getHiddenRows() {
            return [...this.hiddenRows];
        }

        // Apply a programmatic update without invoking editor validation or change callbacks.
        setValue(rowIndex, columnKey, value) {
            const row = this.data[rowIndex];
            if (!row || !this.columns.some(column => column.key === columnKey)) return false;
            this.cancelEdit();
            row[columnKey] = value;
            this.refreshRow(rowIndex);
            if (this.filter) this.setFilter(this.filter);
            return true;
        }

        // Return the live data array, not a defensive copy.
        getData() {
            return this.data;
        }
        
        // Validate and normalize column definitions before use.
        validateColumns(columns) {
            if (!Array.isArray(columns) || !columns.length) {
                throw new TypeError('TableView requires at least one column.');
            }
            const keys = new Set();
            const result = columns.map((column, index) => {
                if (!column || typeof column !== 'object'
                    || typeof column.key !== 'string' || !column.key) {
                    throw new TypeError(`Column ${index + 1} must define a non-empty key.`);
                }
                if (keys.has(column.key)) throw new TypeError(`Duplicate column key: ${column.key}.`);
                keys.add(column.key);
                if ((column.group !== undefined && typeof column.group !== 'string')
                    || (column.sortable !== undefined && typeof column.sortable !== 'boolean')) {
                    throw new TypeError(`Invalid group or sortable flag for column "${column.key}".`);
                }
                const min = column.minWidth ?? 40;
                const max = column.maxWidth ?? 1200;
                if (!Number.isFinite(min) || !Number.isFinite(max) || min <= 0 || max < min
                    || (column.width !== undefined
                        && (!Number.isFinite(Number(column.width)) || Number(column.width) <= 0))) {
                    throw new TypeError(`Invalid width bounds for column "${column.key}".`);
                }
                return { ...column };
            });
            return result;
        }
        
        // Generate effective options for the given columns, considering feature availability.
        optionsForColumns(columns, options = this.options) {
            const keys = new Set(columns.map(column => column.key));
            const next = { ...options };
            for (const name of ['hierarchy', 'rowActions']) {
                const feature = this.featureOptions[name];
                if (feature?.columnKey !== undefined && !keys.has(feature.columnKey)) {
                    console.warn(`TableView disabled ${name}: missing column "${feature.columnKey}".`);
                    next[name] = undefined;
                } else next[name] = feature;
            }
            return next;
        }

        // Definitions are shallow copies; callbacks are preserved, effective widths are included.
        getColumns() {
            return this.columns.map(column => ({ ...column, width: this.getColumnWidth(column) }));
        }

        // Remap selected columns by key; removed columns never select an unrelated neighbor.
        setColumns(definitions) {
            const columns = this.validateColumns(definitions);
            const options = this.optionsForColumns(columns);
            this.cancelEdit();
            const viewport = this.captureViewport();
            const indexes = new Map(columns.map((column, index) => [column.key, index]));
            const remapCell = cell => {
                if (!cell) return null;
                const columnIndex = indexes.get(this.columns[cell.columnIndex].key);
                return columnIndex === undefined ? null : { ...cell, columnIndex };
            };
            this.activeCell = remapCell(this.activeCell);
            this.anchorCell = remapCell(this.anchorCell);
            this.ranges = this.ranges.flatMap(range => {
                const selected = this.columns.slice(range.startCol, range.endCol + 1)
                    .map(column => indexes.get(column.key))
                    .filter(index => index !== undefined).sort((a, b) => a - b);
                const groups = [];
                selected.forEach(index => {
                    const last = groups[groups.length - 1];
                    if (last && last.endCol + 1 === index) last.endCol = index;
                    else groups.push({ ...range, startCol: index, endCol: index });
                });
                return groups;
            });
            const widths = new Map(columns.map(column => [
                column.key, this.clampWidth(column,
                    Number(column.width ?? this.widths.get(column.key) ?? 160)),
            ]));
            this.columns = columns;
            this.options = options;
            this.widths = widths;
            if (!columns.some(column => column.key === this.sortState?.key && column.sortable)) {
                this.sortState = null;
            }
            this.render();
            this.restoreViewport(viewport);
            this.options.onSelectionChange?.(this.getSelectedCell());
            this.options.onConfigurationChange?.(this.getConfiguration());
        }
        
        // Retrieve the currently selected cell with its associated row, column, and value.
        getSelectedCell() {
            if (!this.activeCell) return null;
            const { rowIndex, columnIndex } = this.activeCell;
            const row = this.data[rowIndex];
            const column = this.columns[columnIndex];
            return {
                ...this.activeCell,
                row,
                column,
                value: typeof column.getValue === 'function'
                    ? column.getValue(row, rowIndex) : row?.[column.key],
            };
        }

        // Retrieve the current selection, including ranges, row indexes, row keys, and active cell.
        getSelection() {
            if (!this.ranges.length) return null;
            const rowIndexes = new Set();
            this.ranges.forEach(range => {
                for (let index = range.startRow; index <= range.endRow; index++) {
                    if (!this.hiddenRows.has(index)) rowIndexes.add(index);
                }
            });
            const indexes = [...rowIndexes].sort((a, b) => a - b);
            const activeRange = this.activeCell && this.ranges.find(range =>
                this.activeCell.rowIndex >= range.startRow && this.activeCell.rowIndex <= range.endRow
                && this.activeCell.columnIndex >= range.startCol && this.activeCell.columnIndex <= range.endCol);
            return {
                ranges: this.ranges.map(range => ({
                    ...range, nbRows: range.endRow - range.startRow + 1,
                    isSingleCell: range.startRow === range.endRow && range.startCol === range.endCol,
                })),
                rowIndexes: indexes,
                rowKeys: this.rowKey ? indexes.map(index => this.data[index][this.rowKey]) : [],
                activeCell: this.activeCell ? { ...this.activeCell } : null,
                range: activeRange ? { ...activeRange, nbRows: activeRange.endRow - activeRange.startRow + 1 } : null,
            };
        }

        /**
         * @param {{structured?: boolean, omitNullValues?: boolean}} [options]
         * @returns {Array<*>|{values: Array<*>, cells: Array<Object>}}
         * Structured cells and values have matching indexes; null omission applies to both.
         */
        getSelectedCellValues({ structured = false, omitNullValues = this.options.omitNullValues } = {}) {
            const values = [];
            const cells = [];
            const visited = new Set();
            this.ranges.forEach(range => {
                for (let rowIndex = range.startRow; rowIndex <= range.endRow; rowIndex++) {
                    if (this.hiddenRows.has(rowIndex)) continue;
                    for (let columnIndex = range.startCol; columnIndex <= range.endCol; columnIndex++) {
                        const key = `${rowIndex}:${columnIndex}`;
                        if (visited.has(key)) continue;
                        visited.add(key);
                        const column = this.columns[columnIndex];
                        const value = column.getValue
                            ? column.getValue(this.data[rowIndex], rowIndex)
                            : this.data[rowIndex][column.key];
                        if (!omitNullValues || (value !== null && value !== undefined)) {
                            values.push(value);
                            if (structured) cells.push({
                                rowIndex, columnIndex, columnKey: column.key,
                                rowKey: this.rowKey ? this.data[rowIndex][this.rowKey] : undefined,
                                row: this.data[rowIndex], column: { ...column }, value,
                            });
                        }
                    }
                }
            });
            return structured ? { values, cells } : values;
        }

        // Parse a TSV string into a 2D array of rows and fields. Handles quoted fields and line breaks.
        static parseTsv(text) {
            const rows = [];
            let row = [];
            let field = '';
            let quoted = false;
            let closed = false;
            const endField = () => { row.push(field); field = ''; closed = false; };
            for (let index = 0; index < text.length; index++) {
                const char = text[index];
                if (quoted) {
                    if (char === '"') {
                        if (text[index + 1] === '"') { field += '"'; index++; }
                        else { quoted = false; closed = true; }
                    } else field += char;
                } else if (char === '\t') {
                    endField();
                } else if (char === '\r' || char === '\n') {
                    if (char === '\r' && text[index + 1] === '\n') index++;
                    endField();
                    rows.push(row);
                    row = [];
                } else if (char === '"' && !field && !closed) {
                    quoted = true;
                } else {
                    if (closed || char === '"') throw new TypeError('Invalid quoted TSV field.');
                    field += char;
                }
            }
            if (quoted) throw new TypeError('Unterminated quoted TSV field.');
            if (row.length || field || closed || !rows.length) {
                endField();
                rows.push(row);
            }
            return rows;
        }

        // Convert a 2D array of rows and fields into a TSV string, escaping as necessary.
        static stringifyTsv(rows) {
            return rows.map(row => row.map(value => {
                const text = value == null ? '' : String(value);
                return /["\t\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
            }).join('\t')).join('\r\n');
        }

        // Copy the currently selected range of cells to the clipboard as TSV text.
        copyText() {
            if (!this.ranges.length) return '';
            const minRow = Math.min(...this.ranges.map(range => range.startRow));
            const maxRow = Math.max(...this.ranges.map(range => range.endRow));
            const minCol = Math.min(...this.ranges.map(range => range.startCol));
            const maxCol = Math.max(...this.ranges.map(range => range.endCol));
            const values = [];
            for (let rowIndex = minRow; rowIndex <= maxRow; rowIndex++) {
                if (this.hiddenRows.has(rowIndex)) continue;
                const row = [];
                for (let colIndex = minCol; colIndex <= maxCol; colIndex++) {
                    const column = this.columns[colIndex];
                    row.push(this.isSelected(rowIndex, colIndex)
                        ? column.getValue ? column.getValue(this.data[rowIndex], rowIndex)
                            : this.data[rowIndex][column.key] : '');
                }
                values.push(row);
            }
            return TableView.stringifyTsv(values);
        }
        // Handle clipboard failures by displaying an error message and invoking the error callback.
        clipboardFailure(error) {
            console.error('TableView clipboard failed.', error);
            let status = this.container.querySelector('[data-tv-clipboard-status]');
            if (!status) {
                status = document.createElement('p');
                status.dataset.tvClipboardStatus = 'true';
                status.setAttribute('role', 'alert');
                this.container.appendChild(status);
            }
            status.textContent = error instanceof Error ? error.message : String(error);
            this.options.onClipboardError?.(error);
        }

        // Handle the copy event, writing the selected cells to the clipboard as TSV text.
        handleCopy(event) {
            if (!this.options.clipboard?.copy
                || event.target.closest('input,textarea,select,[data-table-view-editor]')
                || !this.ranges.length) return;
            event.preventDefault();
            try {
                if (!event.clipboardData) throw new Error('Clipboard access is unavailable.');
                event.clipboardData.setData('text/plain', this.copyText());
            } catch (error) { this.clipboardFailure(error); }
        }

        // Handle the paste event, reading TSV text from the clipboard and applying it to the table.
        handlePaste(event) {
            if (!this.options.clipboard?.paste
                || event.target.closest('input,textarea,select,[data-table-view-editor]')) return;
            event.preventDefault();
            try {
                if (!event.clipboardData) throw new Error('Clipboard access is unavailable.');
                this.pasteText(event.clipboardData.getData('text/plain'));
                this.container.querySelector('[data-tv-clipboard-status]')?.remove();
            } catch (error) { this.clipboardFailure(error); }
        }

        // Validate the entire batch before mutation; onPaste is a synchronous, atomic guard.
        // Apply the pasted TSV text to the table, expanding rows as necessary.
        pasteText(text) {
            if (typeof text !== 'string') throw new TypeError('pasteText requires a string.');
            if (!this.options.clipboard?.paste) throw new Error('Pasting is disabled.');
            if (!this.activeCell) throw new Error('Select a destination cell before pasting.');
            if (!this.finishEdit()) return false;
            const matrix = this.options.clipboard.parseTsv
                ? TableView.parseTsv(text) : [[text]];
            const start = { ...this.activeCell };
            if (matrix.some(row => row.length + start.columnIndex > this.columns.length)) {
                throw new RangeError('Pasted data exceeds the available columns.');
            }
            const includeHidden = this.options.clipboard.includeHiddenRows === true;
            const indexes = includeHidden
                ? this.data.map((_row, index) => index) : this.visibleRowIndexes();
            const startIndex = indexes.indexOf(start.rowIndex);
            const targets = indexes.slice(startIndex, startIndex + matrix.length);
            const newRows = [];
            while (targets.length < matrix.length) {
                const rowIndex = this.data.length + newRows.length;
                const row = this.options.createRow
                    ? this.options.createRow({ rowIndex, table: this })
                    : this.rowKey ? { [this.rowKey]: global.crypto.randomUUID() } : {};
                newRows.push(row);
                targets.push(rowIndex);
            }
            const nextData = [...this.data, ...newRows];
            this.validateRows(nextData);
            const changes = [];
            matrix.forEach((values, offset) => {
                const rowIndex = targets[offset];
                const row = nextData[rowIndex];
                values.forEach((raw, columnOffset) => {
                    const columnIndex = start.columnIndex + columnOffset;
                    const column = this.columns[columnIndex];
                    if (!this.isEditable(column, row, rowIndex, includeHidden)) return;
                    const value = typeof column.parse === 'function' ? column.parse(raw)
                        : column.type === 'number' ? this.parseNumber(raw, column) : raw;
                    const context = {
                        row, rowIndex, column, columnIndex, oldValue: row[column.key], value,
                    };
                    const validation = this.validateValue(value, context);
                    if (validation !== true && validation !== undefined) {
                        throw new TypeError(typeof validation === 'string' ? validation : 'Pasted value was rejected.');
                    }
                    changes.push(context);
                });
            });
            if (!changes.length) throw new Error('The destination contains no editable cells.');
            const batch = { changes, newRows, data: nextData, source: matrix, table: this };
            const accepted = this.options.onPaste?.(batch);
            if (accepted && typeof accepted.then === 'function') {
                throw new TypeError('onPaste must be synchronous.');
            }
            if (accepted === false) throw new Error('Paste was rejected by the application.');
            changes.forEach(change => { change.row[change.column.key] = change.value; });
            this.setData(nextData, true);
            this.notifyDataChange({ phase: 'paste', ...batch });
            return true;
        }

        // Use row identity lookup rather than interpolating arbitrary keys into CSS selectors.
        captureViewport() {
            if (this.options.viewport === false) return null;
            const header = this.appearance.stickyHeader
                ? this.wrapper.querySelector('thead')?.getBoundingClientRect().height || 0 : 0;
            const top = this.wrapper.getBoundingClientRect().top + header;
            const anchor = [...this.wrapper.querySelectorAll('tbody tr')]
                .find(row => !row.hidden && row.getBoundingClientRect().bottom > top);
            const rowIndex = anchor ? Number(anchor.dataset.row) : null;
            return {
                rowIndex,
                rowKey: rowIndex !== null && this.rowKey ? this.data[rowIndex]?.[this.rowKey] : null,
                offset: anchor ? anchor.getBoundingClientRect().top - top : 0,
                scrollTop: this.wrapper.scrollTop, scrollLeft: this.wrapper.scrollLeft,
            };
        }

        // Restore the viewport to a previously captured state, including scroll position and anchor row.
        restoreViewport(viewport) {
            if (!viewport) return;
            this.wrapper.scrollTop = viewport.scrollTop;
            this.wrapper.scrollLeft = viewport.scrollLeft;
            const index = this.rowKey && viewport.rowKey !== null
                ? this.data.findIndex(row => row[this.rowKey] === viewport.rowKey) : viewport.rowIndex;
            if (index === null || index < 0 || this.hiddenRows.has(index)) return;
            const anchor = this.wrapper.querySelector(`tbody tr[data-row="${index}"]`);
            if (!anchor) return;
            const header = this.appearance.stickyHeader
                ? this.wrapper.querySelector('thead')?.getBoundingClientRect().height || 0 : 0;
            const top = this.wrapper.getBoundingClientRect().top + header;
            this.wrapper.scrollTop += anchor.getBoundingClientRect().top - top - viewport.offset;
        }

        // Export only presentation settings, never row data, editors, or business callbacks.
        getConfiguration() {
            return {
                version: 1,
                rowHeaders: Boolean(this.options.rowHeaders),
                appearance: { ...this.appearance },
                columns: this.columns.map(column => ({
                    key: column.key, label: column.label ?? column.key, type: column.type || 'text',
                    width: this.getColumnWidth(column),
                    minWidth: column.minWidth ?? 40, maxWidth: column.maxWidth ?? 1200,
                    align: column.align || (column.type === 'number' ? 'right' : 'left'),
                    color: column.color || '', background: column.background || '',
                    decimals: column.decimals ?? 2,
                    locale: column.locale || this.options.locale || 'en-US',
                    useGrouping: column.useGrouping !== false, hideZero: Boolean(column.hideZero),
                })),
            };
        }

        // Update the appearance settings of the table without altering the underlying data or columns.
        setAppearance(appearance) {
            const configuration = this.getConfiguration();
            configuration.appearance = { ...configuration.appearance, ...appearance };
            this.applyConfiguration(configuration);
        }

        // Validate the entire configuration before changing anything. Pending drafts are canceled.
        // Throws a TypeError if the configuration is invalid.
        applyConfiguration(configuration) {
            const fail = message => { throw new TypeError(message); };
            const isColor = value => typeof value === 'string' && /^#[\da-f]{6}$/i.test(value);
            if (!configuration || configuration.version !== 1
                || !configuration.appearance || !Array.isArray(configuration.columns)
                || configuration.columns.length !== this.columns.length) {
                fail('Invalid TableView configuration.');
            }
            const appearance = { ...this.appearance, ...configuration.appearance };
            const rowHeaders = configuration.rowHeaders ?? Boolean(this.options.rowHeaders);
            if (typeof rowHeaders !== 'boolean') fail('rowHeaders must be a boolean.');
            Object.keys(COLOR_FIELDS).forEach(key => {
                if (!isColor(appearance[key])) fail(`Invalid color: ${key}.`);
            });
            Object.entries(SIZE_FIELDS).forEach(([key, { min, max }]) => {
                if (!Number.isInteger(appearance[key]) || appearance[key] < min || appearance[key] > max) {
                    fail(`${key} must be an integer between ${min} and ${max}.`);
                }
            });
            if (typeof appearance.stickyHeader !== 'boolean') fail('stickyHeader must be a boolean.');
            const columns = this.columns.map((column, index) => {
                const next = configuration.columns[index];
                if (!next || next.key !== column.key || typeof next.label !== 'string') {
                    fail('Column keys and order must match the current table.');
                }
                if (!Number.isFinite(next.width)
                    || next.width < (column.minWidth ?? 40) || next.width > (column.maxWidth ?? 1200)) {
                    fail(`Invalid width for column "${column.key}".`);
                }
                if (!['left', 'center', 'right'].includes(next.align)) fail('Invalid alignment.');
                if ((next.color !== '' && !isColor(next.color))
                    || (next.background !== '' && !isColor(next.background))) fail('Invalid cell color.');
                if (!Number.isInteger(next.decimals) || next.decimals < 0 || next.decimals > 10) {
                    fail('Decimal places must be between 0 and 10.');
                }
                if (typeof next.locale !== 'string' || !next.locale
                    || !Intl.NumberFormat.supportedLocalesOf([next.locale]).length) {
                    fail('Unsupported number locale.');
                }
                if (typeof next.useGrouping !== 'boolean' || typeof next.hideZero !== 'boolean') {
                    fail('Numeric display flags must be booleans.');
                }
                return {
                    ...column, label: next.label, width: next.width, align: next.align,
                    color: next.color, background: next.background, decimals: next.decimals,
                    locale: next.locale, useGrouping: next.useGrouping, hideZero: next.hideZero,
                };
            });
            const appearanceChanged = Object.keys(APPEARANCE_DEFAULTS)
                .some(key => this.appearance[key] !== appearance[key]);
            this.cancelEdit();
            if (rowHeaders !== Boolean(this.options.rowHeaders)) {
                this.options.rowHeaders = rowHeaders && this.rowHeaderRenderer ? this.rowHeaderRenderer : rowHeaders;
            }
            this.appearance = Object.fromEntries(Object.keys(APPEARANCE_DEFAULTS)
                .map(key => [key, appearance[key]]));
            this.columns = columns;
            columns.forEach(column => this.widths.set(column.key, column.width));
            this.render();
            if (appearanceChanged) this.options.onAppearanceChange?.({ ...this.appearance });
            this.options.onConfigurationChange?.(this.getConfiguration());
        }

        /**
         * Mount a generic configuration form in any document, including a separate same-origin page.
         * The caller supplies a configuration snapshot and a sync/async onApply callback.
         * Submit awaits acceptance; resets restore the last accepted settings.
         * onDirtyChange reports unapplied changes, including while an application is pending.
         * onApply must be atomic: rejection must leave the target unchanged (or roll it back).
         * The form cannot undo external side effects; it retains the last accepted baseline.
         */
        static mountConfiguration(container, { configuration, onApply, onDirtyChange }) {
            if (!configuration || typeof onApply !== 'function') {
                throw new TypeError('Configuration and onApply are required.');
            }
            configuration = JSON.parse(JSON.stringify(configuration));
            const form = document.createElement('form');
            form.className = 'table-view-config';
            form.noValidate = true;
            const fields = new Map();
            const idPrefix = `tv-config-${++configurationSequence}`;
            const tabs = [];
            const tabList = document.createElement('div');
            tabList.className = 'tv-config-tabs';
            tabList.setAttribute('role', 'tablist');
            tabList.setAttribute('aria-label', 'Table configuration');
            form.appendChild(tabList);
            let dirty = false;
            let busy = false;

            // Activate the first tab by default.
            function activateTab(target, focus = false) {
                tabs.forEach(({ button, panel }) => {
                    const active = panel === target;
                    panel.hidden = !active;
                    button.setAttribute('aria-selected', String(active));
                    button.tabIndex = active ? 0 : -1;
                    if (active && focus) {
                        button.focus({ preventScroll: true });
                        button.scrollIntoView({ block: 'nearest', inline: 'nearest' });
                    }
                });
            }

            // Create a new group (tab) in the configuration dialog with the given label and description.
            function group(label, description) {
                const panel = document.createElement('div');
                panel.id = `${idPrefix}-panel-${tabs.length}`;
                panel.setAttribute('role', 'tabpanel');
                const button = document.createElement('button');
                button.type = 'button';
                button.id = `${panel.id}-tab`;
                button.textContent = label;
                button.setAttribute('role', 'tab');
                button.setAttribute('aria-controls', panel.id);
                panel.setAttribute('aria-labelledby', button.id);
                button.addEventListener('click', () => activateTab(panel));
                button.addEventListener('keydown', event => {
                    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
                    event.preventDefault();
                    const current = tabs.findIndex(tab => tab.button === button);
                    const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
                        : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
                    activateTab(tabs[next].panel, true);
                });
                const fieldset = document.createElement('fieldset');
                const legend = document.createElement('legend');
                legend.textContent = label;
                const details = document.createElement('p');
                details.className = 'tv-config-description';
                details.textContent = description;
                const controls = document.createElement('tbody');
                const settingsTable = document.createElement('table');
                settingsTable.className = 'tv-config-table';
                settingsTable.appendChild(controls);
                fieldset.append(legend, details, settingsTable);
                panel.appendChild(fieldset);
                form.appendChild(panel);
                tabList.appendChild(button);
                tabs.push({ button, panel });
                activateTab(tabs.find(tab => !tab.panel.hidden)?.panel || tabs[0].panel);
                return controls;
            }

            // Create a new field (input control) within the given parent group, with the specified name, 
            // label, value, type, and additional attributes.
            function field(parent, name, label, value, type = 'text', attributes = {}) {
                const wrapper = document.createElement('tr');
                wrapper.className = 'tv-config-row';
                const labelCell = document.createElement('td');
                const valueCell = document.createElement('td');
                const caption = document.createElement('label');
                caption.textContent = label;
                const controls = document.createElement('div');
                controls.className = 'tv-config-control';
                const input = document.createElement(type === 'select' ? 'select' : 'input');
                input.id = `${idPrefix}-${name.replace(/\./g, '-')}`;
                caption.htmlFor = input.id;
                input.name = name;
                if (type === 'select') {
                    ['left', 'center', 'right'].forEach(value => {
                        const option = document.createElement('option');
                        option.value = value;
                        option.textContent = value[0].toUpperCase() + value.slice(1);
                        input.appendChild(option);
                    });
                } else input.type = type;
                if (type === 'checkbox') {
                    input.checked = value;
                    input.defaultChecked = value;
                } else {
                    input.value = value;
                    if (type !== 'select') input.defaultValue = value;
                }
                Object.entries(attributes).forEach(([key, item]) => input.setAttribute(key, item));
                const resetButton = document.createElement('button');
                resetButton.type = 'button';
                resetButton.className = 'tv-config-reset';
                resetButton.textContent = '\u21ba';
                resetButton.title = `Reset ${label}`;
                resetButton.setAttribute('aria-label', resetButton.title);
                resetButton.hidden = true;
                const error = document.createElement('p');
                error.id = `${input.id}-error`;
                error.className = 'tv-config-error';
                error.setAttribute('aria-live', 'polite');
                input.setAttribute('aria-describedby', error.id);
                const entry = { input, row: wrapper, error, resetButton, baseline: readValue(input) };
                resetButton.addEventListener('click', () => {
                    if (busy) return;
                    restoreField(entry);
                    updateDirty();
                    clearFeedback();
                });
                const changed = () => {
                    validateField(entry);
                    updateDirty();
                    clearFeedback();
                };
                input.addEventListener('input', changed);
                input.addEventListener('change', changed);
                controls.append(input, resetButton, error);
                if (type === 'color') {
                    const hex = document.createElement('input');
                    hex.type = 'text';
                    hex.className = 'tv-config-hex';
                    hex.maxLength = 7;
                    hex.value = input.value;
                    hex.setAttribute('aria-label', `HEX ${label}`);
                    hex.addEventListener('input', () => {
                        const valid = /^#[\da-f]{6}$/i.test(hex.value);
                        input.setCustomValidity(valid ? '' : 'Use #RRGGBB.');
                        hex.setAttribute('aria-invalid', String(!valid));
                        if (valid) {
                            input.value = hex.value;
                            changed();
                        } else changed();
                    });
                    input.addEventListener('input', () => { hex.value = input.value; hex.removeAttribute('aria-invalid'); });
                    controls.insertBefore(hex, resetButton);
                    entry.hex = hex;
                } else if (name.endsWith('.color') || name.endsWith('.background')) {
                    input.classList.add('tv-config-hex');
                }
                labelCell.appendChild(caption);
                valueCell.appendChild(controls);
                wrapper.append(labelCell, valueCell);
                parent.appendChild(wrapper);
                fields.set(name, entry);
            }

            // Read the current value of an input field, handling checkboxes specially.
            function readValue(input) {
                return input.type === 'checkbox' ? input.checked : input.value;
            }

            // Restore an input field to its baseline value and re-validate it.
            function restoreField(entry) {
                if (entry.input.type === 'checkbox') entry.input.checked = entry.baseline;
                else entry.input.value = entry.baseline;
                if (entry.hex) {
                    entry.hex.value = entry.input.value;
                    entry.hex.removeAttribute('aria-invalid');
                }
                validateField(entry);
            }

            // Native constraints cover bounds/steps/patterns; locales need an Intl check as well.
            function validateField({ input, error }) {
                input.setCustomValidity('');
                const entry = fields.get(input.name);
                if (entry?.hex && !/^#[\da-f]{6}$/i.test(entry.hex.value)) {
                    input.setCustomValidity('Use #RRGGBB.');
                }
                if (input.name.endsWith('.locale') && input.value) {
                    try {
                        if (!Intl.NumberFormat.supportedLocalesOf([input.value]).length) {
                            input.setCustomValidity('Unsupported number locale.');
                        }
                    } catch (error) {
                        if (!(error instanceof RangeError)) throw error;
                        input.setCustomValidity('Invalid number locale.');
                    }
                }
                const valid = input.checkValidity();
                error.textContent = valid ? '' : input.validationMessage;
                if (valid) input.removeAttribute('aria-invalid');
                else input.setAttribute('aria-invalid', 'true');
                return valid;
            }

            // Update the dirty state of all fields and tabs, enabling or disabling the submit and reset buttons accordingly.
            function updateDirty() {
                let changed = false;
                fields.forEach(entry => {
                    const modified = readValue(entry.input) !== entry.baseline
                        || Boolean(entry.hex && entry.hex.value.toLowerCase() !== String(entry.baseline).toLowerCase());
                    changed ||= modified;
                    entry.row.classList.toggle('is-modified', modified);
                    entry.resetButton.hidden = !modified;
                    entry.resetButton.disabled = busy;
                    if (entry.hex) entry.hex.disabled = busy;
                });
                tabs.forEach(({ button, panel }) => {
                    button.classList.toggle('is-modified', Boolean(panel.querySelector('.is-modified')));
                });
                submit.disabled = busy || !changed;
                reset.disabled = busy || !changed;
                if (dirty !== changed) {
                    dirty = changed;
                    onDirtyChange?.(dirty);
                }
            }

            // Create the appearance settings group and add color and size fields, as well as the sticky header option.
            const appearance = group('Rows and headers', 'Colors and dimensions shared by all rows.');
            Object.entries(COLOR_FIELDS).forEach(([key, label]) =>
                field(appearance, `appearance.${key}`, label, configuration.appearance[key], 'color'));
            Object.entries(SIZE_FIELDS).forEach(([key, { label, min, max }]) =>
                field(appearance, `appearance.${key}`, label, configuration.appearance[key],
                    'number', { min, max, step: 1, required: '' }));
            field(appearance, 'appearance.stickyHeader', 'Sticky header',
                configuration.appearance.stickyHeader, 'checkbox');
            configuration = { ...configuration, rowHeaders: configuration.rowHeaders ?? false };
            field(appearance, 'rowHeaders', 'Show row headers', configuration.rowHeaders, 'checkbox');

            configuration.columns.forEach((column, index) => {
                const controls = group(`Column: ${column.label}`, `Technical key: ${column.key}`);
                const prefix = `columns.${index}.`;
                field(controls, `${prefix}label`, 'Header label', column.label);
                field(controls, `${prefix}width`, 'Width (px)', column.width, 'number',
                    { min: column.minWidth, max: column.maxWidth, step: 'any', required: '' });
                field(controls, `${prefix}align`, 'Alignment', column.align, 'select', { required: '' });
                field(controls, `${prefix}color`, 'Text color (empty = inherited)', column.color,
                    'text', { pattern: '#[0-9a-fA-F]{6}', placeholder: '#24485a' });
                field(controls, `${prefix}background`, 'Background (empty = inherited)', column.background,
                    'text', { pattern: '#[0-9a-fA-F]{6}', placeholder: '#f8f6ef' });
                if (column.type === 'number') {
                    field(controls, `${prefix}decimals`, 'Decimal places', column.decimals,
                        'number', { min: 0, max: 10, step: 1, required: '' });
                    field(controls, `${prefix}locale`, 'Number locale', column.locale,
                        'text', { required: '' });
                    field(controls, `${prefix}useGrouping`, 'Group thousands', column.useGrouping, 'checkbox');
                    field(controls, `${prefix}hideZero`, 'Hide zero values', column.hideZero, 'checkbox');
                }
            });
            const feedback = document.createElement('p');
            feedback.className = 'tv-config-feedback';
            feedback.setAttribute('role', 'status');
            feedback.setAttribute('aria-live', 'polite');
            const submit = document.createElement('button');
            submit.type = 'submit';
            submit.textContent = 'Apply to table (memory only)';
            const reset = document.createElement('button');
            reset.type = 'reset';
            reset.textContent = 'Discard unapplied changes';
            const actions = document.createElement('div');
            actions.className = 'tv-config-actions';
            actions.append(feedback, reset, submit);
            form.appendChild(actions);
            function clearFeedback() {
                feedback.textContent = '';
                feedback.className = 'tv-config-feedback';
            }
            form.addEventListener('reset', event => {
                event.preventDefault();
                if (busy) return;
                fields.forEach(restoreField);
                updateDirty();
                clearFeedback();
            });
            form.addEventListener('submit', async event => {
                event.preventDefault();
                if (busy) return;
                let firstInvalid;
                fields.forEach(entry => {
                    if (!validateField(entry) && !firstInvalid) firstInvalid = entry.input;
                });
                if (firstInvalid) {
                    feedback.textContent = 'Correct the highlighted fields before applying.';
                    feedback.className = 'tv-config-feedback is-error';
                    activateTab(firstInvalid.closest('[role="tabpanel"]'));
                    firstInvalid.focus();
                    return;
                }
                updateDirty();
                if (!dirty) return;
                const next = JSON.parse(JSON.stringify(configuration));
                fields.forEach(({ input }, path) => {
                    const keys = path.split('.');
                    const key = keys.pop();
                    const target = keys.reduce((object, part) => object[part], next);
                    target[key] = input.type === 'checkbox' ? input.checked
                        : input.type === 'number' ? Number(input.value) : input.value;
                });
                busy = true;
                clearFeedback();
                updateDirty();
                fields.forEach(({ input }) => { input.disabled = true; });
                form.setAttribute('aria-busy', 'true');
                try {
                    await onApply(JSON.parse(JSON.stringify(next)));
                    configuration = next;
                    fields.forEach(entry => {
                        const { input } = entry;
                        entry.baseline = readValue(input);
                        if (input.type === 'checkbox') input.defaultChecked = input.checked;
                        else if (input.tagName === 'SELECT') {
                            [...input.options].forEach(option => {
                                option.defaultSelected = option.value === input.value;
                            });
                        } else input.defaultValue = input.value;
                    });
                    updateDirty();
                    feedback.textContent = 'Applied in memory. Reloading the table page discards these settings.';
                    feedback.className = 'tv-config-feedback is-success';
                } catch (error) {
                    feedback.textContent = error.message;
                    feedback.className = 'tv-config-feedback is-error';
                } finally {
                    busy = false;
                    fields.forEach(({ input }) => { input.disabled = false; });
                    updateDirty();
                    form.setAttribute('aria-busy', 'false');
                }
            });
            updateDirty();
            installBaseStyles();
            container.replaceChildren(form);
            return form;
        }

        // Remove the mounted content; shared base styles remain available to other instances.
        destroy() {
            this.stopSelectionDrag();
            this.cancelEdit();
            this.closeContextMenu();
            document.removeEventListener('pointerdown', this._closeOutside);
            document.removeEventListener('scroll', this._closeOnScroll, true);
            document.removeEventListener('keydown', this._closeOnEscape);
            window.removeEventListener('resize', this._closeOnResize);
            this.wrapper.remove();
            this.container.querySelector('[data-tv-clipboard-status]')?.remove();
            this.container.querySelector('[data-tv-data-status]')?.remove();
            this.activeCell = null;
            this.anchorCell = null;
            this.ranges = [];
            this.editing = null;
        }
    }

    Object.defineProperty(TableView, 'version', { value: '0.3.0', enumerable: true });
    global.TableView = TableView;
})(window);
