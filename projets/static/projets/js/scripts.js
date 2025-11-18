    const container = document.getElementById('hot');
    const data = JSON.parse('{{ lignes|escapejs }}');
    // NodeManager pour construire l'arbre
    class NodeManager {
        constructor() {
            this.nodes = new Map();
            this.idToRowIndex = new Map();
        }
        
        buildTree(data) {
            this.nodes.clear();
            this.idToRowIndex.clear();
            
            const root = { numero: "Root", designation: "{{ lot.nom }}", children: [] };
            const stack = [{ node: root, niveau: -1 }];
            
            data.forEach((row, index) => {
                if (!row || row.id === null) return;
                
                const currentNode = {
                    id: row.id,
                    numero: row.numero,
                    designation: row.designation,
                    unite: row.unite,
                    quantite: row.quantite,
                    pu: row.prix_unitaire,
                    montant: row.montant,
                    niveau: row.niveau,
                    est_titre: row.est_titre,
                    _expanded: row._expanded !== false,
                    children: []
                };
                
                this.nodes.set(row.id, currentNode);
                this.idToRowIndex.set(row.id, index);
                
                // Trouver le parent dans la stack
                while (stack.length > 0 && stack[stack.length - 1].niveau >= row.niveau) {
                    stack.pop();
                }
                
                const parent = stack[stack.length - 1].node;
                parent.children.push(currentNode);
                stack.push({ node: currentNode, niveau: row.niveau });
            });
            
            return root;
        }
        
        findNodeById(id) {
            return this.nodes.get(id) || null;
        }
        
        findRowIndexById(id) {
            return this.idToRowIndex.get(id) || -1;
        }
        
        getDirectChildrenIds(nodeId) {
            const node = this.findNodeById(nodeId);
            return node && node.children ? node.children.map(child => child.id) : [];
        }
        
        calculateChildTotal(node) {
            if (!node || !node.children) return 0;
            return node.children.reduce((total, child) => {
                return total + (child.est_titre ? this.calculateChildTotal(child) : (parseFloat(child.montant) || 0));
            }, 0);
        }
        
        updateFromTableData(data) {
            data.forEach((row, index) => {
                if (row && row.id) {
                    const node = this.findNodeById(row.id);
                    if (node) {
                        // Mettre à jour les propriétés modifiables
                        node.designation = row.designation;
                        node.unite = row.unite;
                        node.quantite = row.quantite;
                        node.pu = row.prix_unitaire;
                        node.montant = row.montant;
                    }
                    this.idToRowIndex.set(row.id, index);
                }
            });
        }
    }

    // Variables globales
    let hot;
    let nextTempId = 1000;
    let hiddenRowsState = [];
    let nodeManager = new NodeManager();
    // Renderers 
    function hierarchyRenderer(instance, td, row, col, prop, value, cellProperties) {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        
        const rowData = instance.getSourceDataAtRow(row);
        if (!rowData) return;
        
        const niveau = rowData.niveau || 0;
        const isTitle = rowData.est_titre || false;
        
        if (isTitle) {
            td.classList.add('title-row');
        }
        
        if (prop === 'designation') {
            const indent = niveau * 10;
            td.style.paddingLeft = `${10 + indent}px`;
            td.style.verticalAlign = 'middle';
            
            if (isTitle) {
                const node = nodeManager.findNodeById(rowData.id);
                const hasChildren = node && node.children && node.children.length > 0;
                
                if (hasChildren) {
                    const isExpanded = rowData._expanded !== false;
                    const triangleClass = isExpanded ? 'triangle-expanded' : 'triangle-collapsed';
                    td.innerHTML = `<span class="toggle-triangle ${triangleClass}" data-row="${row}"></span>${value}`;
                } else {
                    td.textContent = value || '';
                }
            } else {
                td.textContent = value || '';
            }
        } else if (prop === 'unite') {
            td.classList.add('htCenter');
        }
    }

    function numericRenderer(instance, td, row, col, prop, value, cellProperties) {
        Handsontable.renderers.NumericRenderer.apply(this, arguments);
        const rowData = instance.getSourceDataAtRow(row);
        const isTitle = rowData ? rowData.est_titre : false;
        
        if (isTitle) {
            td.textContent = '';
            td.classList.add('title-row');
        } else {
            const nv = value || 0;
            if (nv === 0) {
                td.textContent = ''; 
            }
        }
    }

    function montantRenderer(instance, td, row, col, prop, value, cellProperties) {
        const rowData = instance.getSourceDataAtRow(row);
        if (!rowData) return;
        
        const isTitle = rowData.est_titre || false;
        
        if (isTitle) {
            const node = nodeManager.findNodeById(rowData.id);
            const amount = node ? nodeManager.calculateChildTotal(node) : 0;
            td.textContent = amount === 0 ? '' : formatNumber(amount);
            instance.getSourceData()[row].montant = amount;
            td.classList.add('htRight', 'title-row');
        } else {
            const qte = parseFloat(instance.getDataAtRowProp(row, 'quantite')) || 0;
            const pu = parseFloat(instance.getDataAtRowProp(row, 'prix_unitaire')) || 0;
            const total = qte * pu;
            
            instance.getSourceData()[row].montant = total;
            td.textContent = isNaN(total) || total === 0 ? '' : formatNumber(total);
            td.classList.add('htRight', 'montant-cell');
        }        
    }

    // Fonctions utilitaires
    function formatNumber(value, decimals = 2) {
        return value.toLocaleString('fr-FR', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    function updateTotal() {
        const total = hot.getSourceData().reduce((sum, row) => {
            return row && !row.est_titre ? sum + (parseFloat(row.montant) || 0) : sum;
        }, 0);
        
        document.getElementById('total-lot').textContent = `${formatNumber(total, 2)} MAD`;
    }

    function recalcMontantLigne(row) {
        const rowData = hot.getSourceDataAtRow(row);
        if (!rowData) return;
        
        if (rowData.est_titre) {
            const node = nodeManager.findNodeById(rowData.id);
            const total = node ? nodeManager.calculateChildTotal(node) : 0;
            hot.setDataAtRowProp(row, 'montant', total, 'recalc');
        } else {
            const qte = parseFloat(hot.getDataAtRowProp(row, 'quantite')) || 0;
            const pu = parseFloat(hot.getDataAtRowProp(row, 'prix_unitaire')) || 0;
            const montant = qte * pu;
            hot.setDataAtRowProp(row, 'montant', montant, 'recalc');
        }
        updateTotal();
    }

    // Gestion de la sélection
    function getSafeSelection() {
        if (!hot) return null;
        
        const selected = hot.getSelected();
        if (!selected || selected.length === 0) return null;
        
        const [startRow, startCol, endRow, endCol] = selected[0];
        return {
            startRow: Math.min(startRow, endRow),
            endRow: Math.max(startRow, endRow),
            isSingleCell: (startRow === endRow && startCol === endCol)
        };
    }

    // Gestion de l'indentation
    function applyIndentation(selection, increment) {
        if (!selection) {
            alert("❌ Veuillez sélectionner une ligne");
            return;
        }
        
        for (let i = selection.startRow; i <= selection.endRow; i++) {
            const rowData = hot.getSourceDataAtRow(i);
            if (rowData) {
                const currentNiveau = rowData.niveau || 0;
                const newNiveau = increment > 0 ? currentNiveau + 1 : currentNiveau - 1;

                hot.setDataAtRowProp(i, 'niveau', newNiveau);
            }
        }
        setTimeout(() => hot.render(), 50);
    }

    function indente() { applyIndentation(getSafeSelection(), 1); }
    
    function desindente() { applyIndentation(getSafeSelection(), -1); }

    // Gestion des triangles
    function setupTriangleToggle() {
        hot.addHook('afterOnCellMouseDown', function(event, coords, TD) {
            if (event.target.classList.contains('toggle-triangle')) {
                event.stopPropagation();
                const row = parseInt(event.target.getAttribute('data-row'));
                toggleChildrenVisibility(row);
                return false;
            }
        });
    }

    function toggleChildrenVisibility(parentRow) {
        const parentData = hot.getSourceDataAtRow(parentRow);
        if (!parentData || !parentData.est_titre) return;
        
        const node = nodeManager.findNodeById(parentData.id);
        if (!node || !node.children || node.children.length === 0) return;
        
        const isExpanded = !(parentData._expanded !== false);
        parentData._expanded = isExpanded;
        hot.setDataAtRowProp(parentRow, '_expanded', isExpanded);
        
        const childIds = nodeManager.getDirectChildrenIds(parentData.id);
        const data = hot.getSourceData();
        
        // Mettre à jour l'état des lignes cachées
        if (isExpanded) {
            hiddenRowsState = hiddenRowsState.filter(rowIndex => {
                const rowData = data[rowIndex];
                return !childIds.includes(rowData.id);
            });
        } else {
            data.forEach((rowData, index) => {
                if (childIds.includes(rowData.id) && !hiddenRowsState.includes(index)) {
                    hiddenRowsState.push(index);
                }
            });
        }
        
        hot.updateSettings({ hiddenRows: { rows: hiddenRowsState } });
        hot.render(); // Forcer le rendu pour mettre à jour les triangles
    }

    // Configuration Handsontable
    const hotConfig = {
        data: data,
        columns: [
            {data: '_expanded', type: 'checkbox', title: 'e', width: 10},
            {data: 'numero', type: 'text', title: 'N°', width: 50, renderer: hierarchyRenderer},
            {data: 'niveau', type: 'text', title: 'N', width: 20, renderer: hierarchyRenderer},
            {data: 'est_titre', type: 'checkbox', title: 'T', width: 20, hidden: true},
            {data: 'designation', type: 'text', title: 'Désignation', width: 400, renderer: hierarchyRenderer},
            {data: 'unite', type: 'text', title: 'Unité', width: 100, renderer: hierarchyRenderer},
            {data: 'quantite', type: 'numeric', numericFormat: { pattern: '0,0.000' }, title: 'Quantité', width: 120, renderer: numericRenderer},
            {data: 'prix_unitaire', type: 'numeric', numericFormat: { pattern: '0,0.00' }, title: 'PU (DH)', width: 120, renderer: numericRenderer},
            {data: 'montant', type: 'numeric', readOnly: true, numericFormat: { pattern: '0,0.00' }, title: 'Montant (DH)', width: 140, renderer: montantRenderer}
        ],
        rowHeaders: false,
        colHeaders: true,
        licenseKey: 'non-commercial-and-evaluation',
        contextMenu: ['row_above', 'row_below', 'remove_row'],
        hiddenColumns: {columns: [0, 2, 3], indicators: false},
        hiddenRows: true,
        minSpareRows: 2,
        height: 'auto',
        width: 'auto',
        rowHeights: 40,
        manualColumnResize: true,
        manualRowResize: false,
        autoRowSize: false,
        outsideClickDeselects: false,
        persistentState: true,
            
        afterChange: function(changes, source) {
            if (changes) {
                changes.forEach(function(change) {
                    const [row, prop, oldValue, newValue] = change;
                    if (prop === 'est_titre' && newValue !== oldValue) {
                        setTimeout(() => hot.render(), 50);
                    }
                    if ((prop === 'quantite' || prop === 'prix_unitaire') && newValue !== oldValue) {
                        recalcMontantLigne(row);
                        nodeManager.updateFromTableData(hot.getSourceData());
                    }
                });
            }
        },
        
        beforeChange: function(changes, source) {
            if (!changes) return true;
            
            changes.forEach(function(change) {
                const [row, prop, oldValue, newValue] = change;
                
                if ((prop === 'quantite' || prop === 'prix_unitaire') && newValue !== null) {
                    if (parseFloat(newValue) < 0) {
                        alert("Les valeurs négatives ne sont pas autorisées");
                        return false;
                    }
                    if (typeof newValue === 'string') {
                        const cleanedValue = newValue.replace(/\s/g, '').replace(',', '.');
                        change[3] = newValue.trim() === '' || isNaN(cleanedValue) ? '' : cleanedValue;
                    }
                }
            });
            return true;
        }
    };

    // Initialisation
    document.addEventListener('DOMContentLoaded', function() {
        if (container) {
            hot = new Handsontable(container, hotConfig);
            
            nodeManager.buildTree(data);
            updateTotal();
            setupTriangleToggle();
            
            // Raccourcis clavier
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Tab' && !e.ctrlKey && !e.altKey) {
                    e.preventDefault();
                    e.shiftKey ? desindente() : indente();
                }
                if (e.ctrlKey && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) {
                    e.preventDefault();
                    e.key === 'ArrowRight' ? indente() : desindente();
                }
            });
        }

        // Masquer les messages automatiquement
        setTimeout(() => {
            document.querySelectorAll('.alert-auto-dismiss').forEach(alert => {
                alert.style.display = 'none';
            });
        }, 3000);
    });
    function convertToTitle() {
        const selected = getSafeSelection();
        if (!selected) {
            alert("Veuillez sélectionner une ligne");
            return;
        }
        
        const rowIndex = selected.startRow;
        const rowData = hot.getSourceDataAtRow(rowIndex);
    
        if (!rowData) return;
        
        hot.setDataAtRowProp(rowIndex, 'est_titre', true);
        rowData.quantite = 0;
        rowData.prix_unitaire = 0;
        rowData.unite = '';
        rowData.montant = 0;
        
        hot.render();
        updateTotal();        
    }

    function convertToNormal() {
        const selected = getSafeSelection();
        if (!selected) {
            alert("Veuillez sélectionner une ligne");
            return;
        }
        
        const rowIndex = selected.startRow;
        const rowData = hot.getSourceDataAtRow(rowIndex);
        
        if (rowData && rowData.est_titre) {
            hot.setDataAtRowProp(rowIndex, 'est_titre', false);
        }
    }
    function saveData() {
        const saveBtn = document.getElementById('save-btn');
        afficherLoading(saveBtn, "Enregistrement...");
        const sourceData = hot.getSourceData();
        
        const finalData = sourceData
            .filter(row => row && row.designation && row.designation.trim() !== '')
            .map(row => ({
                id: row.id,
                numero: row.numero,
                designation: row.designation,
                unite: row.unite,
                quantite: row.quantite || 0,
                prix_unitaire: row.prix_unitaire || 0,
                niveau: row.niveau || 0,
                est_titre: row.est_titre || false,
                parent_id: row.parent_id || null
            }));
        
        fetch("{% url 'projets:sauvegarder_lignes_bordereau' lot.id %}", {
            method: "POST",
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': '{{ csrf_token }}'
            },
            body: JSON.stringify(finalData)
        })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => { 
                    throw new Error(text || response.statusText) 
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'ok') {
                alert("Données enregistrées avec succès !");
            } else {
                throw new Error(data.message);
            }
        })
        .catch(error => {
            console.error('Erreur:', error);
            alert("Erreur d'enregistrement : " + error.message);
        });
    }

    function exportExcel() {
        const exportData = hot.getData().filter(row => row && row[1] !== null && row[1] !== '');
        const wb = XLSX.utils.book_new();
        const wsData = [
            ['N°', 'Désignation', 'Unité', 'Quantité', 'PU (DH)', 'Montant (DH)'],
            ...exportData
        ];
        const ws = XLSX.utils.aoa_to_sheet(wsData);
        XLSX.utils.book_append_sheet(wb, ws, "Bordereau");
        XLSX.writeFile(wb, "bordereau_{{ lot.nom|slugify }}.xlsx");
    }

    function exportPDF() {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        const exportData = hot.getData().filter(row => row && row[1] !== null && row[1] !== '');
        const headers = ['N°', 'Désignation', 'Unité', 'Quantité', 'PU (DH)', 'Montant (DH)'];
        const body = exportData.map(row => row.map(cell => {
            if(typeof cell === 'number') {
                return cell.toLocaleString('fr-FR', { minimumFractionDigits: 2 });
            }
            return cell || '';
        }));
        doc.text("Bordereau des prix unitaires - {{ lot.nom }}", 14, 15);
        doc.autoTable({
            head: [headers],
            body: body,
            startY: 20,
            styles: { fontSize: 8 },
            headStyles: { fillColor: [0, 123, 255] }
        });
        doc.save("bordereau_{{ lot.nom|slugify }}.pdf");
    }
function indenteAvecEnfants() {
        const selection = getSafeSelection();
        
        if (!selection || selection.length === 0){
            alert("❌ Veuillez sélectionner une ligne");
            return;
        }
        
        const rowIndex = selection.startRow;
        const rowData = hot.getSourceDataAtRow(rowIndex);
        
        if (!rowData) return;
        
        const currentNiveau = rowData.niveau || 0;
        const newNiveau = Math.min(currentNiveau + 1, 5);
        
        if (currentNiveau === newNiveau) {
            alert("⚠️ Niveau maximum atteint");
            return;
        }
        
        // Indenter la ligne sélectionnée et tous ses enfants
        const lignesAIndenter = getLignesEnfants(rowIndex);
        lignesAIndenter.unshift(rowIndex); // Ajouter la ligne parente
        
        // Appliquer l'indentation à toutes les lignes concernées
        lignesAIndenter.forEach(ligneIndex => {
            const ligneData = hot.getSourceDataAtRow(ligneIndex);
            if (ligneData) {
                const nouveauNiveauLigne = (ligneData.niveau || 0) + 1;
                hot.setDataAtRowProp(ligneIndex, 'niveau', nouveauNiveauLigne);
            }
        });
        
        setTimeout(() => {
            hot.render();
        }, 50);
    }
    
    // Fonction pour désindenter avec gestion des enfants
    function desindenteAvecEnfants() {
       const selection = getSafeSelection();
        
        if (!selection || selection.length === 0) {
            alert("❌ Veuillez sélectionner une ligne");
            return;
        }
        
        const rowIndex = selection.startRow;
        const rowData = hot.getSourceDataAtRow(rowIndex);
        
        if (!rowData) return;
        
        const currentNiveau = rowData.niveau || 0;
        const newNiveau = Math.max(currentNiveau - 1, 0);
        
        if (currentNiveau === newNiveau) {
            alert("⚠️ Niveau minimum atteint");
            return;
        }
        
        // Désindenter la ligne sélectionnée et tous ses enfants
        const lignesADesindenter = getLignesEnfants(rowIndex);
        lignesADesindenter.unshift(rowIndex);
                
        // Appliquer la désindentation à toutes les lignes concernées
        lignesADesindenter.forEach(ligneIndex => {
            const ligneData = hot.getSourceDataAtRow(ligneIndex);
            if (ligneData) {
                const nouveauNiveauLigne = Math.max((ligneData.niveau || 0) - 1, 0);
                hot.setDataAtRowProp(ligneIndex, 'niveau', nouveauNiveauLigne);
            }
        });
        
        setTimeout(() => {
            hot.render();
        }, 50);
    }

    // Fonction utilitaire pour récupérer tous les enfants d'une ligne
    function getLignesEnfants(parentRow) {
        const enfants = [];
        const parentData = hot.getSourceDataAtRow(parentRow);
        if (!parentData) return enfants;
        
        const parentNiveau = parentData.niveau || 0;
        
        // Parcourir les lignes suivantes jusqu'au prochain même niveau
        for (let i = parentRow + 1; i < hot.countRows(); i++) {
            const ligneData = hot.getSourceDataAtRow(i);
            if (!ligneData) break;
            
            const ligneNiveau = ligneData.niveau || 0;
            
            // Si on retrouve le même niveau ou inférieur, on arrête
            if (ligneNiveau <= parentNiveau) break;
            
            // Ajouter les enfants directs et indirects
            enfants.push(i);
        }
        
        return enfants;
    }
    