/**
 * GoPlan — Formulaire calendrier : gestion des exceptions
 *
 * IDs utilisés (template calendrier_form.html) :
 *   - #calendar-exceptions      : <tbody> des exceptions
 *   - #calendar-exception-template : <template> avec __prefix__ pour empty_form
 *   - #calendar-add-exception   : bouton "Ajouter une exception"
 *   - [name$="-TOTAL_FORMS"]    : management_form (compteur)
 */
(function () {
    'use strict';

    const tbody     = document.getElementById('calendar-exceptions');
    const template  = document.getElementById('calendar-exception-template');
    const addBtn    = document.getElementById('calendar-add-exception');
    const totalInput = document.querySelector('input[name$="-TOTAL_FORMS"]');

    if (!tbody || !template || !addBtn || !totalInput) {
        // La page n'est pas le formulaire calendrier — on sort proprement
        return;
    }

    // ══════════════════════════════════════════════════════════
    // ① SNIPPET D'INITIALISATION — marquer les lignes vides
    //    → À PLACER ICI, une seule fois, au chargement
    // ══════════════════════════════════════════════════════════
    tbody.querySelectorAll('tr').forEach(tr => {
        const dateInput = tr.querySelector('input[type="date"]');
        if (dateInput && !dateInput.value) {
            tr.classList.add('is-empty');
        }
    });

    // ══════════════════════════════════════════════════════════
    // ② Handler "Ajouter" — avec le snippet "retirer is-empty"
    // ══════════════════════════════════════════════════════════
    addBtn.addEventListener('click', () => {
        const index = Number(totalInput.value);
        const html  = template.innerHTML.replace(/__prefix__/g, index);

        const wrapper = document.createElement('tbody');
        wrapper.innerHTML = html;
        const row = wrapper.querySelector('tr');
        if (!row) return;

        // ══════════════════════════════════════════════════════
        // ② SNIPPET "retirer is-empty" — À PLACER ICI
        //    Juste après avoir récupéré la <tr> du wrapper
        // ══════════════════════════════════════════════════════
        row.classList.remove('is-empty');

        tbody.appendChild(row);
        totalInput.value = index + 1;

        // Focus sur le premier champ (confort UX)
        const firstInput = row.querySelector('input[type="date"], input[type="number"]');
        if (firstInput) {
            firstInput.focus();
        }
    });

    // ══════════════════════════════════════════════════════════
    // ③ Bonus — retirer is-empty dès que l'utilisateur saisit
    //    une date sur une ligne existante (facultatif mais propre)
    // ══════════════════════════════════════════════════════════
    tbody.addEventListener('input', (e) => {
        if (e.target.matches('input[type="date"]')) {
            const row = e.target.closest('tr');
            if (row && e.target.value) {
                row.classList.remove('is-empty');
            }
        }
    });
})();