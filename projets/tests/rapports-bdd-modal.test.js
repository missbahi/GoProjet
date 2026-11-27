const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const jsDir = path.join(__dirname, '..', '..', 'goProjet', 'static', 'projets', 'js');

function rowTemplate(cat) {
    return `<tr>
        <input type="hidden" name="depenses-__prefix__-categorie" value="${cat}">
        <td><select class="depense-ref-select"><option value="">— Sélectionner —</option></select>
            <input type="hidden" name="depenses-__prefix__-designation" value=""></td>
        <td><input name="depenses-__prefix__-quantite" value=""></td>
        <td><input name="depenses-__prefix__-unite" value=""></td>
        <td><input name="depenses-__prefix__-prix_unitaire" value=""></td>
        <td class="depense-montant"></td>
        <td><label class="depense-delete-trigger"><input type="checkbox" name="depenses-__prefix__-DELETE"></label></td>
    </tr>`;
}

function setup() {
    const dom = new JSDOM(`
        <input type="hidden" id="id_depenses-TOTAL_FORMS" value="0">
        <div id="depenses-categories" data-total-forms-id="id_depenses-TOTAL_FORMS">
          <div data-depense-categorie="PERSONNEL">
            <button type="button" class="categorie-toggle" data-target="depense-table-PERSONNEL"></button>
            <div id="depense-table-PERSONNEL" class="hidden">
              <table><tbody id="depense-tbody-PERSONNEL"></tbody></table>
              <button type="button" class="depense-add-btn" data-categorie="PERSONNEL"></button>
            </div>
          </div>
          <template id="depense-empty-form-template-PERSONNEL">${rowTemplate('PERSONNEL')}</template>
          <script id="referentiel-data-PERSONNEL" type="application/json">
            [{"designation": "Chef d'équipe", "unite": "J", "prix": "300.00"},
             {"designation": "Manœuvre", "unite": "J", "prix": "250.50"}]
          </script>
        </div>
        <div id="modalBDDConsultation"><h3 id="modalBDDTitle"></h3><input id="modalBDDSearch">
          <table><tbody id="modalBDDTbody"></tbody></table>
          <div id="modalBDDEmpty"></div><span id="modalBDDCount"></span></div>
    `, { runScripts: 'outside-only', url: 'https://example.test/' });
    const { window } = dom;
    window.eval(fs.readFileSync(path.join(jsDir, 'rapports-form.js'), 'utf8'));
    window.eval(fs.readFileSync(path.join(jsDir, 'rapports-bdd-modal.js'), 'utf8'));
    window.document.dispatchEvent(new window.Event('DOMContentLoaded'));
    return dom;
}

test('Insérer depuis la BDD met à jour le sélecteur de la nouvelle ligne', t => {
    const dom = setup();
    t.after(() => dom.window.close());
    const { window } = dom;
    const { document } = window;

    window.ouvrirModalBDD('PERSONNEL', 'Personnel');
    document.querySelectorAll('#modalBDDTbody button')[1].click();

    const row = document.querySelector('#depense-tbody-PERSONNEL tr:last-child');
    assert.equal(row.querySelector('.depense-ref-select').value, 'Manœuvre');
    assert.equal(row.querySelector('input[name$="-designation"]').value, 'Manœuvre');
    assert.equal(row.querySelector('input[name$="-unite"]').value, 'J');
    assert.equal(row.querySelector('input[name$="-prix_unitaire"]').value, '250.5');
});

test('La modale BDD affiche les désignations comme du texte, sans interpréter le HTML', t => {
    const dom = setup();
    t.after(() => dom.window.close());
    const { window } = dom;
    const { document } = window;
    document.getElementById('referentiel-data-PERSONNEL').textContent =
        JSON.stringify([{ designation: '<img src=x onerror="window.pwned=1">', unite: 'J', prix: '1' }]);

    window.ouvrirModalBDD('PERSONNEL', 'Personnel');

    assert.equal(document.querySelector('#modalBDDTbody img'), null);
    assert.match(document.querySelector('#modalBDDTbody td').textContent, /<img/);
});
