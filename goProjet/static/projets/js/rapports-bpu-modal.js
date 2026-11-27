/* static/projets/js/rapports-bpu-modal.js
 * Fenêtre « Lignes BPU » du rapport journalier : choix de prestations du
 * bordereau (prix unitaire > 0), ajoutées en lignes de travaux liées à leur prix.
 * Données chargées à l'ouverture (data-url de #modalBPU) pour la date saisie :
 * réalisé à date = dernier cumul officiel + rapports postérieurs, rapport ouvert
 * exclu. Rendu par le DOM (textContent uniquement : aucune donnée injectée en HTML).
 */
(function () {
    'use strict';

    if (window.__rapportBpuModalInitialized) return;
    window.__rapportBpuModalInitialized = true;

    const fmtNombre = (valeur, decimales) => (Number.parseFloat(valeur) || 0).toLocaleString('fr-FR', {
        minimumFractionDigits: decimales, maximumFractionDigits: decimales,
    });
    const selection = new Set();
    let lignes = [];
    let dateChargee = null;

    function donnees() {
        return lignes;
    }

    function dateDuRapport() {
        return document.querySelector('form input[name="date"]')?.value || '';
    }

    function message(texte) {
        const vide = document.getElementById('modalBPUEmpty');
        if (!vide) return;
        vide.classList.toggle('hidden', !texte);
        vide.textContent = texte || '';
    }

    async function charger() {
        const modal = document.getElementById('modalBPU');
        const jour = dateDuRapport();
        if (!modal?.dataset.url || !jour) {
            lignes = [];
            return 'Renseignez la date du rapport pour afficher les lignes du bordereau.';
        }
        if (jour === dateChargee) return null;
        const params = new URLSearchParams({ date: jour });
        if (modal.dataset.rapport) params.set('rapport', modal.dataset.rapport);
        try {
            const reponse = await fetch(`${modal.dataset.url}?${params}`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            const data = await reponse.json();
            if (!data.success) return data.message || 'Lignes du bordereau indisponibles.';
            lignes = data.lignes || [];
            dateChargee = jour;
            selection.clear();
            return null;
        } catch (e) {
            return 'Lignes du bordereau indisponibles.';
        }
    }

    function element(tag, { texte, classe, titre } = {}) {
        const el = document.createElement(tag);
        if (classe) el.className = classe;
        if (texte !== undefined) el.textContent = texte;
        if (titre) el.title = titre;
        return el;
    }

    function detailRealise(ligne) {
        const parties = [];
        if (ligne.source) {
            const au = ligne.date_base ? ` au ${ligne.date_base.split('-').reverse().join('/')}` : '';
            parties.push(`${ligne.source}${au} : ${fmtNombre(ligne.officiel, 2)}`);
        } else {
            parties.push('Aucun attachement validé ni CA à cette date');
        }
        parties.push(`Rapports journaliers ${ligne.source ? 'postérieurs' : 'cumulés'} : ${fmtNombre(ligne.rapports_apres, 2)}`);
        if (ligne.provisoire) parties.push('Provisoire : CA en brouillon');
        return parties.join('\n');
    }

    function celluleAvancement(ligne) {
        const realise = Number.parseFloat(ligne.realise) || 0;
        const marche = Number.parseFloat(ligne.quantite_marche) || 0;
        const td = element('td', { classe: 'text-right', titre: detailRealise(ligne) });
        const valeur = element('span', { texte: `${fmtNombre(realise, 2)} / ${fmtNombre(marche, 2)}` });
        if (ligne.provisoire) {
            valeur.textContent += ' *';
            valeur.style.color = 'var(--accent-warning)';
        }
        td.appendChild(valeur);
        if (marche > 0) {
            const pct = (realise / marche) * 100;
            const badge = element('span', {
                texte: ` ${fmtNombre(pct, 0)} %`,
                titre: pct > 100 ? 'Quantité du marché dépassée' : 'Avancement de ce prix',
            });
            badge.style.color = pct > 100 ? 'var(--accent-danger)' : 'var(--text-muted)';
            badge.style.fontSize = '0.75em';
            td.appendChild(badge);
        }
        return td;
    }

    function rendre() {
        const tbody = document.getElementById('modalBPUTbody');
        if (!tbody) return;
        tbody.replaceChildren();
        donnees().forEach(ligne => {
            const tr = document.createElement('tr');
            tr.dataset.id = String(ligne.id);
            tr.dataset.lot = ligne.lot;
            tr.dataset.recherche = `${ligne.numero} ${ligne.designation} ${ligne.unite} ${ligne.lot}`.toLowerCase();
            tr.style.cursor = 'pointer';

            const tdCase = element('td', { classe: 'text-center' });
            const caseACocher = document.createElement('input');
            caseACocher.type = 'checkbox';
            caseACocher.setAttribute('aria-label', `Choisir le prix ${ligne.numero}`);
            caseACocher.checked = selection.has(ligne.id);
            caseACocher.addEventListener('change', () => basculer(ligne.id, caseACocher.checked));
            tdCase.appendChild(caseACocher);

            const tdDesignation = element('td');
            tdDesignation.appendChild(element('div', { texte: ligne.designation }));
            tdDesignation.appendChild(element('div', { texte: ligne.lot, classe: 'text-xs' }))
                .style.color = 'var(--text-muted)';

            tr.append(
                tdCase,
                element('td', { texte: ligne.numero || '—', classe: 'cell-nowrap' }),
                tdDesignation,
                element('td', { texte: ligne.unite || '—', classe: 'text-center' }),
                element('td', { texte: fmtNombre(ligne.prix, 2), classe: 'text-right' }),
                celluleAvancement(ligne),
            );
            // Un clic sur la ligne coche/décoche (sauf sur la case elle-même).
            tr.addEventListener('click', (event) => {
                if (event.target === caseACocher) return;
                caseACocher.checked = !caseACocher.checked;
                basculer(ligne.id, caseACocher.checked);
            });
            tbody.appendChild(tr);
        });
    }

    function basculer(id, coche) {
        if (coche) selection.add(id); else selection.delete(id);
        majPied();
    }

    function lignesVisibles() {
        return Array.from(document.querySelectorAll('#modalBPUTbody tr')).filter(tr => tr.style.display !== 'none');
    }

    function filtrer() {
        const q = (document.getElementById('modalBPUSearch')?.value || '').trim().toLowerCase();
        const lot = document.getElementById('modalBPULot')?.value || '';
        let visibles = 0;
        document.querySelectorAll('#modalBPUTbody tr').forEach(tr => {
            const ok = (!q || tr.dataset.recherche.includes(q)) && (!lot || tr.dataset.lot === lot);
            tr.style.display = ok ? '' : 'none';
            if (ok) visibles++;
        });
        message(visibles > 0 ? '' : 'Aucune ligne trouvée.');
        majPied(visibles);
    }

    function majPied(visibles) {
        const total = donnees().length;
        const n = visibles ?? lignesVisibles().length;
        const compteur = document.getElementById('modalBPUCount');
        if (compteur) {
            compteur.textContent = `${n} / ${total} ligne(s) affichée(s) · ${selection.size} sélectionnée(s)`;
        }
        const bouton = document.getElementById('modalBPUAjouter');
        if (bouton) {
            bouton.disabled = selection.size === 0;
            bouton.lastChild.textContent = selection.size ? ` Ajouter la sélection (${selection.size})` : ' Ajouter la sélection';
        }
    }

    function remplirLots() {
        const select = document.getElementById('modalBPULot');
        if (!select) return;
        select.replaceChildren(new Option('Tous les lots', ''));
        const lots = [...new Set(donnees().map(l => l.lot))];
        lots.forEach(lot => select.appendChild(new Option(lot, lot)));
        select.hidden = lots.length < 2;
    }

    function ajouterSelection() {
        const container = document.getElementById('travaux-container');
        if (!container?.ajouterLigneBPU) return;
        // Ordre du bordereau, quel que soit l'ordre des clics.
        const choisies = donnees().filter(l => selection.has(l.id));
        let derniere = null;
        choisies.forEach(ligne => { derniere = container.ajouterLigneBPU(ligne) || derniere; });
        selection.clear();
        window.fermerModalBPU();
        // La quantité du jour reste à saisir : focus sur la première ligne ajoutée.
        const rows = document.querySelectorAll('#travaux-tbody tr');
        const premiere = rows[rows.length - choisies.length];
        (premiere || derniere)?.querySelector('input[name$="-quantite"]')?.focus();
    }

    window.ouvrirModalBPU = async function () {
        const modal = document.getElementById('modalBPU');
        if (!modal) return;
        modal.classList.add('open');
        const titre = document.getElementById('modalBPUTitle');
        const jour = dateDuRapport();
        if (titre) {
            titre.textContent = 'Lignes du bordereau des prix'
                + (jour ? ` — réalisé au ${jour.split('-').reverse().join('/')}` : '');
        }
        if (jour !== dateChargee) message('Chargement des lignes du bordereau…');
        const erreur = await charger();
        if (erreur) {
            document.getElementById('modalBPUTbody')?.replaceChildren();
            message(erreur);
            majPied(0);
            return;
        }
        remplirLots();
        rendre();
        const recherche = document.getElementById('modalBPUSearch');
        if (recherche) recherche.value = '';
        filtrer();
        recherche?.focus();
    };

    window.fermerModalBPU = function () {
        document.getElementById('modalBPU')?.classList.remove('open');
    };

    document.addEventListener('input', (event) => {
        if (event.target.id === 'modalBPUSearch') filtrer();
    });
    document.addEventListener('change', (event) => {
        if (event.target.id === 'modalBPULot') filtrer();
        if (event.target.id === 'modalBPUToutCocher') {
            const coche = event.target.checked;
            lignesVisibles().forEach(tr => {
                const caseACocher = tr.querySelector('input[type="checkbox"]');
                if (caseACocher) caseACocher.checked = coche;
                basculer(Number(tr.dataset.id), coche);
            });
        }
    });
    document.addEventListener('click', (event) => {
        if (event.target.closest('#modalBPUAjouter')) ajouterSelection();
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') window.fermerModalBPU();
    });
})();
