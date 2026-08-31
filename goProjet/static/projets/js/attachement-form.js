    // Le script JavaScript reste identique car il n'affecte pas la responsivité
    const container = document.getElementById('hot');
    const hotData = JSON.parse('{{ lignes|escapejs }}');
    const isEdition = {% if is_edition %}true{% else %}false{% endif %};
    const attachementId = {% if is_edition %}{{ attachement.id }}{% else %}null{% endif %}; 
    const estValidable =  {% if is_edition %}{% if attachement.est_validable %}true{% else %}false{% endif %}
                          {% else %}true{% endif %}; 
    
    // Variables globales
    const modifiedCells = new Set();
    let hot;

    // ==================== FONCTIONS UTILITAIRES ====================
    function updateOriginalFilename(input) {
        if (input.files && input.files[0]) {
            const originalFilename = input.files[0].name;
            document.getElementById('original_filename').value = originalFilename;
        }
    }
    function formatNumber(value, decimals = 2) {
        return value.toLocaleString('en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    function showSumSelectedCells(hotInstance) {
        const selection = hotInstance.getSelected();
        if (!selection) return;
        
        let [startRow, startCol, endRow, endCol] = selection[0];

        // Ajuster si nécessaire
        if (startRow > endRow) [startRow, endRow] = [endRow, startRow];
        if (startCol > endCol) [startCol, endCol] = [endCol, startCol];

        let sum = 0;
        let cellCount = 0;
        
        for (let row = startRow; row <= endRow; row++) {
            for (let col = startCol; col <= endCol; col++) {
                // if (col < 3 || col > 7) continue;
                
                const rowData = hotInstance.getSourceDataAtRow(row);
                let value = 0;
                
                if (col < colMontantIndex) { 
                    value = parseFloat(hotInstance.getDataAtCell(row, col)) || 0;
                } else { // montant
                    const pu = parseFloat(rowData.prix_unitaire) || 0;
                    const qte = parseFloat(rowData.quantite_realisee) || 0;
                    value = qte * pu;
                }
                
                if (!isNaN(value) && value !== 0) {
                    sum += value;
                    cellCount++;
                }
            }
        }
        return { sum, cellCount };
    }

    function displaySelectionSum() {
        const result = showSumSelectedCells(hot);
        const displayElement = document.getElementById('selectionSumDisplay');
        if (result && result.cellCount > 1) {
            const formattedSum = formatNumber(result.sum);
            const average = formatNumber(result.sum / result.cellCount) || 0;
            displayElement.textContent = `Somme : ${formattedSum} | Moyenne : ${average} | (${result.cellCount} cellules)`;
            displayElement.style.display = 'block';
        } else {
            displayElement.style.display = 'none';
        }
    }

    function updateTotal() {
        let total = 0;
        const data = hot.getSourceData();
                
        data.forEach((row) => {
            const isTitle = row.is_title;
            if (isTitle) return;
            
            const qte = parseFloat(row.quantite_realisee) || 0;
            const pu = parseFloat(row.prix_unitaire) || 0;
            const montant = qte * pu;
            
            total += montant;
        });
        
        const totalFormatted = formatNumber(total, 2);
        const totalElement = document.getElementById('total_attachement');
        totalElement.innerHTML = `<strong>${totalFormatted} DH</strong>`;
        totalElement.style.color = '#22d3ee';            
    }

    // ==================== FONCTIONS DE VALIDATION ====================

    function validerFormulaire() {
        const numero = document.getElementById('numero').value;
        const dateEtablissement = document.getElementById('date_etablissement').value;
        const dateDebut = document.getElementById('date_debut_periode').value;
        const dateFin = document.getElementById('date_fin_periode').value;
        
        if (!numero || !dateEtablissement || !dateDebut || !dateFin) {
            alert('Veuillez remplir tous les champs obligatoires (*)');
            return false;
        }
        
        const hasValidData = hot.getSourceData().some(row => {
            const isTitle = row.is_title;
            const quantite = parseFloat(row.quantite_realisee) || 0;
            return !isTitle && quantite > 0;
        });
        
        if (!hasValidData) {
            alert('Veuillez saisir au moins une quantité à attacher');
            return false;
        }
        
        return true;
    }

    function preparerDonneesLignes() {
        const lignesData = hot.getSourceData().map(row => ({
            id: row.id,
            quantite_realisee: parseFloat(row.quantite_realisee) || 0,
            {% if not is_edition %}
            inclure_titre: row.inclure_titre || false,
            is_title: row.est_titre || false
            {% endif %}
        }));

        let hiddenInput = document.getElementById('lignes-hidden');
        if (!hiddenInput) {
            hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'lignes_attachement';
            hiddenInput.id = 'lignes-hidden';
            document.getElementById('attachement-form').appendChild(hiddenInput);
        }
        hiddenInput.value = JSON.stringify(lignesData);
    }

    function afficherLoading(button, texte) {
        if (button) {
            button.disabled = true;
            button.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${texte}`;
        }
    }

    // ==================== FONCTIONS D'ACTION ====================

    function reouvrirAttachement(attachementId) {
        if (!attachementId) return;
        
        if (confirm("Êtes-vous sûr de vouloir réouvrir cet attachement validé ?\n\nCette action :\n- Réinitialisera le statut à 'Brouillon'\n- Réinitialisera toutes les validations\n- Rendrera l'attachement à nouveau modifiable")) {
            const button = document.getElementById('reouvrir-btn');
            afficherLoading(button, 'Réouverture...');
            window.location.href = "{% if is_edition %}{% url 'projets:reouvrir_attachement' attachement.id %}{% endif %}";
        }
    }

    function soumettreFormulaire(action, texteLoading) {
        // Valider le formulaire
        if (!validerFormulaire()) {
            return false;
        }
        
        // Préparer les données du tableau
        preparerDonneesLignes();
        
        // Afficher le loading sur tous les boutons d'action
        const saveBtn = document.getElementById('save-btn');
        const transmettreBtn = document.getElementById('transmettre-btn');
        
        if (saveBtn) afficherLoading(saveBtn, texteLoading);
        if (transmettreBtn) afficherLoading(transmettreBtn, texteLoading);
        
        // Soumettre le formulaire
        console.log(`${action} de l'attachement...`);
        document.getElementById('attachement-form').submit();
        
        return true;
    }
    
    function hierarchyRenderer(instance, td, row, col, prop, value, cellProperties) {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        
        const rowData = instance.getSourceDataAtRow(row);
        if (!rowData) return;
        
        const niveau = rowData.niveau || 0;
        const isTitle = rowData.is_title || false;
        if (isTitle) {
            td.className = td.className + ' title-row';
        }
        if (prop === 'designation') { // Colonne Désignation
            const indent = niveau * 8;
            td.style.paddingLeft = `${8 + indent}px`;
        } else if (prop === 'unite') { // Colonne Numéro
            td.className = td.className + ' htCenter';
        } 
    }
    // ==================== CONFIGURATION HANDSONTABLE ====================

    const hotConfig = {
        data: hotData,
        columns: [
            { data: 'numero', title: 'N°', readOnly: true, width: 80 },
            { data: 'niveau', title: 'Niveau', readOnly: true, width: 80 },
            { data: 'est_titre', title: 'Titre', readOnly: true, width: 80 },
            { data: 'designation', title: 'Désignation', readOnly: true, width: 400, renderer: hierarchyRenderer },
            { data: 'unite', title: 'Unité', readOnly: true, width: 100, className: 'htCenter' },
            { data: 'quantite_prevue', title: 'Quantité<br>marché', readOnly: true, type: 'numeric', numericFormat: { pattern: '0,0.000' }, width: 120 },
            { data: 'prix_unitaire', title: 'PU', readOnly: true, type: 'numeric', numericFormat: { pattern: '0,0.00' }, width: 120 },
            { data: 'quantite_deja_realisee', 
                title: 'Quantité<br>attachée', 
                readOnly: true, 
                type: 'numeric', 
                width: 100,
                className: 'editable-quantity-attachee',
                numericFormat: { pattern: '0,0.000' }, 
                renderer: function(instance, td, row, col, prop, value, cellProperties) {
                    Handsontable.renderers.NumericRenderer.apply(this, arguments);
                    const qte_r = value || 0;
                    if (qte_r === 0) td.textContent = '';
                },
            },
            { data: 'quantite_realisee', 
                title: isEdition ? 'Quantité<br>à modifier' : 'Quantité<br>à attacher', 
                type: 'numeric', 
                className: 'editable-quantity', 
                width: 140, 
                numericFormat: { pattern: '0,0.000' },
                readOnly: !estValidable,
                renderer: function(instance, td, row, col, prop, value, cellProperties) {
                    Handsontable.renderers.NumericRenderer.apply(this, arguments);
                    const qte_r = value || 0;
                    if (qte_r === 0) {
                        td.textContent = '';
                        return;
                    }
                    if (modifiedCells.has(`${row}-${col}`)) {
                        td.className = td.className + ' modified-cell';
                    }
                },
            },
            { data: 'montant', 
                title: 'Montant<br>attaché(HT)', 
                readOnly: true, 
                type: 'numeric', 
                numericFormat: { pattern: '0,0.00' }, 
                width: 140,
                renderer: function(instance, td, row, col, prop, value, cellProperties) {
                    const rowData = instance.getSourceDataAtRow(row);
                    const isTitle = rowData ? rowData.is_title : false;
                    
                    if (isTitle) {
                        td.textContent = '';
                        return;
                    }
                    
                    const pu = parseFloat(rowData.prix_unitaire) || 0;
                    const qte = parseFloat(rowData.quantite_realisee) || 0;
                    const total = qte * pu;
                    
                    if (total === 0 || isNaN(total)) {
                        td.textContent = '';
                        return;
                    }
                    
                    Handsontable.renderers.NumericRenderer.apply(this, arguments);
                    td.textContent = total.toLocaleString('en-US', { minimumFractionDigits: 2 });
                    td.className = 'htRight';
                    td.style.fontWeight = '600';
                    td.style.color = '#2B9C62';
                }
            },
        ],
        colHeaders: true,
        rowHeaders: false,
        hiddenColumns: {columns: [1, 2], indicators: false},
        manualColumnResize: true,
        licenseKey: 'non-commercial-and-evaluation',
        contextMenu: false,
        height: 'auto',
        stretchH: 'all',
        manualRowResize: true,
        rowHeights: 40,
        afterChange: estValidable ? function(changes, source) {            
            if (changes) {
                changes.forEach(function(change) {
                    const [row, prop, oldValue, newValue] = change;
                    if (prop === 'quantite_realisee' && newValue !== oldValue) {
                        const col = hot.propToCol(prop);
                        modifiedCells.add(`${row}-${col}`);
                        setTimeout(() => hot.render(), 0);
                    }
                });
                updateTotal();
            }
        } : null,
        beforeChange: estValidable ? function(changes, source) {
            if (!changes) return true;
            
            changes.forEach(function(change) {
                const [row, prop, oldValue, newValue] = change;
                
                // Nettoyer les espaces
                if (newValue !== null && typeof newValue === 'string') {
                    change[3] = newValue.replace(/\s/g, '');
                }
                
                // Validation : empêcher les valeurs négatives
                if (prop === 'quantite_realisee' && parseFloat(newValue) < 0) {
                    alert("Les quantités négatives ne sont pas autorisées");
                    return false;
                }
            });
            return true;
        } : null,
        afterSelection: displaySelectionSum,
        afterDeselect: function() {
            const displayElement = document.getElementById('selectionSumDisplay');
            if (displayElement) displayElement.style.display = 'none';
        },
    };
    const colMontantIndex = hotConfig.columns.findIndex(col => col.data === 'montant');
    // ==================== GESTION DES BOUTONS ====================

    function setupSaveButton() {
        const saveBtn = document.getElementById('save-btn');
        if (!saveBtn) return;

        saveBtn.addEventListener('click', function(e) {
            e.preventDefault();
            soumettreFormulaire(
                'Sauvegarde', 
                '{% if is_edition %}Modification{% else %}Création{% endif %}...'
            );
        });
    }

    function setupTransmissionButton() {
        const transmettreBtn = document.getElementById('transmettre-btn');
        if (!transmettreBtn) return;

        transmettreBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            if (confirm("Êtes-vous sûr de vouloir transmettre cet attachement pour validation ?\n\nCette action :\n- Sauvegardera toutes les modifications\n- Changera le statut à 'Transmis'\n- Lancera le processus de validation")) {
                
                // Changer le statut avant soumission
                const statutInput = document.getElementById('statut');
                if (statutInput) statutInput.value = 'TRANSMIS';
                
                // Soumettre avec validation et préparation des données
                soumettreFormulaire('Transmission', 'Transmission...');
            }
        });
    }

    function setupDeleteButton() {
        const deleteBtn = document.getElementById('delete-btn');
        if (!deleteBtn) return;

        deleteBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            if (confirm("Êtes-vous sûr de vouloir supprimer cet attachement ? Cette action est irréversible.")) {
                const deleteForm = document.createElement('form');
                deleteForm.method = 'POST';
                deleteForm.action = "{% if is_edition %}{% url 'projets:supprimer_attachement' attachement.id %}{% endif %}";
                
                const csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrfmiddlewaretoken';
                csrfInput.value = '{{ csrf_token }}';
                
                deleteForm.appendChild(csrfInput);
                document.body.appendChild(deleteForm);
                deleteForm.submit();
            }
        });
    }

    // ==================== INITIALISATION ====================

    function initHandsontable() {
        if (container) {
            hot = new Handsontable(container, hotConfig);
            updateTotal();
        }
    }

    function initMessagesAutoDismiss() {
        setTimeout(() => {
            const alerts = document.querySelectorAll('.alert-auto-dismiss');
            alerts.forEach(alert => {
                alert.style.display = 'none';
            });
        }, 5000);
    }

    function initEventListeners() {
        setupSaveButton();
        setupTransmissionButton();
        setupDeleteButton();
    }

    // Initialisation principale
    document.addEventListener('DOMContentLoaded', function() {
        initHandsontable();
        initEventListeners();
        initMessagesAutoDismiss();
    });
