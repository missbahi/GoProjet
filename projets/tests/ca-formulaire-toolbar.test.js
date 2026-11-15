const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const rootPath = path.join(__dirname, '..', '..');

function mount(t, disabled = false) {
    let template = fs.readFileSync(path.join(rootPath, 'projets', 'templates', 'projets',
        'ca', 'formulaire.html'), 'utf8');
    const controls = {
        mois: `<input type="month" name="mois" value="2025-01" required ${disabled ? 'disabled' : ''}>`,
        origine: `<select name="origine" ${disabled ? 'disabled' : ''}><option value="REPRISE">Reprise</option></select>`,
        observations: `<textarea name="observations" ${disabled ? 'disabled' : ''}>Correction</textarea>`,
    };
    for (const [name, control] of Object.entries(controls)) {
        template = template.replace(`{{ form.${name}.label_tag }}`, `<label>${name}</label>`);
        template = template.replace(`{{ form.${name} }}`, control);
    }
    const dom = new JSDOM(template.replace(/\{%[\s\S]*?%\}/g, '').replace(/\{\{[\s\S]*?\}\}/g, ''),
        { runScripts: 'outside-only' });
    t.after(() => dom.window.close());
    return dom.window;
}

test('CA controls stay in the form toolbar in edit and read-only modes', t => {
    for (const disabled of [false, true]) {
        const { document } = mount(t, disabled);
        const toolbar = document.querySelector('#ca-form .ca-selection-toolbar');
        for (const name of ['mois', 'origine', 'observations']) {
            const field = document.querySelector(`[name="${name}"]`);
            assert.ok(toolbar.contains(field));
            assert.equal(field.disabled, disabled);
            assert.equal(field.closest('form').id, 'ca-form');
        }
    }
});

test('CA fullscreen keeps toolbar values accessible and native invalid handling active', async t => {
    const window = mount(t);
    const { document } = window;
    const root = document.querySelector('[data-ca-editor]');
    const toolbar = root.querySelector('.ca-selection-toolbar');
    const month = toolbar.querySelector('[name="mois"]');
    const origin = toolbar.querySelector('[name="origine"]');
    const observations = toolbar.querySelector('[name="observations"]');
    assert.equal(month.closest('[data-fullscreen-fields]'), null);
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
    window.eval(fs.readFileSync(path.join(rootPath, 'goplan', 'static', 'goplan',
        'js', 'planning-fullscreen.js'), 'utf8'));
    root.querySelector('[data-planning-fullscreen]').click();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(root.hasAttribute('data-workspace-fullscreen'), true);
    assert.equal(month.value, '2025-01');
    assert.equal(origin.value, 'REPRISE');
    assert.equal(observations.value, 'Correction');
    month.value = '';
    const invalid = new window.Event('invalid', { cancelable: true });
    assert.equal(month.dispatchEvent(invalid), true);
    assert.equal(root.hasAttribute('data-workspace-fullscreen'), true);
    month.value = '2025-02';
    root.querySelector('[data-planning-fullscreen]').click();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(month.value, '2025-02');
    assert.equal(observations.value, 'Correction');
    assert.equal(root.hasAttribute('data-workspace-fullscreen'), false);
});
