const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

for (const kind of ['Affectation', 'Atelier']) {
    test(`editing ${kind} posts even when a hidden field shadows form.id`, () => {
        const formId = `edit${kind}Form`;
        const listeners = {};
        const requests = [];
        const form = {
            id: { tagName: 'INPUT', name: 'id', value: '42' },
            matches: selector => selector === `form#${formId}`,
            querySelectorAll: () => [],
            querySelector: () => null,
        };
        const elements = {
            [formId]: form,
            [`edit${kind}Id`]: { value: '42' },
            'editMateriel': { value: '7' },
            'editMaterielInput': {
                value: 'Materiel test',
                dataset: { initialLabel: 'Materiel test', initialId: '7' },
                classList: { remove() {} },
            },
            'editDateDebut': { value: '2026-10-01' },
            'editAtelierCode': { value: 'AT01' },
            'editAtelierLibelle': { value: 'Atelier test' },
            'editAtelierActif': { checked: true },
            [`${kind.toLowerCase()}-config`]: {
                dataset: { editTemplate: '/modifier/0/' },
            },
        };
        const context = {
            window: {},
            document: {
                readyState: 'loading',
                cookie: '',
                getElementById: id => elements[id] || null,
                querySelector: () => null,
                addEventListener: (event, handler) => { listeners[event] = handler; },
                body: { addEventListener() {} },
            },
            FormData: class extends Map {
                constructor(source) {
                    super();
                    assert.equal(source, form);
                }
            },
            fetch: (url, options) => {
                requests.push({ url, options });
                return new Promise(() => {});
            },
            console,
        };
        const filename = path.join(__dirname, '..', 'goProjet', 'static', 'projets',
            'js', `${kind.toLowerCase()}-modal.js`);
        vm.runInNewContext(fs.readFileSync(filename, 'utf8'), context);

        let prevented = false;
        listeners.submit({ target: form, preventDefault() { prevented = true; } });
        assert.equal(prevented, true);
        assert.equal(requests.length, 1);
        assert.equal(requests[0].url, '/modifier/42/');
        assert.equal(requests[0].options.method, 'POST');
        assert.equal(requests[0].options.headers['X-Requested-With'], 'XMLHttpRequest');
        if (kind === 'Affectation') {
            assert.equal(requests[0].options.body.get('materiel'), '7');
        }

        prevented = false;
        listeners.submit({
            target: { matches: () => false },
            preventDefault() { prevented = true; },
        });
        assert.equal(prevented, false);
        assert.equal(requests.length, 1);
    });
}
