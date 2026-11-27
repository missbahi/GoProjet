/* static/projets/js/rapports-bdd-modal.js */
(function () {
    'use strict';

    if (window.__rapportBddModalInitialized) return;
    window.__rapportBddModalInitialized = true;

    window.ouvrirModalBDD = function (codeCategorie, labelCategorie) {
        const modal = document.getElementById('modalBDDConsultation');
        const title = document.getElementById('modalBDDTitle');
        const search = document.getElementById('modalBDDSearch');
        const tbody = document.getElementById('modalBDDTbody');
        const empty = document.getElementById('modalBDDEmpty');
        const count = document.getElementById('modalBDDCount');
        if (!modal || !tbody) return;

        if (title) title.textContent = 'Référentiel BDD : ' + labelCategorie;
        if (search) search.value = '';

        let list = [];
        const scriptEl = document.getElementById('referentiel-data-' + codeCategorie);
        if (scriptEl) {
            try { list = JSON.parse(scriptEl.textContent || '[]'); } catch (e) { list = []; }
        }

        tbody.innerHTML = '';
        if (list.length === 0) {
            empty?.classList.remove('hidden');
            if (count) count.textContent = '0 élément disponible';
        } else {
            empty?.classList.add('hidden');
            if (count) count.textContent = `${list.length} élément(s) disponible(s)`;

            // Construction par le DOM (textContent) : aucune donnée injectée en HTML.
            const cellule = (texte, classe) => {
                const td = document.createElement('td');
                if (classe) td.className = classe;
                td.textContent = texte;
                return td;
            };
            list.forEach(item => {
                const prix = parseFloat(item.prix) || 0;
                const prixFmt = prix.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' DH';
                const tr = document.createElement('tr');
                tr.append(
                    cellule(item.designation || ''),
                    cellule(item.unite || '-', 'text-center'),
                    cellule(prixFmt, 'text-right'),
                );
                const action = document.createElement('td');
                action.className = 'text-center';
                const bouton = document.createElement('button');
                bouton.type = 'button';
                bouton.className = 'app-btn-primary text-xs';
                bouton.innerHTML = '<i class="fas fa-plus mr-1"></i> Insérer';
                bouton.addEventListener('click', () => window.ajouterDepuisModalBDD(
                    codeCategorie, item.designation || '', item.unite || '', prix,
                ));
                action.appendChild(bouton);
                tr.appendChild(action);
                tbody.appendChild(tr);
            });
        }

        modal.classList.add('open');
    };

    window.fermerModalBDD = function () {
        document.getElementById('modalBDDConsultation')?.classList.remove('open');
    };

    window.filtrerModalBDD = function () {
        const q = (document.getElementById('modalBDDSearch')?.value || '').toLowerCase();
        const rows = document.querySelectorAll('#modalBDDTbody tr');
        let visible = 0;
        rows.forEach(tr => {
            const match = tr.textContent.toLowerCase().includes(q);
            tr.style.display = match ? '' : 'none';
            if (match) visible++;
        });
        const empty = document.getElementById('modalBDDEmpty');
        if (empty) {
            if (visible === 0 && rows.length > 0) empty.classList.remove('hidden');
            else empty.classList.add('hidden');
        }
        const count = document.getElementById('modalBDDCount');
        if (count) count.textContent = `${visible} élément(s) trouvé(s)`;
    };

    window.ajouterDepuisModalBDD = function (code, designation, unite, prix) {
        // Dérouler la catégorie
        const table = document.getElementById('depense-table-' + code);
        if (table?.classList.contains('hidden')) {
            table.classList.remove('hidden');
            const toggle = document.querySelector(`.categorie-toggle[data-target="depense-table-${code}"]`);
            toggle?.querySelector('.toggle-icon')?.classList.add('rotate-90');
        }

        // Ajouter une ligne
        document.querySelector(`.depense-add-btn[data-categorie="${code}"]`)?.click();

        // Remplir la dernière ligne
        const tbody = document.getElementById('depense-tbody-' + code);
        const rows = tbody?.querySelectorAll('tr');
        const last = rows?.[rows.length - 1];
        if (!last) return;

        const select = last.querySelector('.depense-ref-select');
        if (select) {
            window.remplirSelectReferentiel?.(select, code);
            // Filet de sécurité : si l'option est absente, on l'ajoute plutôt
            // que de laisser le sélecteur sur « — Sélectionner — ».
            if (![...select.options].some(o => o.value === designation)) {
                const opt = new Option(designation, designation);
                opt.dataset.unite = unite;
                opt.dataset.prix = String(prix);
                select.appendChild(opt);
            }
            select.value = designation;
        }
        const d = last.querySelector('input[name$="-designation"]');
        const u = last.querySelector('input[name$="-unite"]');
        const p = last.querySelector('input[name$="-prix_unitaire"]');
        if (d) d.value = designation;
        if (u) u.value = unite;
        if (p) { p.value = prix; p.dispatchEvent(new Event('input', { bubbles: true })); }

        fermerModalBDD();
    };

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') fermerModalBDD();
    });

})();