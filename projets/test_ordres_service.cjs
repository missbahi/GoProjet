const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

test('OSVD exposes duration, unit and motif using fresh type data after HTMX swaps', () => {
    const handlers = {};
    const bodyHandlers = {};
    const hidden = new Map();
    const controls = [{ disabled: false }, { disabled: false }];
    function element(id) {
        return {
            value: '',
            classList: {
                add(name) { if (name === 'hidden') hidden.set(id, true); },
                remove(name) { if (name === 'hidden') hidden.set(id, false); },
                toggle(name, enabled) { if (name === 'hidden') hidden.set(id, enabled); },
            },
            querySelectorAll: () => controls,
        };
    }
    const elements = Object.fromEntries([
        'type_os', 'champs_conditionnels', 'champ_duree', 'champ_montant',
        'type_os_info', 'prerequis_info', 'unicite_info', 'champs_avenant_delai',
    ].map(id => [id, element(id)]));
    const window = {};
    const document = {
        getElementById: id => elements[id],
        addEventListener: (name, handler) => { (handlers[name] ||= []).push(handler); },
        body: { addEventListener: (name, handler) => { bodyHandlers[name] = handler; } },
    };
    vm.runInNewContext(fs.readFileSync(
        path.join(__dirname, '..', 'goProjet', 'static', 'projets', 'js', 'ordres_service.js'), 'utf8',
    ), { window, document });
    // Les données peuvent arriver après le chargement initial du script.
    window.TYPES_OS_DATA = {
        1: { code: 'OSVD', showDuree: true, showMontant: false, prerequis: ['OSC'], unique: false },
        2: { code: 'AUTRE', showDuree: false, showMontant: false, prerequis: [], unique: false },
    };
    elements.type_os.value = '1';
    handlers.DOMContentLoaded[0]();
    assert.equal(hidden.get('champ_duree'), false);
    assert.equal(hidden.get('champs_avenant_delai'), false);
    assert.equal(controls.every(control => !control.disabled), true);
    elements.type_os.value = '2';
    bodyHandlers['htmx:afterSwap']({ detail: { target: { id: 'main-content' } } });
    assert.equal(hidden.get('champs_avenant_delai'), true);
    assert.equal(controls.every(control => control.disabled), true);
});
