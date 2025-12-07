/**
 * Gestionnaire de bordereau de prix - Version simplifiée
 * Gestion optimisée du collage externe (Excel)
 */

// ============================================================================
// CLASSES DE BASE OPTIMISÉES
// ============================================================================

class Line {
    constructor(id = null, numero = "", designation = "", unite = "", 
                quantite = 0, pu = 0, parent = null, expanded = true) {
        this.id = id;
        this.children = [];
        this.numero = numero;
        this.designation = designation;
        this.unite = unite;
        this.quantite = quantite;
        this.prix_unitaire = pu;
        this.parent = parent;
        this.expanded = expanded;
        
        // Cache pour optimisation
        this._cachedAmount = null;
        this._cachedLevel = null;
    }

    get level() {
        // if (this._cachedLevel !== null) return this._cachedLevel;
        
        let level = 0;
        let current = this.parent;
        while (current) {
            level++;
            current = current.parent;
        }
        
        // this._cachedLevel = level;
        return level;
    }

    get hasChildren() {
        return this.children.length > 0;
    }

    get amount() {
        if (this._cachedAmount !== null) return this._cachedAmount;
        
        if (this.hasChildren) {
            const total = this.children.reduce((sum, child) => sum + child.amount, 0);
            this._cachedAmount = total;
            return total;
        }
        
        const total = this.quantite * this.prix_unitaire;
        this._cachedAmount = total;
        return total;
    }

    invalidateCache() {
        this._cachedAmount = null;
        this._cachedLevel = null;
        
        // Invalider aussi les parents
        if (this.parent) {
            this.parent.invalidateCache();
        }
    }
    getChildIndex(child) {
        return this.children.indexOf(child);
    }
    getFirstChild() {
        return this.children[0] || null;
    }

    getLastChild() {
        return this.children[this.children.length - 1] || null;
    }

    indent() {
        const parent = this.parent;
        if (!parent) return false;
        
        const currentIndex = parent.getChildIndex(this);
        if (currentIndex === 0) return false;
        
        const previousSibling = parent.children[currentIndex - 1];
        parent.removeChild(this);
        previousSibling.addChild(this);
        
        // this.invalidateParentCaches();
        return true;
    }

    desindent() {
        const parent = this.parent;
        if (!parent) return false;
        
        // Si cette ligne n'est pas le dernier enfant de son parent, elle ne peut pas se déindenter
        if (parent.getLastChild() !== this) return false;
        
        const grandParent = parent.parent;
        if (!grandParent) return false;
        
        const parentIndex = grandParent.getChildIndex(parent);
        parent.removeChild(this);
        grandParent.insertChildAt(this, parentIndex + 1);
        
        // this.invalidateParentCaches();
        return true;
    }

    addChild(child) {
        child.parent = this;
        this.children.push(child);
        this.invalidateCache();
    }

    removeChild(child) {
        const index = this.children.indexOf(child);
        if (index !== -1) {
            this.children.splice(index, 1);
            child.parent = null;
            this.invalidateCache();
            return true;
        }
        return false;
    }

    toggleExpanded() {
        this.expanded = !this.expanded;
    }

    get descendantIds() {
        const ids = [];
        const traverse = (line) => {
            line.children.forEach(child => {
                ids.push(child.id);
                traverse(child);
            });
        };
        traverse(this);
        return ids;
    }
}

class LineManager {
    constructor(lotNom = "Bordereau", data = []) {
        this.root = new Line(null, "Root", lotNom);
        this.lines = new Map(); // Map<id, Line>
        this.flatIndex = new Map(); // Map<id, index>
        this.cachedFlatList = null;
        if (data && data.length > 0) {
            this.buildTree(data);
        }
    }

    // ============================================================================
    // GESTION DES DONNÉES EXTERNES (COLLAGE EXCEL)
    // ============================================================================

    /**
     * Traite les données collées depuis Excel et les convertit en lignes
     * @param {Array} excelData - Données Excel [[col1, col2, col3, col4, col5], ...]
     * @param {number} startRow - Ligne de départ dans le tableau
     * @returns {Array} - Indices des nouvelles lignes créées
     */
    processExcelPaste(excelData, startRow = 0) {
        // console.log(`Processing ${excelData.length} rows from Excel paste`);
        
        const newLineIndices = [];
        
        excelData.forEach((excelRow, index) => {
            const targetIndex = startRow + index;
            const lineData = this.parseExcelRow(excelRow);
            
            // Créer ou mettre à jour la ligne
            const line = this.insertOrUpdateLineAt(targetIndex, lineData);
            newLineIndices.push(targetIndex);
            
            // console.log(`Processed row ${index}: "${lineData.designation}"`);
        });
        
        // Invalider le cache
        this.invalidateCache();
        
        return newLineIndices;
    }

    /**
     * Parse une ligne Excel selon le format: [N°, Désignation, Unité, PU, Quantité]
     * @param {Array} excelRow - Ligne Excel
     * @returns {Object} - Données structurées pour Line
     */
    parseExcelRow(excelRow) {
        // Format attendu: ['1', 'Installation du chantier ', 'f', '200 000,00 ', '1,00']
        
        return {
            numero: this.cleanString(excelRow[0] || ''),
            designation: this.cleanString(excelRow[1] || 'Nouvelle ligne'),
            unite: this.cleanString(excelRow[2] || ''),
            prix_unitaire: this.parseFrenchNumber(excelRow[3] || '0'),
            quantite: this.parseFrenchNumber(excelRow[4] || '0'),
            expanded: true
        };
    }

    cleanString(value) {
        if (value === null || value === undefined) return '';
        return String(value).trim();
    }

    parseFrenchNumber(value) {
        if (!value) return 0;
        
        const str = String(value).trim()
            .replace(/\s/g, '')      // Supprimer les espaces
            .replace(',', '.')       // Remplacer virgule par point
            .replace(/[^\d.-]/g, ''); // Garder seulement chiffres, point, moins
        
        const num = parseFloat(str);
        return isNaN(num) ? 0 : num;
    }

    /**
     * Insère ou met à jour une ligne à un index spécifique
     */
    insertOrUpdateLineAt(index, lineData) {
        const existingLine = this.getLineByFlatIndex(index);
        
        if (existingLine) {
            // Mettre à jour la ligne existante
            existingLine.numero = lineData.numero;
            existingLine.designation = lineData.designation;
            existingLine.unite = lineData.unite;
            existingLine.quantite = lineData.quantite;
            existingLine.prix_unitaire = lineData.prix_unitaire;
            existingLine.expanded = lineData.expanded;
            existingLine.invalidateCache();
            return existingLine;
        } else {
            // Créer une nouvelle ligne
            const id = `paste_${Date.now()}_${index}_${Math.random().toString(36).substr(2, 9)}`;
            const newLine = new Line(
                id,
                lineData.numero,
                lineData.designation,
                lineData.unite,
                lineData.quantite,
                lineData.prix_unitaire,
                this.root, // Parent racine par défaut
                lineData.expanded
            );
            
            // Insérer à la bonne position
            return this.insertLineAtFlatIndex(newLine, index);
        }
    }

    /**
     * Insère une ligne à un index spécifique dans la liste plate
     */
    insertLineAtFlatIndex(line, targetIndex) {
        const flatList = this.getFlatList();
        
        // Déterminer où insérer
        if (targetIndex >= flatList.length) {
            // Ajouter à la fin
            this.root.addChild(line);
        } else {
            // Insérer avant la ligne à l'index cible
            const targetLine = flatList[targetIndex];
            if (targetLine && targetLine.parent) {
                const parent = targetLine.parent;
                const siblingIndex = parent.children.indexOf(targetLine);
                parent.children.splice(siblingIndex, 0, line);
                line.parent = parent;
            } else {
                this.root.addChild(line);
            }
        }
        
        // Ajouter à la map
        this.lines.set(line.id, line);
        
        // Invalider les caches
        this.invalidateCache();
        
        return line;
    }

    // ============================================================================
    // GESTION DE LA STRUCTURE HIÉRARCHIQUE
    // ============================================================================
    buildTree(data) {
        this.lines.clear();
        this.cacheValid = false;
        this.invalidateCache();
        // Étape 1: Créer tous les nodes
        const nodeMap = new Map();
        
        data.forEach(row => {
            if (!row || row.id === null || row.id === undefined) return;
            
            let line = new Line(
                row.id, 
                row.numero || "",
                row.designation || "Nouvelle ligne", 
                row.unite || "", 
                parseFloat(row.quantite) || 0, 
                parseFloat(row.prix_unitaire) || 0,
                null,
                row._expanded !== undefined ? row._expanded : true
            );
            
            nodeMap.set(row.id, line);
            this.lines.set(row.id, line);
        });

        // Étape 2: Construire la hiérarchie
        data.forEach(row => {
            if (!row || !nodeMap.has(row.id)) return;
            
            const line = nodeMap.get(row.id);
            
            if (row.parent_id && nodeMap.has(row.parent_id)) {
                nodeMap.get(row.parent_id).addChild(line);
            } else {
                this.root.addChild(line);
            }
        });
        
        // Mettre à jour l'index plat
        this.updateFlatIndex();
    }
    getFlatList() {
        if (this.cachedFlatList) return this.cachedFlatList;
        
        const result = [];
        const traverse = (line) => {
            result.push(line);
            
            if (line.hasChildren) {
                line.children.forEach(child => traverse(child));
            }
        };
        
        this.root.children.forEach(traverse);
        this.cachedFlatList = result;
        
        // Mettre à jour l'index plat
        this.updateFlatIndex();
        
        return result;
    }

    updateFlatIndex() {
        this.flatIndex.clear();
        const flatList = this.getFlatList();
        
        flatList.forEach((line, index) => {
            if (line.id) {
                this.flatIndex.set(line.id, index);
            }
        });
    }

    getLineByFlatIndex(index) {
        const flatList = this.getFlatList();
        return index >= 0 && index < flatList.length ? flatList[index] : null;
    }
    removeLineByIndex(rowIndex, amount = 1) {
        const flatList = this.getFlatList();
        try {
            for (let i = amount-1; i >= 0; i--) {
                const line = flatList[rowIndex + i];

                if (line && line.parent) {
                    line.parent.removeChild(line);
                    this.flatIndex.delete(line.id);
                }
                // else {
                //     console.log('Line not found at index ', rowIndex + i);
                // }   
            }
            this.invalidateCache();
            return true;
        } catch (e) {
            console.error(e);
            return false;
        }
           

    }

    get nbLines() {
        return this.getFlatList().length;
    }
    getLineIndexById(id) {
        return this.flatIndex.get(id) || -1;
    }

    invalidateCache() {
        this.cachedFlatList = null;
        this.flatIndex.clear();
    }

    get totalAmount() {
        return this.root.amount;
    }

    /**
     * Convertit toutes les lignes en format tableau pour Handsontable
     */
    toTableData() {
        return this.getFlatList().map(line => ({
            id: line.id,
            _expanded: line.expanded,
            niveau: line.level,
            est_titre: line.hasChildren,
            numero: line.numero,
            designation: line.designation,
            unite: line.unite,
            quantite: line.quantite,
            prix_unitaire: line.prix_unitaire,
            montant: line.amount
        }));
    }

    // ============================================================================
    // INDENTATION/DÉSINDENTATION
    // ============================================================================

    indentLine(start, nbRows = 1) {

        const cachedFlatList = this.getFlatList();
        const nbLines = cachedFlatList.length;
        if (start < 0 || start + nbRows > nbLines) return false;
        
        // obtenir les lignes à indenter
        const lines = cachedFlatList.slice(start, start + nbRows);
        
        // boucler sur les lignes et les indenter et calculer le nombre de fois que les lignes sont indented
        let maxIndentNumber = 0;
        lines.forEach(line => {
            if (line.indent()) maxIndentNumber++;
        });
        
        // mettre à jour la liste plate si au moins une ligne a été indented
        if (maxIndentNumber > 0) {
            this.invalidateCache();
            return maxIndentNumber;
        }
        
        return 0;
    }

 
    desindentLine(start, nbRows = 1) {
        console.log('desindentLine', start, nbRows);
        const cachedFlatList = this.getFlatList();
        const nbLines = cachedFlatList.length;
        if (start < 0 || start + nbRows > nbLines) return false;
        
        // obtenir les lignes à désindenter
        const lines = cachedFlatList.slice(start, start + nbRows);
        
        let maxDesindentNumber = 0;
        lines.forEach(line => {
            if (line.desindent()) maxDesindentNumber++;
        });
        
        // mettre à jour la liste plate si au moins une ligne a été désindented
        if (maxDesindentNumber > 0) {
            this.invalidateCache();
            return maxDesindentNumber;
        }
        
        return 0;
    }

    // ============================================================================
    // EXPANSION/COLLAPSE
    // ============================================================================

    toggleExpansion(index) {
        const line = this.getLineByFlatIndex(index);
        if (line && line.hasChildren) {
            line.toggleExpanded();
            this.invalidateCache();
            return true;
        }
        return false;
    }

    getHiddenRows() {
        const hiddenRows = [];
        const flatList = this.getFlatList();
        
        flatList.forEach((line, index) => {
            if (line.hasChildren && !line.expanded) {
                // Cacher tous les descendants de cette ligne
                const descendantIndices = this.getDescendantIndices(line.id);
                hiddenRows.push(...descendantIndices);
            }
        });
        
        // Éliminer les doublons
        return [...new Set(hiddenRows)];
    }

    getDescendantIndices(parentId) {
        const parentLine = this.lines.get(parentId);
        if (!parentLine) return [];
        
        const indices = [];
        const traverse = (line) => {
            line.children.forEach(child => {
                const childIndex = this.getLineIndexById(child.id);
                if (childIndex !== -1) {
                    indices.push(childIndex);
                    traverse(child);
                }
            });
        };
        
        traverse(parentLine);
        return indices;
    }
}

// ============================================================================
// GESTIONNAIRE PRINCIPAL
// ============================================================================

class BordereauManager {
    constructor(options = {}) {
        this.containerId = options.containerId || 'hot';
        this.lotNom = options.lotNom || 'Bordereau';
        this.csrfToken = options.csrfToken || '';
        this.saveUrl = options.saveUrl || '';
        
        // Initialisation
        this.hot = null;
        this.lineManager = null;
        this.initialize();
    }

    initialize() {
        // Initialiser le LineManager
        this.lineManager = new LineManager(this.lotNom);
        
        // Charger les données initiales si présentes
        if (window.bordereauData && Array.isArray(window.bordereauData)) {
            this.lineManager = new LineManager(this.lotNom, window.bordereauData);
        }
        
        // Initialiser Handsontable
        this.initHandsontable();
        
        // Configurer les raccourcis clavier
        this.setupKeyboardShortcuts();
    }

    initHandsontable() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`Container #${this.containerId} non trouvé`);
            return;
        }

        this.hot = new Handsontable(container, this.getHotConfig());
        
        // Initialiser l'affichage hiérarchique
        setTimeout(() => this.updateHiddenRows(), 100);
    }

    getHotConfig() {
        return {
            data: this.lineManager.toTableData(),
            columns: [
                {data: '_expanded', type: 'checkbox', title: 'e', width: 10},
                {data: 'niveau', type: 'text', title: 'N', width: 20, 
                 renderer: this.hierarchyRenderer.bind(this)},
                {data: 'est_titre', type: 'checkbox', title: 'T', width: 20, 
                 hidden: true, renderer: this.hierarchyRenderer.bind(this)},
                {data: 'numero', type: 'text', title: 'N°', width: 50, 
                 renderer: this.hierarchyRenderer.bind(this)},
                {data: 'designation', type: 'text', title: 'Désignation', 
                 renderer: this.hierarchyRenderer.bind(this)},
                {data: 'unite', type: 'text', title: 'Unité', width: 100, 
                 renderer: this.hierarchyRenderer.bind(this)},
                {data: 'quantite', type: 'numeric', numericFormat: { pattern: '0,0.000' }, 
                 title: 'Quantité', width: 120, renderer: this.numericRenderer.bind(this)},
                {data: 'prix_unitaire', type: 'numeric', numericFormat: { pattern: '0,0.00' }, 
                 title: 'PU (DH)', width: 120, renderer: this.numericRenderer.bind(this)},
                {data: 'montant', type: 'numeric', readOnly: true, 
                 numericFormat: { pattern: '0,0.00' }, title: 'Montant (DH)', width: 140, 
                 renderer: this.montantRenderer.bind(this)},
            ],
            rowHeaders: false,
            colHeaders: true,
            licenseKey: 'non-commercial-and-evaluation',
            contextMenu: ['row_above', 'row_below', 'remove_row'],
            hiddenColumns: {columns: [0, 1, 2], indicators: false},
            hiddenRows: {rows: [], indicators: false},
            minSpareRows: 5, // Plus de lignes vides pour faciliter le collage
            height: 'auto',
            width: 'auto',
            rowHeights: 40,
            manualColumnResize: true,
            outsideClickDeselects: false,
            afterRemoveRow: this.handleAfterRemoveRow.bind(this),
            // Gestion des changements
            // afterChange: this.handleAfterChange.bind(this),
            // beforeChange: this.handleBeforeChange.bind(this),
            // GESTION DU COLLAGE (SIMPLIFIÉ)
            beforePaste: (data, coords) => this.handlePaste(data, coords),
            
            // GESTION DES CHANGEMENTS
            
            beforeChange: (changes, source) => this.handleBeforeChange(changes, source),
            afterChange: (changes, source) => {
                if (!changes || source === 'loadData') return;
                
                changes.forEach(change => {
                    const [row, prop, oldValue, newValue] = change;
                    this.handleCellChange(row, prop, newValue);
                });
            },
            
            // GESTION DU CLIC SUR LES TRIANGLES
            afterOnCellMouseDown: (event, coords, TD) => {
                if (event.target.classList.contains('toggle-triangle')) {
                    event.preventDefault();
                    event.stopPropagation();
                    
                    const row = parseInt(event.target.getAttribute('data-row'));
                    this.toggleExpansion(row);
                    return false;
                }
            }
        };
    }

    // ============================================================================
    // GESTION DU COLLAGE (VERSION SIMPLIFIÉE)
    // ============================================================================

    handlePaste(data, coords) {
        // console.log('Paste detected:', data);
        
        if (!data || !Array.isArray(data) || data.length === 0) {
            return true; // Laisser Handsontable gérer
        }
        
        // Déterminer la position de collage
        let startRow = 0;
        if (coords && Array.isArray(coords) && coords.length > 0) {
            startRow = coords[0].start?.row || 0;
        }
        
        console.log(`Pasting ${data.length} rows at position ${startRow}`);
        
        // Traiter les données Excel
        this.processPastedData(data, startRow);
        
        return false; // Bloquer le traitement natif
    }

    processPastedData(excelData, startRow) {
        // 1. Traiter les données dans le LineManager
        const newIndices = this.lineManager.processExcelPaste(excelData, startRow);
        
        // 2. Mettre à jour le tableau en une seule opération
        this.refreshTable();
        
        console.log(`Successfully pasted ${newIndices.length} rows`);
    }

    refreshTable() {
        if (!this.hot) return;
        
        // 1. Mettre à jour les données
        this.hot.updateSettings({
            data: this.lineManager.toTableData()
        });
        
        // 2. Mettre à jour les lignes cachées
        this.updateHiddenRows();
        
        // 3. Mettre à jour le total
        this.updateTotal();
        
        // 4. Forcer un rendu
        this.hot.render();
    }

    // ============================================================================
    // GESTION DES CHANGEMENTS DE CELLULES
    // ============================================================================

    handleCellChange(row, property, value) {
        const line = this.lineManager.getLineByFlatIndex(row);
        if (!line) return;
        
        switch(property) {
            case 'numero':
                line.numero = value;
                break;
            case 'designation':
                line.designation = value;
                break;
            case 'unite':
                line.unite = value;
                break;
            case 'quantite':
                line.quantite = parseFloat(value) || 0;
                line.invalidateCache();
                break;
            case 'prix_unitaire':
                line.prix_unitaire = parseFloat(value) || 0;
                line.invalidateCache();
                break;
            case '_expanded':
                line.expanded = value;
                this.lineManager.invalidateCache();
                this.updateHiddenRows();
                break;
        }
        
        // Mettre à jour le montant affiché
        if (property === 'quantite' || property === 'prix_unitaire') {
            this.hot.setDataAtRowProp(row, 'montant', line.amount);
        }
    }

    handleAfterRemoveRow(index, amount, source) {
        // console.log(`Removing line at index ${index} (${source}) (amount: ${amount})`);
        this.lineManager.removeLineByIndex(index, amount);
        this.updateTotal();
        this.dataChanged = true;
    }

    handleAfterChange(changes, source) {
        if (!changes || this.updating) return;
        
        changes.forEach(change => {
            const [row, prop, oldValue, newValue] = change;
            const line = this.lineManager.getLineByIndex(row);

            if (!line) return;
            
            switch(prop) {
                case 'numero': 
                    line.numero = newValue; 
                    this.dataChanged = true;
                    break;
                case 'designation': 
                    line.designation = newValue; 
                    this.dataChanged = true;
                    break;
                case 'unite': 
                    line.unite = newValue; 
                    this.dataChanged = true;
                    break;
                case 'quantite': 
                    line.quantite = parseFloat(newValue) || 0; 
                    this.dataChanged = true;
                    this.updateTotal();
                    this.hot.setDataAtRowProp(row, 'montant', line.amount(), 'recalc');
                    break;
                case 'prix_unitaire': 
                    line.prix_unitaire = parseFloat(newValue) || 0; 
                    this.dataChanged = true;
                    this.updateTotal();
                    this.hot.setDataAtRowProp(row, 'montant', line.amount(), 'recalc');
                    break;
                case '_expanded': 
                    line._expanded = newValue;
                    // Mettre à jour l'affichage hiérarchique
                    setTimeout(() => this.toggleChildrenVisibility(row), 50);
                    break;
            }
        });
        
        // Si le changement vient d'un paste, traiter spécialement
        if (source === 'paste' && this.pendingPaste) {
            this.finalizePaste();
        }
    }

    handleBeforeChange(changes, source) {
        if (!changes) return true;
        
        changes.forEach(change => {
            const [row, prop, oldValue, newValue] = change;
            
            if (prop === 'quantite' || prop === 'prix_unitaire') {
                if (newValue !== null && parseFloat(newValue) < 0) {
                    alert("Les valeurs négatives ne sont pas autorisées");
                    return false;
                }
                
                if (newValue !== null && typeof newValue === 'string') {
                    const cleanedValue = newValue.replace(/\s/g, '').replace(',', '.');
                    if (newValue.trim() === '' || isNaN(cleanedValue)) {
                        change[3] = '';
                    } else {
                        change[3] = cleanedValue;
                    }
                }
            }
        });
        
        return true;
    }
    // ============================================================================
    // GESTION DE L'EXPANSION/HIERARCHIE
    // ============================================================================

    toggleExpansion(row) {
        if (this.lineManager.toggleExpansion(row)) {
            this.refreshTable();
        }
    }

    updateHiddenRows() {
        if (!this.hot) return;
        
        const hiddenRows = this.lineManager.getHiddenRows();
        this.hot.updateSettings({
            hiddenRows: {
                rows: hiddenRows,
                indicators: false
            }
        });
    }

    // ============================================================================
    // RENDERERS
    // ============================================================================

    hierarchyRenderer(instance, td, row, col, prop, value, cellProperties) {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        
        const line = this.lineManager.getLineByFlatIndex(row);
        if (!line) return;
        
        const niveau = line.level;
        const isTitle = line.hasChildren;

        if (isTitle) {
            td.className = (td.className || '') + ' title-row';
        }
        
        if (prop === 'designation') {
            const indent = niveau * 15;
            td.style.paddingLeft = `${indent}px`;
            td.style.verticalAlign = 'middle';
            
            if (isTitle) {
                const triangleClass = line.expanded ? 'triangle-expanded' : 'triangle-collapsed';
                td.innerHTML = `<span class="toggle-triangle ${triangleClass}" data-row="${row}"></span>${value || ''}`;
            } else {
                td.textContent = value || '';
                td.style.paddingLeft = `${indent + 15}px`;
            }
        }
    }

    numericRenderer(instance, td, row, col, prop, value, cellProperties) {
        Handsontable.renderers.NumericRenderer.apply(this, arguments);
        
        const line = this.lineManager.getLineByFlatIndex(row);
        if (!line) return;
        
        if (line.hasChildren) {
            td.textContent = '';
            td.className = (td.className || '') + ' title-row';
        } else if (value === 0 || value === '' || value === null) {
            td.textContent = '';
        }
    }

    montantRenderer(instance, td, row, col, prop, value, cellProperties) {
        Handsontable.renderers.NumericRenderer.apply(this, arguments);
        
        const line = this.lineManager.getLineByFlatIndex(row);
        if (!line) return;
        
        if (line.hasChildren) {
            td.textContent = line.amount === 0 ? '' : this.formatNumber(line.amount);
            td.className = 'htRight title-row';
        } else {
            td.textContent = line.amount === 0 ? '' : this.formatNumber(line.amount);
            td.className = 'htRight montant-cell';
        }
    }

    // ============================================================================
    // FONCTIONS UTILITAIRES
    // ============================================================================

    getSafeSelection() {
        if (!this.hot) return null;
        
        const selected = this.hot.getSelected();
        if (!selected || !Array.isArray(selected) || selected.length === 0) {
            return null;
        }
        
        const [startRow, startCol, endRow, endCol] = selected[0];
        
        return {
            startRow: Math.min(startRow, endRow),
            startCol: Math.min(startCol, endCol),
            endRow: Math.max(startRow, endRow),
            endCol: Math.max(startCol, endCol),
            isSingleCell: (startRow === endRow && startCol === endCol),
            nbRows: endRow - startRow + 1
        };
    }

    formatNumber(value, decimals = 2) {
        return value.toLocaleString('en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    updateTotal() {
        const total = this.lineManager.totalAmount;
        const totalElement = document.getElementById('total-lot');
        
        if (totalElement) {
            totalElement.textContent = `${this.formatNumber(total)} MAD`;
        }
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Tab pour indenter/désindenter
            if (e.key === 'Tab' && !e.ctrlKey && !e.altKey && this.hot) {
                e.preventDefault();
                const selected = this.hot.getSelected();
                if (!selected || selected.length === 0) return;
                
                const startRow = selected[0][0];
                
                if (e.shiftKey) {
                    // Désindenter
                    if (this.lineManager.desindentLine(startRow)) {
                        this.refreshTable();
                    }
                } else {
                    // Indenter
                    if (this.lineManager.indentLine(startRow)) {
                        this.refreshTable();
                    }
                }
            }
        });
    }

    // ============================================================================
    // FONCTIONS PUBLIQUES POUR LES BOUTONS
    // ============================================================================

    insertChildLine() {
        const selected = this.hot?.getSelected();
        if (!selected || selected.length === 0) {
            alert("Veuillez sélectionner une ligne");
            return;
        }
        
        const startRow = selected[0][0];
        const newLine = this.lineManager.insertOrUpdateLineAt(startRow + 1, {
            numero: '',
            designation: 'Nouvelle ligne',
            unite: '',
            quantite: 1,
            prix_unitaire: 0,
            expanded: true
        });
        
        this.refreshTable();
    }

    indente() {
        const selected = this.getSafeSelection();
        if (!selected || selected.nbRows === 0) {
            alert("Veuillez sélectionner une ligne");
            return;
        }
        
        const startRow = selected.startRow;
        const result = this.lineManager.indentLine(startRow, selected.nbRows);
        if (result > 0) {
            console.log('indentation successful. Inserted ' + result + ' lines.');
            this.refreshTable();
        }
        else {
            console.log('indentation failed');
        }
    }

    desindente() {
        const selected = this.getSafeSelection();
        if (!selected || selected.nbRows === 0) {
            alert("Veuillez sélectionner une ligne");
            return;
        }
        
        const startRow = selected.startRow;
        const result = this.lineManager.desindentLine(startRow, selected.nbRows);
        if (result > 0) {
            console.log('desindentation successful. Desindented ' + result + ' lines.');
            this.refreshTable();
        }
        else {
            console.log('desindentation failed');
        }
        
    }

    saveData() {
        const saveBtn = document.getElementById('save-btn');
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enregistrement...';
        }
        
        const flatList = this.lineManager.getFlatList();
        console.log(flatList);
        const finalData = flatList.map(line => ({
            id: line.id,
            numero: line.numero,
            designation: line.designation,
            unite: line.unite,
            quantite: line.quantite,
            prix_unitaire: line.prix_unitaire,
            niveau: line.level,
            est_titre: line.hasChildren,
            parent_id: line.parent ? line.parent.id : null
        }));

        fetch(this.saveUrl, {
            method: "POST",
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify(finalData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'ok') {
                saveBtn.innerHTML = '<i class="fas fa-save"></i>';
                alert(data.message);
                // window.location.reload();
                // Si le backend a créé de nouveaux IDs, les mettre à jour dans lineManager
                if (data.lignes) {
                    console.log(data.lignes);
                    Object.entries(data.lignes).forEach(([oldId, newId]) =>{
                        const line = this.lineManager.lines.get(oldId);
                        if (line) {
                            // Mettre à jour l'ID
                            line.id = newId;
                            
                            // Mettre à jour dans la Map
                            this.lineManager.lines.delete(oldId);
                            this.lineManager.lines.set(newId, line);
                            
                            console.log(`ID mis à jour: ${oldId} -> ${newId}`);
                        }
                    this.lineManager.invalidateCache()
                    });
                }
            } else {
                throw new Error(data.message);
            }
        })
        .catch(error => {
            console.error('Erreur:', error);
            alert("Erreur d'enregistrement : " + error.message);
        })
        .finally(() => {
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fas fa-save"></i>';
            }
        });
    }

    exportExcel() {
        const exportData = this.hot.getData().filter(row => row && row[1] !== null && row[1] !== '');
        const wb = XLSX.utils.book_new();
        const wsData = [
            ['N°', 'Désignation', 'Unité', 'Quantité', 'PU (DH)', 'Montant (DH)'],
            ...exportData.map(row => [row[3], row[4], row[5], row[6], row[7], row[8]])
        ];
        const ws = XLSX.utils.aoa_to_sheet(wsData);
        XLSX.utils.book_append_sheet(wb, ws, "Bordereau");
        XLSX.writeFile(wb, `bordereau_${this.lotNom.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.xlsx`);
    }

    exportPDF() {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        const exportData = this.hot.getData().filter(row => row && row[1] !== null && row[1] !== '');
        const headers = ['N°', 'Désignation', 'Unité', 'Quantité', 'PU (DH)', 'Montant (DH)'];
        const body = exportData.map(row => [row[3], row[4], row[5], row[6], row[7], row[8]]);
        
        doc.text(`Bordereau des prix unitaires - ${this.lotNom}`, 14, 15);
        doc.autoTable({
            head: [headers],
            body: body,
            startY: 20,
            styles: { fontSize: 8 },
            headStyles: { fillColor: [0, 123, 255] }
        });
        doc.save(`bordereau_${this.lotNom.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.pdf`);
    }
}

// ============================================================================
// EXPORT GLOBAL
// ============================================================================

window.BordereauManager = BordereauManager;

// Fonction d'initialisation
window.initializeBordereau = function(options = {}) {
    window.bordereauManager = new BordereauManager(options);
    return window.bordereauManager;
};

// Fonctions globales pour les boutons
window.saveData = function() { window.bordereauManager?.saveData(); };
window.insertChildLine = function() { window.bordereauManager?.insertChildLine(); };
window.indente = function() { window.bordereauManager?.indente(); };
window.desindente = function() { window.bordereauManager?.desindente(); };
window.exportExcel = function() { window.bordereauManager?.exportExcel(); };
window.exportPDF = function() { window.bordereauManager?.exportPDF(); };

// Auto-initialisation
document.addEventListener('DOMContentLoaded', function() {
    if (window.bordereauData) {
        setTimeout(() => {
            window.initializeBordereau({
                containerId: 'hot',
                lotNom: window.lotNom || 'Bordereau',
                csrfToken: window.csrfToken || '',
                saveUrl: window.saveUrl || ''
            });
        }, 100);
    }
});