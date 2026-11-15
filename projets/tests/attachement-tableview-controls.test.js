const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

test('Attachment file selection and reopening work without legacy handlers', t => {
    const dom = new JSDOM(`
        <form id="attachement-form"></form>
        <button id="reouvrir-btn" type="button">Réouvrir</button>
        <div id="attachement-tableview" data-editable="true" data-reopen-url="#reopened"></div>
        <div id="attachement-tableview-error" hidden></div>
        <div id="total_attachement"></div><div id="selectionSumDisplay"></div>
        <input id="fichier" type="file"><input id="original_filename">
        <script id="attachement-tableview-data" type="application/json"></script>
    `, { runScripts: 'outside-only', url: 'https://example.test/' });
    t.after(() => dom.window.close());
    const { window } = dom;
    const { document } = window;
    document.getElementById('attachement-tableview-data').textContent = JSON.stringify('[]');
    const jsDir = path.join(__dirname, '..', '..', 'goProjet', 'static', 'projets', 'js');
    window.eval(fs.readFileSync(path.join(jsDir, 'table-view.js'), 'utf8'));
    window.eval(fs.readFileSync(path.join(jsDir, 'attachement-tableview.js'), 'utf8'));
    document.dispatchEvent(new window.Event('DOMContentLoaded'));
    assert.equal(document.getElementById('attachement-tableview-error').hidden, true);

    const file = document.getElementById('fichier');
    Object.defineProperty(file, 'files', { value: [new window.File(['x'], 'preuve.txt')] });
    file.dispatchEvent(new window.Event('change'));
    assert.equal(document.getElementById('original_filename').value, 'preuve.txt');

    const reopen = document.getElementById('reouvrir-btn');
    window.confirm = () => false;
    reopen.click();
    assert.equal(reopen.disabled, false);
    assert.equal(window.location.hash, '');
    window.confirm = () => true;
    reopen.click();
    assert.equal(reopen.disabled, true);
    assert.equal(window.location.hash, '#reopened');
});
