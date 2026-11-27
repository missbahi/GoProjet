const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const jsDir = path.join(__dirname, '..', '..', 'goProjet', 'static', 'projets', 'js');

const LIGNE_TRAVAIL = `<tr>
    <input type="hidden" name="lignes_travaux-__prefix__-id">
    <input type="hidden" name="lignes_travaux-__prefix__-ordre">
    <input type="hidden" name="lignes_travaux-__prefix__-ligne_bordereau">
    <td><span class="travail-bpu-badge hidden"><span class="travail-bpu-numero"></span>
        <button type="button" class="travail-bpu-delier"></button></span>
        <input name="lignes_travaux-__prefix__-designation"></td>
    <td><input name="lignes_travaux-__prefix__-quantite"></td>
    <td><input name="lignes_travaux-__prefix__-unite"></td>
    <td><input name="lignes_travaux-__prefix__-observations"></td>
    <td><input type="checkbox" name="lignes_travaux-__prefix__-DELETE" class="hidden">
        <button type="button" class="travail-delete-btn"></button></td>
</tr>`;

function setup(lignes) {
    const dom = new JSDOM(`
        <form>
        <input type="date" name="date" value="2026-11-22">
        <input type="hidden" id="id_lignes_travaux-TOTAL_FORMS" value="0">
        <div id="travaux-container" data-total-forms-id="id_lignes_travaux-TOTAL_FORMS">
            <button type="button" class="categorie-toggle" data-target="travaux-body"><i class="toggle-icon"></i></button>
            <div id="travaux-body" class="hidden">
                <table><tbody id="travaux-tbody"></tbody></table>
                <button type="button" class="travaux-add-btn"></button>
            </div>
            <template id="travail-empty-form-template">${LIGNE_TRAVAIL}</template>
        </div>
        </form>
        <div id="modalBPU" data-url="/api/lignes-bpu/" data-rapport="7">
            <h3 id="modalBPUTitle"></h3>
            <input id="modalBPUSearch"><select id="modalBPULot" hidden><option value="">Tous</option></select>
            <input type="checkbox" id="modalBPUToutCocher">
            <table><tbody id="modalBPUTbody"></tbody></table>
            <div id="modalBPUEmpty" class="hidden"></div><span id="modalBPUCount"></span>
            <button type="button" id="modalBPUAjouter" disabled><i></i> Ajouter la sélection</button>
        </div>
    `, { runScripts: 'outside-only', url: 'https://example.test/' });
    const { window } = dom;
    // Le serveur (api_lignes_bpu_rapport) est simulé : on enregistre les URL appelées.
    window.appels = [];
    window.fetch = async (url) => {
        window.appels.push(url);
        return { json: async () => ({ success: true, lignes }) };
    };
    window.eval(fs.readFileSync(path.join(jsDir, 'rapports-form.js'), 'utf8'));
    window.eval(fs.readFileSync(path.join(jsDir, 'rapports-bpu-modal.js'), 'utf8'));
    window.document.dispatchEvent(new window.Event('DOMContentLoaded'));
    return dom;
}

const LIGNES = [
    { id: 11, numero: '1.1', designation: 'Déblai en terrain meuble', unite: 'M3', prix: '35.00',
      quantite_marche: '1000.00', realise: '550.00', lot: 'Lot 1 Voirie',
      officiel: '500.00', source: 'Attachement n° 3 (validé)', date_base: '2026-10-31',
      rapports_apres: '50.00', provisoire: false },
    { id: 21, numero: '2.1', designation: 'Bordure T3', unite: 'ML', prix: '120.00',
      quantite_marche: '500.00', realise: '0', lot: 'Lot 2 Assainissement',
      officiel: '0', source: '', date_base: null, rapports_apres: '0', provisoire: false },
    { id: 22, numero: '2.2', designation: 'Regard 1x1', unite: 'U', prix: '2500.00',
      quantite_marche: '12.00', realise: '14', lot: 'Lot 2 Assainissement',
      officiel: '14', source: 'CA 10/2026 (brouillon)', date_base: '2026-10-31',
      rapports_apres: '0', provisoire: true },
];

test('Les lignes BPU cochées deviennent des lignes de travaux liées', async t => {
    const dom = setup(LIGNES);
    t.after(() => dom.window.close());
    const { window } = dom;
    const { document } = window;

    await window.ouvrirModalBPU();
    // Date du formulaire et rapport ouvert (exclu du cumul) transmis au serveur.
    assert.equal(window.appels.length, 1);
    assert.match(window.appels[0], /date=2026-11-22/);
    assert.match(window.appels[0], /rapport=7/);
    assert.match(document.getElementById('modalBPUTitle').textContent, /22\/11\/2026/);
    assert.equal(document.querySelectorAll('#modalBPUTbody tr').length, 3);
    // Détail du réalisé en infobulle ; CA en brouillon signalé.
    const cellules = document.querySelectorAll('#modalBPUTbody tr td:last-child');
    assert.match(cellules[0].title, /Attachement n° 3 \(validé\) au 31\/10\/2026/);
    assert.match(cellules[0].title, /postérieurs : 50,00/);
    assert.match(cellules[2].title, /Provisoire/);
    assert.equal(document.getElementById('modalBPULot').hidden, false);  // 2 lots : filtre visible

    // Clic sur la 3e ligne puis sur la 1re : ajout dans l'ordre du bordereau.
    document.querySelectorAll('#modalBPUTbody tr')[2].click();
    document.querySelectorAll('#modalBPUTbody tr')[0].click();
    assert.equal(document.getElementById('modalBPUAjouter').disabled, false);
    document.getElementById('modalBPUAjouter').click();

    const rows = document.querySelectorAll('#travaux-tbody tr');
    assert.equal(rows.length, 2);
    assert.equal(rows[0].querySelector('input[name$="-ligne_bordereau"]').value, '11');
    assert.equal(rows[0].querySelector('input[name$="-designation"]').value, 'Déblai en terrain meuble');
    assert.equal(rows[0].querySelector('input[name$="-unite"]').value, 'M3');
    assert.equal(rows[1].querySelector('input[name$="-ligne_bordereau"]').value, '22');
    assert.equal(rows[1].querySelector('.travail-bpu-numero').textContent, '2.2');
    assert.equal(rows[1].querySelector('.travail-bpu-badge').classList.contains('hidden'), false);
    assert.equal(document.getElementById('id_lignes_travaux-TOTAL_FORMS').value, '2');
    assert.equal(document.getElementById('travaux-body').classList.contains('hidden'), false);

    // Délier : le texte reste, le lien disparaît.
    rows[1].querySelector('.travail-bpu-delier').click();
    assert.equal(rows[1].querySelector('input[name$="-ligne_bordereau"]').value, '');
    assert.equal(rows[1].querySelector('input[name$="-designation"]').value, 'Regard 1x1');
});

test('Recherche et filtre par lot ; pas de rechargement pour la même date', async t => {
    const dom = setup(LIGNES);
    t.after(() => dom.window.close());
    const { window } = dom;
    const { document } = window;
    await window.ouvrirModalBPU();
    await window.ouvrirModalBPU();
    assert.equal(window.appels.length, 1);

    const recherche = document.getElementById('modalBPUSearch');
    recherche.value = 'bordure';
    recherche.dispatchEvent(new window.Event('input', { bubbles: true }));
    const visibles = [...document.querySelectorAll('#modalBPUTbody tr')].filter(tr => tr.style.display !== 'none');
    assert.deepEqual(visibles.map(tr => tr.dataset.id), ['21']);

    recherche.value = '';
    recherche.dispatchEvent(new window.Event('input', { bubbles: true }));
    const lot = document.getElementById('modalBPULot');
    lot.value = 'Lot 1 Voirie';
    lot.dispatchEvent(new window.Event('change', { bubbles: true }));
    const parLot = [...document.querySelectorAll('#modalBPUTbody tr')].filter(tr => tr.style.display !== 'none');
    assert.deepEqual(parLot.map(tr => tr.dataset.id), ['11']);
});

test('Les désignations sont affichées comme du texte', async t => {
    const dom = setup([{ id: 1, numero: '1', designation: '<img src=x onerror="window.pwned=1">', unite: 'U',
                         prix: '1', quantite_marche: '1', realise: '0', lot: 'Lot' }]);
    t.after(() => dom.window.close());
    await dom.window.ouvrirModalBPU();
    assert.equal(dom.window.document.querySelector('#modalBPUTbody img'), null);
    assert.match(dom.window.document.querySelector('#modalBPUTbody').textContent, /<img/);
});
