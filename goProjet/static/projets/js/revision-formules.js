function renderFormulesRevision(racine) {
    if (!window.katex) {
        return;
    }
    racine.querySelectorAll('[data-formule-latex]').forEach((element) => {
        const formule = element.dataset.formuleLatex;
        if (!formule) {
            return;
        }
        window.katex.render(formule, element, {
            displayMode: !element.classList.contains(
                'formule-revision-texte--predefinie',
            ),
            throwOnError: false,
            strict: 'ignore',
        });
        ajusterLargeurFormule(element);
    });
}

const formulesObservees = new WeakSet();

function ajusterLargeurFormule(conteneur) {
    const katex = conteneur.querySelector('.katex');
    if (!katex) {
        return;
    }
    katex.style.fontSize = '';
    const tailleNaturelle = Number.parseFloat(
        window.getComputedStyle(katex).fontSize,
    );
    const largeurDisponible = conteneur.clientWidth;
    const largeurNaturelle = katex.scrollWidth;
    if (largeurDisponible > 0 && largeurNaturelle > largeurDisponible) {
        const minimum = conteneur.classList.contains(
            'formule-revision-texte--predefinie',
        ) ? 0.3 : 0.35;
        const ratio = Math.max(minimum, (largeurDisponible - 4) / largeurNaturelle);
        katex.style.fontSize = `${tailleNaturelle * ratio}px`;
    }
    if (!formulesObservees.has(conteneur) && window.ResizeObserver) {
        formulesObservees.add(conteneur);
        new ResizeObserver(() => {
            requestAnimationFrame(() => ajusterLargeurFormule(conteneur));
        }).observe(conteneur);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    renderFormulesRevision(document);
    initialiserApercuFormule();
    initialiserTableIndexRevision();
    initialiserCollageIndexRevision();
    initialiserRedimensionnementIndex();
    initialiserAjoutIndexTableau();
});

document.addEventListener('htmx:afterSwap', () => {
    renderFormulesRevision(document);
    initialiserApercuFormule();
    initialiserTableIndexRevision();
    initialiserCollageIndexRevision();
    initialiserRedimensionnementIndex();
    initialiserAjoutIndexTableau();
});

function initialiserTableIndexRevision() {
    document.querySelectorAll('.revision-index-tableview input[type="number"]')
        .forEach((input) => {
            if (input.dataset.tableNavigation === 'true') {
                return;
            }
            input.dataset.tableNavigation = 'true';
            input.addEventListener('keydown', (event) => {
                if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(
                    event.key,
                )) {
                    return;
                }
                const cellule = input.closest('td');
                const ligne = cellule.closest('tr');
                const indexColonne = Array.from(ligne.cells).indexOf(cellule);
                let cible;
                if (event.key === 'ArrowLeft') {
                    cible = ligne.cells[indexColonne - 1]?.querySelector('input');
                } else if (event.key === 'ArrowRight') {
                    cible = ligne.cells[indexColonne + 1]?.querySelector('input');
                } else {
                    const lignes = Array.from(ligne.parentElement.rows);
                    const indexLigne = lignes.indexOf(ligne)
                        + (event.key === 'ArrowDown' ? 1 : -1);
                    cible = lignes[indexLigne]?.cells[indexColonne]
                        ?.querySelector('input');
                }
                if (cible) {
                    event.preventDefault();
                    cible.focus();
                    cible.select();
                }
            });
        });
}

function jetonTableau() {
    if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID().replaceAll('-', '').slice(0, 10);
    }
    return Math.random().toString(36).slice(2, 12);
}

function initialiserAjoutIndexTableau() {
    document.querySelectorAll('.revision-index-tableview').forEach((conteneur) => {
        const table = conteneur.querySelector('table');
        if (!table || table.dataset.ajoutInitialise === 'true') {
            return;
        }
        table.dataset.ajoutInitialise = 'true';

        table.addEventListener('click', (event) => {
            if (event.target.closest('[data-add-index-column]')) {
                ajouterColonneIndex(table);
            }
            if (event.target.closest('[data-add-index-row]')) {
                ajouterLigneIndex(table);
            }
        });
    });
}

function ajouterColonneIndex(table) {
    const enteteAjout = table.querySelector('.revision-index-add-column');
    if (!enteteAjout) {
        return;
    }
    const token = jetonTableau();
    const nombreColonnes = table.querySelectorAll(
        'thead th[data-colonne-index]',
    ).length;
    const th = document.createElement('th');
    th.dataset.colonneIndex = String(nombreColonnes);
    th.dataset.nouveauMoisToken = token;
    const dernierCode = Array.from(table.querySelectorAll(
        'th[data-mois-code], th[data-nouveau-mois-token]',
    )).map((entete) => entete.dataset.moisCode).filter(Boolean).pop();
    const dernierNouveau = Array.from(table.querySelectorAll(
        'th[data-nouveau-mois-token] input[type="month"]',
    )).map((input) => input.value).filter(Boolean).pop();
    const reference = dernierNouveau || (
        dernierCode
            ? `${dernierCode.slice(0, 4)}-${dernierCode.slice(4, 6)}`
            : ''
    );
    let moisSuivant = '';
    if (reference) {
        const [annee, mois] = reference.split('-').map(Number);
        const suivante = new Date(annee, mois, 1);
        moisSuivant = `${suivante.getFullYear()}-${String(
            suivante.getMonth() + 1,
        ).padStart(2, '0')}`;
    }
    th.innerHTML = `
        <input type="month" class="revision-index-new-month"
               name="nouveau_mois_${token}" aria-label="Nouveau mois"
               value="${moisSuivant}">
        <select name="statut_mois_col_${token}"
                class="revision-index-statut">
            <option value="IND_DEF">Définitif</option>
            <option value="IND_PRO" selected>Provisoire</option>
        </select>
        <button type="button" class="revision-index-resize-handle"
                aria-label="Redimensionner le nouveau mois"
                title="Redimensionner"></button>
    `;
    enteteAjout.before(th);
    const ligneAjout = table.querySelector('.revision-index-add-row td');
    if (ligneAjout) {
        ligneAjout.colSpan += 1;
    }

    table.querySelectorAll('tbody tr:not(.revision-index-add-row)').forEach((tr) => {
        const celluleAjout = tr.querySelector('.revision-index-add-column-cell');
        const td = document.createElement('td');
        td.className = 'revision-index-cell is-numeric';
        const indexId = tr.querySelector('[data-index-id]')?.dataset.indexId;
        const tokenLigne = tr.dataset.newIndexToken;
        const nom = tokenLigne
            ? `valeur_nouvelle_ligne_${tokenLigne}_col_${token}`
            : `valeur_colonne_${token}_${indexId}`;
        td.innerHTML = `
            <input type="number" name="${nom}" step="0.0001" min="0"
                   inputmode="decimal" aria-label="Nouvelle valeur">
        `;
        celluleAjout.before(td);
    });
    table.closest('.revision-index-tableview')
        ?.querySelector('.revision-index-new-month:not([data-focus])')
        ?.setAttribute('data-focus', 'true');
    th.querySelector('input').focus();
    initialiserTableIndexRevision();
    delete table.dataset.redimensionnementInitialise;
    initialiserRedimensionnementIndex();
}

function ajouterLigneIndex(table) {
    const ligneAjout = table.querySelector('.revision-index-add-row');
    if (!ligneAjout) {
        return;
    }
    const token = jetonTableau();
    const tr = document.createElement('tr');
    tr.dataset.newIndexToken = token;
    const rowHeader = document.createElement('th');
    rowHeader.className = 'tv-row-header tv-frozen';
    rowHeader.scope = 'row';
    rowHeader.innerHTML = `
        <input type="text" name="nouvel_index_${token}_symbole"
               class="revision-index-new-label" maxlength="20"
               placeholder="Symbole" aria-label="Symbole du nouvel index">
        <input type="text" name="nouvel_index_${token}_libelle"
               class="revision-index-new-label" maxlength="200"
               placeholder="Libellé" aria-label="Libellé du nouvel index">
    `;
    tr.append(rowHeader);

    table.querySelectorAll(
        'thead th[data-mois-code], thead th[data-nouveau-mois-token]',
    ).forEach((entete) => {
        const td = document.createElement('td');
        td.className = 'revision-index-cell is-numeric';
        const code = entete.dataset.moisCode;
        const tokenMois = entete.dataset.nouveauMoisToken;
        const nom = code
            ? `valeur_nouvelle_ligne_${token}_${code}`
            : `valeur_nouvelle_ligne_${token}_col_${tokenMois}`;
        td.innerHTML = `
            <input type="number" name="${nom}" step="0.0001" min="0"
                   inputmode="decimal" aria-label="Nouvelle valeur">
        `;
        tr.append(td);
    });
    const celluleAjout = document.createElement('td');
    celluleAjout.className = 'revision-index-add-column-cell';
    tr.append(celluleAjout);
    ligneAjout.before(tr);
    tr.querySelector('input').focus();
    initialiserTableIndexRevision();
}

function parserValeurIndex(brut) {
    const nettoye = String(brut || '')
        .replace(/\s/g, '')
        .replace(/\u00a0/g, '')
        .replace(',', '.');
    if (!nettoye) {
        return '';
    }
    const valeur = Number.parseFloat(nettoye);
    if (!Number.isFinite(valeur) || valeur < 0) {
        throw new Error(`Valeur invalide : « ${brut} »`);
    }
    return String(valeur);
}

function initialiserCollageIndexRevision() {
    document.querySelectorAll('.revision-index-tableview').forEach((tableview) => {
        if (tableview.dataset.collageInitialise === 'true') {
            return;
        }
        tableview.dataset.collageInitialise = 'true';
        tableview.addEventListener('paste', (event) => {
            const origine = event.target.closest(
                '.revision-index-cell input[type="number"]',
            );
            const texte = event.clipboardData?.getData('text/plain');
            if (!origine || !texte || (!texte.includes('\t') && !texte.includes('\n'))) {
                return;
            }
            event.preventDefault();
            const statut = tableview.closest('form')
                ?.querySelector('[data-index-paste-status]');
            const matrice = texte
                .replace(/\r\n/g, '\n')
                .replace(/\r/g, '\n')
                .replace(/\n$/, '')
                .split('\n')
                .map((ligne) => ligne.split('\t'));
            const lignes = Array.from(
                tableview.querySelectorAll('tbody tr'),
            );
            const ligneOrigine = origine.closest('tr');
            const champsOrigine = Array.from(
                ligneOrigine.querySelectorAll('.revision-index-cell input'),
            );
            const ligneDepart = lignes.indexOf(ligneOrigine);
            const colonneDepart = champsOrigine.indexOf(origine);

            try {
                if (ligneDepart + matrice.length > lignes.length) {
                    throw new Error('Le collage dépasse le nombre de lignes disponibles.');
                }
                const changements = [];
                matrice.forEach((valeurs, offsetLigne) => {
                    const ligne = lignes[ligneDepart + offsetLigne];
                    const champs = Array.from(
                        ligne.querySelectorAll('.revision-index-cell input'),
                    );
                    if (colonneDepart + valeurs.length > champs.length) {
                        throw new Error('Le collage dépasse le nombre de mois disponibles.');
                    }
                    valeurs.forEach((brut, offsetColonne) => {
                        changements.push({
                            champ: champs[colonneDepart + offsetColonne],
                            valeur: parserValeurIndex(brut),
                        });
                    });
                });
                let derniere = origine;
                changements.forEach(({champ, valeur}) => {
                    champ.value = valeur;
                    champ.dispatchEvent(new Event('input', {bubbles: true}));
                    champ.dispatchEvent(new Event('change', {bubbles: true}));
                    derniere = champ;
                });
                derniere.focus();
                derniere.select();
                if (statut) {
                    statut.textContent = `${changements.length} valeur(s) collée(s) depuis le presse-papiers.`;
                    statut.style.color = 'var(--accent-success)';
                }
            } catch (error) {
                if (statut) {
                    statut.textContent = error.message;
                    statut.style.color = 'var(--accent-danger)';
                }
            }
        });
    });
}

function initialiserRedimensionnementIndex() {
    document.querySelectorAll('.revision-index-tableview').forEach((conteneur) => {
        const table = conteneur.querySelector('.table-view-table');
        if (!table || table.dataset.redimensionnementInitialise === 'true') {
            return;
        }
        table.dataset.redimensionnementInitialise = 'true';
        const projetId = document.querySelector('[data-revision-projet-id]')
            ?.dataset.revisionProjetId || 'global';
        const cleSession = `revision-index-largeurs-${projetId}`;
        let largeurs = {};
        try {
            largeurs = JSON.parse(sessionStorage.getItem(cleSession) || '{}');
        } catch {
            largeurs = {};
        }

        const appliquerLargeur = (index, largeur) => {
            table.querySelectorAll(
                `tr > :nth-child(${index + 1})`,
            ).forEach((cellule) => {
                cellule.style.width = `${largeur}px`;
                cellule.style.minWidth = `${largeur}px`;
                cellule.style.maxWidth = `${largeur}px`;
            });
        };

        table.querySelectorAll('thead th[data-colonne-index]').forEach((entete) => {
            const index = Number(entete.dataset.colonneIndex);
            if (largeurs[index]) {
                appliquerLargeur(index, largeurs[index]);
            }
            const poignee = entete.querySelector(
                '.revision-index-resize-handle',
            );
            if (!poignee || poignee.dataset.initialise === 'true') {
                return;
            }
            poignee.dataset.initialise = 'true';
            poignee.addEventListener('pointerdown', (event) => {
                event.preventDefault();
                const debutX = event.clientX;
                const largeurInitiale = entete.getBoundingClientRect().width;
                const minimum = index === 0 ? 120 : 76;
                poignee.setPointerCapture(event.pointerId);

                const deplacer = (moveEvent) => {
                    const largeur = Math.max(
                        minimum,
                        Math.round(largeurInitiale + moveEvent.clientX - debutX),
                    );
                    appliquerLargeur(index, largeur);
                    largeurs[index] = largeur;
                };
                const terminer = () => {
                    poignee.removeEventListener('pointermove', deplacer);
                    poignee.removeEventListener('pointerup', terminer);
                    poignee.removeEventListener('pointercancel', terminer);
                    try {
                        sessionStorage.setItem(
                            cleSession,
                            JSON.stringify(largeurs),
                        );
                    } catch {
                        // Le redimensionnement reste actif sans persistance.
                    }
                };
                poignee.addEventListener('pointermove', deplacer);
                poignee.addEventListener('pointerup', terminer);
                poignee.addEventListener('pointercancel', terminer);
            });
        });
    });
}

function texteIndex(selecteur) {
    const select = document.querySelector(selecteur);
    if (!select || !select.value) {
        return '';
    }
    return `\\mathrm{${select.options[select.selectedIndex].text.trim()}}`;
}

function decimalTexte(valeur) {
    const nombre = Number.parseFloat((valeur || '').replace(',', '.'));
    if (!Number.isFinite(nombre)) {
        return '';
    }
    return String(nombre);
}

function initialiserApercuFormule() {
    const formulaire = document.getElementById('revision-formule-form');
    const apercu = document.getElementById('revision-formule-apercu');
    if (!formulaire || !apercu || !window.katex) {
        return;
    }

    const actualiser = () => {
        const k = decimalTexte(formulaire.querySelector('[name="k"]')?.value);
        if (!k) {
            apercu.textContent = 'Complétez la partie fixe et les termes.';
            return;
        }
        const morceaux = [k];
        const total = Number.parseInt(
            formulaire.querySelector('[name$="-TOTAL_FORMS"]')?.value || '0',
            10,
        );
        for (let index = 0; index < total; index += 1) {
            const prefix = `termes-${index}`;
            if (formulaire.querySelector(`[name="${prefix}-DELETE"]`)?.checked) {
                continue;
            }
            const coefficient = decimalTexte(
                formulaire.querySelector(`[name="${prefix}-coefficient"]`)?.value,
            );
            const type = formulaire.querySelector(
                `[name="${prefix}-type_terme"]`,
            )?.value;
            if (!coefficient || !type) {
                continue;
            }
            let expression;
            if (type === 'COMPOSITE') {
                const a = texteIndex(`[name="${prefix}-index_composite_a"]`);
                const b = texteIndex(`[name="${prefix}-index_composite_b"]`);
                if (!a || !b) {
                    continue;
                }
                expression = `\\frac{${coefficient}${a}(1+${b})}{${a}_0(1+${b}_0)}`;
            } else {
                const simple = texteIndex(`[name="${prefix}-index_simple"]`);
                if (!simple) {
                    continue;
                }
                expression = `${coefficient}\\frac{${simple}}{${simple}_0}`;
            }
            morceaux.push(`+ ${expression}`);
        }
        window.katex.render(
            `P = P_0\\left(${morceaux.join(' ')}\\right)`,
            apercu,
            {displayMode: true, throwOnError: false, strict: 'ignore'},
        );
        ajusterLargeurFormule(apercu);
    };

    formulaire.addEventListener('input', actualiser);
    formulaire.addEventListener('change', actualiser);
    actualiser();
}
