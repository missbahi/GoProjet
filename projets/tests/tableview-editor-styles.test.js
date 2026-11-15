const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const root = path.join(__dirname, '..', '..');
const cssDir = path.join(root, 'goProjet', 'static', 'projets', 'css');
function templateStyles(template) {
    const source = fs.readFileSync(path.join(root, 'projets', 'templates', 'projets', template), 'utf8');
    return [...source.matchAll(/static 'projets\/css\/([^']+\.css)'/g)].map(([, name]) => {
        const css = fs.readFileSync(path.join(cssDir, name), 'utf8');
        return css.replace(/@import url\("([^"]+)"\);/g,
            (_, imported) => fs.readFileSync(path.join(cssDir, imported), 'utf8'));
    }).join('\n');
}

test('Four editors load the shared table and fullscreen styles', t => {
    const editors = [
        { template: path.join('lots', 'saisie_bordereau.html'), attribute: 'data-bordereau-editor', host: 'hot' },
        { template: path.join('ca', 'formulaire.html'), attribute: 'data-ca-editor', host: 'ca-table', toolbar: 'ca-selection-toolbar' },
        { template: path.join('decomptes', 'attachement_form.html'), attribute: 'data-attachement-editor',
            host: 'attachement-tableview', wrapper: 'attachement-tableview', toolbar: 'attachment-editor-toolbar' },
        { template: path.join('decomptes', 'fiche_controle.html'), attribute: 'data-fiche-controle-editor',
            host: 'fiche-tableview', toolbar: 'ca-selection-toolbar' },
    ];
    for (const editor of editors) {
        const dom = new JSDOM(`<div class="attachment-workflow-page attachment-page--attachement_form">
            <div ${editor.attribute}>
                <div class="${editor.toolbar || ''}"></div>
                <div class="${editor.wrapper || ''}"><div id="${editor.host}">
                    <div class="table-view-scroll"><table class="table-view-table">
                        <thead><tr><th>Nom</th></tr></thead><tbody><tr><td>Travaux</td></tr></tbody>
                    </table></div>
                </div></div>
            </div></div>`, { runScripts: 'outside-only' });
        t.after(() => dom.window.close());
        const { window } = dom;
        const style = window.document.createElement('style');
        style.textContent = templateStyles(editor.template);
        window.document.head.append(style);
        const table = window.document.querySelector('.table-view-table');
        const scroll = window.document.querySelector('.table-view-scroll');
        assert.equal(window.getComputedStyle(table).borderCollapse, 'separate', editor.host);
        assert.equal(window.getComputedStyle(table.querySelector('th')).textAlign, 'center', editor.host);
        assert.equal(window.getComputedStyle(scroll).maxHeight, '72vh', editor.host);
        if (editor.toolbar) {
            assert.equal(window.getComputedStyle(window.document.querySelector(`.${editor.toolbar}`)).position,
                'sticky', editor.host);
        }
        const editorRoot = window.document.querySelector(`[${editor.attribute}]`);
        editorRoot.setAttribute('data-workspace-fullscreen', '');
        assert.equal(window.getComputedStyle(editorRoot).position, 'fixed', editor.host);
        assert.equal(window.getComputedStyle(scroll).maxHeight, 'none', editor.host);
    }
});

test('Attachment template receives both shared and specific table styles', t => {
    const template = fs.readFileSync(path.join(root, 'projets', 'templates', 'projets',
        'decomptes', '_attachement_form_content_test.html'), 'utf8');
    const dom = new JSDOM(template, { runScripts: 'outside-only' });
    t.after(() => dom.window.close());
    const { window } = dom;
    const style = window.document.createElement('style');
    style.textContent = templateStyles(path.join('decomptes', 'attachement_form.html'));
    window.document.head.append(style);
    const host = window.document.getElementById('attachement-tableview');
    host.innerHTML = '<div class="table-view-scroll"><table class="table-view-table"></table></div>';
    assert.equal(window.getComputedStyle(host.querySelector('.table-view-scroll')).maxHeight, '72vh');
    assert.equal(window.getComputedStyle(host.querySelector('table')).minWidth, 'max(1200px, 100%)');
});
