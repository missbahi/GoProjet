const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require('jsdom');

const jsPath = path.join(__dirname, '..', '..', 'goProjet', 'static', 'projets', 'js');

test('Attachment selection shows loading until navigation or history restoration', t => {
    const template = fs.readFileSync(path.join(__dirname, '..', 'templates', 'projets',
        'decomptes', '_fiche_controle_content.html'), 'utf8');
    const spinner = template.match(/<span id="attachement-loading"[\s\S]*?<\/span>\s*<\/span>/)[0];
    const script = template.match(/<script>([\s\S]*?)<\/script>/)[1];
    const virtualConsole = new VirtualConsole();
    virtualConsole.on('jsdomError', error => {
        if (!error.message.includes('navigation')) throw error;
    });
    const dom = new JSDOM(`<select id="attachement-select">
        <option value="">Choisir</option><option value="1" selected>Un</option>
        <option value="2">Deux</option></select>${spinner}`, {
        url: 'https://example.test/fiche?attachement_id=1', runScripts: 'outside-only', virtualConsole,
    });
    t.after(() => dom.window.close());
    const { window } = dom;
    window.eval(script);
    const select = window.document.getElementById('attachement-select');
    const loading = window.document.getElementById('attachement-loading');
    assert.equal(loading.hidden, true);
    assert.equal(loading.getAttribute('role'), 'status');
    for (const value of ['2', '']) {
        select.value = value;
        select.dispatchEvent(new window.Event('change'));
        assert.equal(loading.hidden, false);
        assert.equal(select.getAttribute('aria-busy'), 'true');
        window.dispatchEvent(new window.PageTransitionEvent('pageshow', { persisted: true }));
        assert.equal(loading.hidden, true);
        assert.equal(select.hasAttribute('aria-busy'), false);
        assert.equal(select.value, '1');
    }
});

function mount(t, value = '1 234,50') {
    const dom = new JSDOM(`
        <div data-fiche-controle-editor data-fullscreen-document>
        <p data-planning-fullscreen-error hidden></p>
        <button data-planning-fullscreen aria-pressed="false"><i class="fas fa-expand"></i></button>
        <button id="fiche-toggle-expanded-all" disabled><i></i></button>
        <div id="selectionSumDisplay"></div>
        <dialog id="fiche-help-dialog"></dialog>
        <button id="fiche-help-open"></button><button id="fiche-help-close"></button>
        <button id="fiche-info-open"></button>
        <div id="fiche-tableview-error" hidden></div>
        <div id="fiche-tableview"></div>
        <div class="fiche-print-table"><table class="table-fiche"><tbody>
            <tr class="lot-header"><td colspan="13">LOT 1</td></tr>
            <tr class="is_title" data-ligne-id="1" data-parent-id="" data-niveau="0">
                <td>1</td><td>Ouvrages</td><td></td><td></td><td></td><td></td><td></td>
                <td></td><td></td><td></td><td></td><td></td><td></td>
            </tr>
            <tr data-ligne-id="2" data-parent-id="1" data-niveau="1">
                <td>1.1</td><td>Travaux détaillés</td><td>m</td><td>10,00</td>
                <td>${value}</td><td>1,00</td><td>2,00</td><td>246,90</td>
                <td>3,00</td><td>370,35</td><td>7,00</td><td>864,15</td><td>30 %</td>
            </tr>
            <tr class="sous-total"><td colspan="3">SOUS-TOTAL LOT 1</td>
                <td colspan="2">${value}</td><td colspan="3">246,90</td>
                <td colspan="2">370,35</td><td colspan="2">864,15</td><td>30 %</td>
            </tr>
            <tr class="total-general"><td colspan="3">TOTAL GÉNÉRAL</td>
                <td colspan="2">${value}</td><td colspan="3">246,90</td>
                <td colspan="2">370,35</td><td colspan="2">864,15</td><td>30 %</td>
            </tr>
        </tbody></table></div></div>
    `, { runScripts: 'outside-only', pretendToBeVisual: true });
    t.after(() => dom.window.close());
    const { window } = dom;
    window.eval(fs.readFileSync(path.join(jsPath, 'table-view.js'), 'utf8'));
    let table;
    window.TableView = class extends window.TableView {
        constructor(...args) {
            super(...args);
            table = this;
        }
    };
    window.console.error = () => {};
    window.eval(fs.readFileSync(path.join(jsPath, 'fiche-controle-tableview.js'), 'utf8'));
    return { window, table };
}

test('Both information buttons open the same help modal', t => {
    const { window } = mount(t);
    const dialog = window.document.getElementById('fiche-help-dialog');
    dialog.showModal = () => dialog.setAttribute('open', '');
    dialog.close = () => dialog.removeAttribute('open');
    for (const id of ['fiche-info-open', 'fiche-help-open']) {
        window.document.getElementById(id).click();
        assert.equal(dialog.open, true);
        window.document.getElementById('fiche-help-close').click();
        assert.equal(dialog.open, false);
    }
});

test('Fiche TableView aligns and formats columns and supports manual resizing', t => {
    const { window, table } = mount(t);
    assert.ok(table);
    const cells = table.wrapper.querySelectorAll('tbody tr[data-row="2"] td');
    assert.equal(cells[0].style.textAlign, 'left');
    assert.equal(cells[1].style.textAlign, 'left');
    assert.equal(cells[2].style.textAlign, 'center');
    assert.equal(cells[4].style.textAlign, 'right');
    assert.equal(cells[4].textContent.replace(/[\u00a0\u202f]/g, ' '), '1 234,50');
    assert.equal(cells[12].textContent, '30 %');
    assert.equal(table.options.editable, false);
    assert.deepEqual(Array.from(table.columns.slice(5, 12), column => column.label), [
        'Qté cumul N-1', 'Qté part.', 'Mt part.', 'Qté cumul N', 'Mt cumul N',
        'Qté M - Qté N', 'Mt M - Mt N',
    ]);

    const header = table.wrapper.querySelector('thead tr:last-child th');
    assert.equal(table.appearance.headerHeight, 48);
    const heightHandle = header.querySelector('.table-view-header-resize-handle');
    heightHandle.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    assert.equal(table.appearance.headerHeight, 49);
    const widthHandle = header.querySelector('.table-view-resize-handle');
    widthHandle.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    assert.equal(table.getColumnWidth(table.columns[0]), 85);
});

test('Hierarchy folds nested rows without changing the complete print table or totals', t => {
    const { window, table } = mount(t);
    assert.equal(table.getData()[2].level, 2);
    table.getCell(1, 1).querySelector('[data-tv-action="fold"]').click();
    assert.deepEqual([...table.hiddenRows], [2]);
    table.getCell(0, 1).querySelector('[data-tv-action="fold"]').click();
    assert.deepEqual([...table.hiddenRows], [1, 2, 3]);
    assert.equal(window.document.querySelectorAll('.table-fiche tbody tr').length, 5);
    assert.match(window.document.querySelector('.total-general').textContent, /1 234,50/);
    table.getCell(0, 1).querySelector('[data-tv-action="fold"]').click();
    assert.deepEqual([...table.hiddenRows], [2]);
});

test('Toolbar collapses and expands all groups while leaving the print table complete', t => {
    const { window, table } = mount(t);
    const button = window.document.getElementById('fiche-toggle-expanded-all');
    assert.equal(button.disabled, false);
    const fold = table.getCell(0, 1).querySelector('.tv-fold');
    assert.equal(fold.textContent, '');
    assert.equal(fold.getAttribute('aria-expanded'), 'true');
    const rules = Array.from(window.document.getElementById('table-view-base-styles').sheet.cssRules);
    const closed = rules.find(rule => rule.selectorText === '.tv-fold::before');
    const open = rules.find(rule => rule.selectorText === '.tv-fold[aria-expanded="true"]::before');
    assert.equal(closed.style.transform, 'rotate(45deg)');
    assert.equal(open.style.transform, 'rotate(135deg)');
    button.click();
    assert.deepEqual([...table.hiddenRows], [1, 2, 3]);
    assert.equal(button.getAttribute('aria-label'), 'Développer toutes les lignes filles');
    assert.equal(table.getCell(0, 1).querySelector('.tv-fold').getAttribute('aria-expanded'), 'false');
    button.click();
    assert.deepEqual([...table.hiddenRows], []);
    assert.equal(window.document.querySelectorAll('.table-fiche tbody tr').length, 5);
});

test('Grand total stays in the grid and cannot be hidden or removed', t => {
    const { window, table } = mount(t);
    const style = window.document.createElement('style');
    style.textContent = fs.readFileSync(path.join(jsPath, '..', 'css',
        'fiche-controle-tableview.css'), 'utf8');
    window.document.head.appendChild(style);
    const total = () => table.wrapper.querySelector('tbody tr.fiche-total');
    assert.equal(window.getComputedStyle(total().cells[0]).position, 'sticky');
    assert.equal(window.getComputedStyle(total().cells[0]).bottom, '0px');
    const amount = total().cells[4].textContent;
    table.selectCell(4, 4);
    table.options.rowActions.onAction('hide', { selection: table.getSelection() });
    assert.equal(total().hidden, false);
    window.confirm = () => true;
    table.options.rowActions.onAction('delete', { selection: table.getSelection() });
    window.document.getElementById('fiche-toggle-expanded-all').click();
    assert.equal(table.wrapper.querySelectorAll('tr.fiche-total').length, 1);
    assert.equal(total().hidden, false);
    assert.equal(total().cells[4].textContent, amount);
    assert.equal(window.document.querySelectorAll('.table-fiche tr.total-general').length, 1);
});

test('Fiche toolbar enters and exits document fullscreen', async t => {
    const { window } = mount(t);
    const { document } = window;
    const root = document.querySelector('[data-fiche-controle-editor]');
    const button = root.querySelector('[data-planning-fullscreen]');
    let fullscreen = null;
    Object.defineProperty(document, 'fullscreenElement', { get: () => fullscreen });
    document.documentElement.requestFullscreen = async () => {
        fullscreen = document.documentElement;
        document.dispatchEvent(new window.Event('fullscreenchange'));
    };
    document.exitFullscreen = async () => {
        fullscreen = null;
        document.dispatchEvent(new window.Event('fullscreenchange'));
    };
    window.eval(fs.readFileSync(path.join(__dirname, '..', '..', 'goplan', 'static',
        'goplan', 'js', 'planning-fullscreen.js'), 'utf8'));
    button.click();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(root.hasAttribute('data-workspace-fullscreen'), true);
    assert.equal(button.getAttribute('aria-pressed'), 'true');
    button.click();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(root.hasAttribute('data-workspace-fullscreen'), false);
    assert.equal(button.getAttribute('aria-pressed'), 'false');
});

test('Context actions hide and restore rows and copy formatted values', async t => {
    const { window, table } = mount(t);
    let copied = '';
    Object.defineProperty(window.navigator, 'clipboard', {
        value: { writeText: async text => { copied = text; } },
    });
    table.selectCell(2, 1);
    const actions = table.options.rowActions;
    actions.onAction('copy', { selection: table.getSelection() });
    await Promise.resolve();
    assert.match(copied.replace(/[\u00a0\u202f]/g, ' '), /1 234,50/);
    actions.onAction('hide', { selection: table.getSelection() });
    assert.deepEqual([...table.hiddenRows], [2]);
    actions.onAction('show', { selection: table.getSelection() });
    assert.deepEqual([...table.hiddenRows], []);
    assert.equal(window.document.querySelectorAll('.table-fiche tbody tr').length, 5);
});

test('Invalid numeric data displays an explicit error', t => {
    const { window, table } = mount(t, 'invalide');
    assert.equal(table, undefined);
    const error = window.document.getElementById('fiche-tableview-error');
    assert.equal(error.hidden, false);
    assert.match(error.textContent, /Valeur numérique invalide/);
});
