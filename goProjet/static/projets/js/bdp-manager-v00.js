/**
 * Gestionnaire de bordereau de prix - Version initiale
 */

// ============================================================================
// CLASSES DE BASE OPTIMISÉES
// ============================================================================

class Line {
    constructor(id = null, numero = "", designation = "", unite = "", 
                quantite = 0, pu = 0, parent = null, expanded = true) {
        this.id = id || this.generateId();
        this.children = [];
        this.numero = numero;
        this.designation = designation;
        this.unite = unite;
        this.quantite = parseFloat(quantite) || 0;
        this.prix_unitaire = parseFloat(pu) || 0;
        this.parent = parent;
        this.expanded = expanded;
        
        // Cache pour optimisation
        this._cachedAmount = null;
        this._cachedLevel = null;
    }

    generateId() {
        return `line_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
    }

    get level() {
        if (this._cachedLevel !== null) return this._cachedLevel;
        
        let level = 0;
        let current = this.parent;
        while (current) {
            level++;
            current = current.parent;
        }
        
        this._cachedLevel = level;
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

        // Le niveau des descendants dépend de ce nœud (ex: après indent/desindent)
        this.invalidateChildrenLevel();

        // Le montant des ancêtres dépend de ce nœud
        if (this.parent) {
            this.parent.invalidateAmountCache();
        }
    }

    invalidateChildrenLevel() {
        this.children.forEach(child => {
            child._cachedLevel = null;
            child.invalidateChildrenLevel();
        });
    }

    invalidateAmountCache() {
        this._cachedAmount = null;
        if (this.parent) {
            this.parent.invalidateAmountCache();
        }
    }

    getChildIndex(child) {
        return this.children.indexOf(child);
    }

    getNextSibling() {
        if (!this.parent) return null;
        const index = this.parent.getChildIndex(this);
        return this.parent.children[index + 1] || null;
    }

    getPreviousSibling() {
        if (!this.parent) return null;
        const index = this.parent.getChildIndex(this);
        return this.parent.children[index - 1] || null;
    }

    getFirstChild() {
        return this.children[0] || null;
    }

    getLastChild() {
        return this.children[this.children.length - 1] || null;
    }

    indent() {
        const previousSibling = this.getPreviousSibling();
        
        // Ne peut pas indenter s'il n'y a pas de frère précédent
        if (!previousSibling) return false;
        
        const parent = this.parent;
        if (!parent) return false;
        
        // Retirer de l'ancien parent
        parent.removeChild(this);
        
        // Ajouter au frère précédent comme enfant
        previousSibling.addChild(this);
        
        return true;
    }

    desindent() {
        const parent = this.parent;
        
        // Doit avoir un parent et ne pas être à la racine
        if (!parent || !parent.parent) return false;
        
        const grandParent = parent.parent;
        const parentIndex = grandParent.getChildIndex(parent);
        
        // Retirer du parent actuel
        parent.removeChild(this);
        
        // Insérer après le parent dans le grand-parent
        grandParent.insertChildAt(this, parentIndex + 1);
        
        return true;
    }

    addChild(child) {
        child.parent = this;
        this.children.push(child);
        this.invalidateCache();
    }

    insertChildAt(child, index) {
        child.parent = this;
        this.children.splice(index, 0, child);
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

    moveChild(child, newIndex) {
        const currentIndex = this.getChildIndex(child);
        if (currentIndex === -1) return false;
        
        // Retirer de l'index actuel
        this.children.splice(currentIndex, 1);
        
        // Insérer à la nouvelle position
        this.children.splice(newIndex, 0, child);
        this.invalidateCache();
        return true;
    }

    moveChildUp(child) {
        const index = this.getChildIndex(child);
        if (index > 0) {
            return this.moveChild(child, index - 1);
        }
        return false;
    }

    moveChildDown(child) {
        const index = this.getChildIndex(child);
        if (index !== -1 && index < this.children.length - 1) {
            return this.moveChild(child, index + 1);
        }
        return false;
    }

    moveUp() {
        if (!this.parent) return false;
        return this.parent.moveChildUp(this);
    }

    moveDown() {
        if (!this.parent) return false;
        return this.parent.moveChildDown(this);
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

    toggleExpanded() {
        if (this.hasChildren) {
            this.expanded = !this.expanded;
            return true;
        }
        return false;
    }
}

class LineManager {
    constructor(lotNom = "Bordereau", data = []) {
        this.root = new Line(null, "Root", lotNom);
        this.lines = new Map(); 
        this.flatIndex = new Map(); 
        this.cacheInvalid = true;
        this.cachedFlatList = null;
        this.emptyLineManager = new EmptyLineManager(this);

        if (data && data.length > 0) {
            this.buildTree(data);
        } else {
            this.ensureEmptyLinesForEditing();
        }

        this.ensureEmptyLinesForEditing();
    }
    /**
     * Ajoute une ligne vide à un endroit spécifique
     */
    addEmptyLineAt(index, parent = this.root) {
        const line = new Line();
        line.designation = "";
        
        if (parent === this.root && index !== undefined) {
            // Insérer à un index spécifique dans la racine
            this.insertLineAtFlatIndex(line, index);
        } else {
            parent.addChild(line);
        }
        
        this.lines.set(line.id, line);
        this.invalidateCache();
        return line;
    }

    /**
     * Ajoute une ligne vide à la fin d'un parent donné.
     *  Si aucun parent n'est spécifié, ajoute à la racine.
     *   */
    addEmptyLine(parent = this.root) {
        const line = new Line();
        parent.addChild(line);
        this.lines.set(line.id, line);
        this.invalidateCache();
        return line;
    }

    /** 
     * Nettoie les lignes vides (appelé avant sauvegarde)
     */
    cleanupEmptyLinesForSave() {
        return this.emptyLineManager.prepareForSave();
    }
    
    /**
     * Garantit qu'il y a toujours des lignes vides pour l'édition
     */
    ensureEmptyLinesForEditing() {
        return this.emptyLineManager.ensureEmptyLines();
    }
    
    /**
     * Vérifie si une ligne est vide
     */
    isEmptyLine(line) {
        return this.emptyLineManager.isEmptyLine(line);
    }

    // ============================================================================
    // CONSTRUCTION DE L'ARBRE
    // ============================================================================

    buildTree(data) {
        this.lines.clear();
        this.cacheInvalid = true;
        
        // Étape 1: Créer tous les nœuds
        const nodeMap = new Map();
        const createdLines = [];
        
        data.forEach(row => {
            if (!row || row.id === undefined) return;
            
            const line = new Line(
                row.id,
                row.numero || "",
                row.designation || "",
                row.unite || "",
                parseFloat(row.quantite) || 0,
                parseFloat(row.prix_unitaire) || 0,
                null,
                row._expanded !== undefined ? row._expanded : true
            );
            
            nodeMap.set(row.id, line);
            this.lines.set(row.id, line);
            createdLines.push({line, parentId: row.parent_id});
        });

        // Étape 2: Construire la hiérarchie
        createdLines.forEach(({line, parentId}) => {
            if (parentId && nodeMap.has(parentId)) {
                nodeMap.get(parentId).addChild(line);
            } else {
                this.root.addChild(line);
            }
        });

        // Vérifier si l'arbre est vide
        if (this.root.children.length === 0) {
            this.addEmptyLine();
        }
        
        this.invalidateCache();
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
        const newLineIndices = [];
        const invalidRows = [];
        let blankRows = 0;
        
        excelData.forEach((excelRow, index) => {
            const targetIndex = startRow + index;
            if (this.isBlankExcelRow(excelRow)) {
                blankRows++;
                return;
            }

            const lineData = this.parseExcelRow(excelRow);
            if (!lineData) {
                invalidRows.push(index + 1);
                return;
            }
            
            // Créer ou mettre à jour la ligne
            this.insertOrUpdateLineAt(targetIndex, lineData);
            newLineIndices.push(targetIndex);
        });
        
        // Invalider le cache
        this.invalidateCache();

        console.info('Collage Excel:', {
            rowsReceived: excelData.length,
            rowsProcessed: newLineIndices.length,
            blankRows,
            invalidRows: invalidRows.length,
        });

        if (invalidRows.length > 0) {
            this.showMessage(
                `Collage refusé pour les lignes Excel invalides : ${invalidRows.join(', ')}. ` +
                'Les colonnes PU et Quantité doivent contenir des nombres positifs.',
                'warning'
            );
        }
        
        return newLineIndices;
    }

    /**
    * Parse une ligne Excel selon le format: [N°, Désignation, Unité, Quantité, PU]
     * @param {Array} excelRow - Ligne Excel
     * @returns {Object} - Données structurées pour Line
     */
    parseExcelRow(excelRow) {
        const quantite = this.parseFrenchNumber(excelRow[3]);
        const prixUnitaire = this.parseFrenchNumber(excelRow[4]);

        if (prixUnitaire === null || quantite === null || prixUnitaire < 0 || quantite < 0) {
            return null;
        }
        
        return {
            numero: this.cleanString(excelRow[0] || ''),
            designation: this.cleanString(excelRow[1] || 'Nouvelle ligne'),
            unite: this.cleanString(excelRow[2] || ''),
            prix_unitaire: prixUnitaire,
            quantite: quantite,
            expanded: true
        };
    }

    cleanString(value) {
        if (value === null || value === undefined) return '';
        return String(value).trim();
    }

    parseFrenchNumber(value) {
        if (value === null || value === undefined || String(value).trim() === '') return 0;
        if (typeof value === 'number') return Number.isFinite(value) ? value : null;

        let str = String(value).trim()
            .replace(/[\s\u00a0']/g, '')
            .replace(/[^\d,.-]/g, '');

        if (!str || !/^-?(?:\d+|\d+[.,]\d+|[.,]\d+)$/.test(str)) return null;

        const lastComma = str.lastIndexOf(',');
        const lastDot = str.lastIndexOf('.');
        if (lastComma !== -1 && lastDot !== -1) {
            const decimalSeparator = lastComma > lastDot ? ',' : '.';
            const groupingSeparator = decimalSeparator === ',' ? '.' : ',';
            str = str.replaceAll(groupingSeparator, '').replace(decimalSeparator, '.');
        } else if (lastComma !== -1) {
            str = str.replace(',', '.');
        } else if ((str.match(/\./g) || []).length > 1) {
            str = str.replaceAll('.', '');
        }

        const num = Number(str);
        return Number.isFinite(num) ? num : null;
    }

    isBlankExcelRow(excelRow) {
        return !Array.isArray(excelRow) || excelRow.slice(0, 5).every(
            value => value === null || value === undefined || String(value).trim() === ''
        );
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
            const newLine = new Line(
                null, // ID généré automatiquement
                lineData.numero,
                lineData.designation,
                lineData.unite,
                lineData.quantite,
                lineData.prix_unitaire,
                this.root, // Parent racine par défaut
                lineData.expanded !== undefined ? lineData.expanded : true
            );
            return this.root.addChild(newLine);
            // Insérer à la bonne position
            // return this.insertLineAtFlatIndex(newLine, index);
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
        this.updateFlatIndex();
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

        const lines = cachedFlatList.slice(start, start + nbRows);
        if (lines.length === 0) return 0;

        const firstLine = lines[0];
        const oldParent = firstLine.parent;
        const newParent = firstLine.getPreviousSibling();
        if (!oldParent || !newParent) return 0;

        // Ne garder que les vraies lignes sœurs de la première : les descendants
        // déjà présents dans la sélection (lignes repliées masquées) suivent
        // automatiquement leur parent, il ne faut pas les indenter séparément.
        const siblings = lines.filter(line => line.parent === oldParent);

        siblings.forEach(line => {
            oldParent.removeChild(line);
            newParent.addChild(line);
        });

        if (siblings.length > 0) {
            this.invalidateCache();
            return siblings.length;
        }

        return 0;
    }
 
    desindentLine(start, nbRows = 1) {

        const cachedFlatList = this.getFlatList();
        const nbLines = cachedFlatList.length;
        if (start < 0 || start + nbRows > nbLines) return false;

        const lines = cachedFlatList.slice(start, start + nbRows);
        if (lines.length === 0) return 0;

        const firstLine = lines[0];
        const oldParent = firstLine.parent;
        if (!oldParent || !oldParent.parent) return 0;
        const grandParent = oldParent.parent;

        // Ne garder que les vraies lignes sœurs de la première (voir indentLine).
        const siblings = lines.filter(line => line.parent === oldParent);

        // Index calculé une seule fois puis incrémenté : l'ancien parent ne bouge
        // pas dans grandParent.children pendant la boucle, ce qui préserve l'ordre.
        let insertIndex = grandParent.getChildIndex(oldParent) + 1;
        siblings.forEach(line => {
            oldParent.removeChild(line);
            grandParent.insertChildAt(line, insertIndex);
            insertIndex++;
        });

        if (siblings.length > 0) {
            this.invalidateCache();
            return siblings.length;
        }

        return 0;
    }

    moveLineUp(index) {
        const line = this.getLineByFlatIndex(index);
        if (line) {
            if (line.moveUp()) {
                this.invalidateCache();
                const newIndex = this.getLineIndexById(line.id);
                return newIndex;
            }
        };
        return -1;
    }

    moveLineDown(index) {
        const line = this.getLineByFlatIndex(index);
        if (line) {
            if (line.moveDown()) {
                this.invalidateCache();
                const newIndex = this.getLineIndexById(line.id);
                return newIndex;
            }
        };
        return -1;
    }
    // Méthode utilitaire pour échanger deux lignes dans la liste plate (utile pour le déplacement)
    swapLines(index1, index2) {
        const flatList = this.getFlatList();
        [flatList[index1], flatList[index2]] = [flatList[index2], flatList[index1]];
        this.invalidateCache();
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

class EmptyLineManager {
    constructor(lineManager) {
        this.lineManager = lineManager;
        this.emptyLineThreshold = 3; // Garder 3 lignes vides à la fin
    }
    
    /**
     * Vérifie si une ligne est vide
     */
    isEmptyLine(line) {
        return !line.designation || 
               line.designation.trim() === '' || 
               (line.quantite === 0 && 
                line.prix_unitaire === 0 && 
                (!line.numero || line.numero.trim() === ''));
    }
    
    /**
     * Vérifie si une ligne peut être supprimée (vide et sans enfants)
     */
    isRemovableEmptyLine(line) {
        return this.isEmptyLine(line) && !line.hasChildren;
    }
    
    /**
     * Ajoute des lignes vides à la fin si nécessaire
     */
    ensureEmptyLines() {
        const flatList = this.lineManager.getFlatList();
        let emptyLinesCount = 0;

        for (let index = flatList.length - 1; index >= 0; index--) {
            if (!this.isRemovableEmptyLine(flatList[index])) break;
            emptyLinesCount++;
        }
        
        if (emptyLinesCount < this.emptyLineThreshold) {
            const toAdd = this.emptyLineThreshold - emptyLinesCount;
            for (let i = 0; i < toAdd; i++) {
                this.lineManager.addEmptyLine();
            }
            this.lineManager.invalidateCache();
            return toAdd;
        }
        return 0;
    }
    
    /**
     * Nettoie les lignes vides (pour sauvegarde)
     */
    cleanupEmptyLines() {
        const flatList = this.lineManager.getFlatList();
        const toRemove = [];
        
        // Parcourir à l'envers pour ne pas perturber les indices
        for (let i = flatList.length - 1; i >= 0; i--) {
            const line = flatList[i];
            
            // Supprimer les lignes vides sans enfants
            if (this.isRemovableEmptyLine(line)) {
                // Ne pas supprimer si c'est la seule ligne
                if (flatList.length - toRemove.length <= 1) {
                    break;
                }
                toRemove.push(line);
            }
        }
        
        // Supprimer les lignes
        toRemove.forEach(line => {
            if (line.parent) {
                line.parent.removeChild(line);
                this.lineManager.lines.delete(line.id);
            }
        });
        
        if (toRemove.length > 0) {
            this.lineManager.invalidateCache();
        }
        
        return toRemove.length;
    }
    
    /**
     * Nettoie spécifiquement pour la sauvegarde
     */
    prepareForSave() {
        const removedCount = this.cleanupEmptyLines();
        
        // Ajouter exactement 1 ligne vide pour permettre l'ajout futur
        const hasEmptyLines = this.lineManager.getFlatList().some(line => this.isEmptyLine(line));
        if (!hasEmptyLines) {
            this.lineManager.addEmptyLine();
            return removedCount + 1;
        }
        
        return removedCount;
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
        this.isSyncing = false; // Éviter les boucles de synchronisation
        this.dataChanged = false;
        this.allLinesExpanded = true;
        
        // Initialisation
        this.hot = null;
        this.lineManager = null;
        this.colMontantIndex = 8; // Index de la colonne "montant"
        this.initialize();
    }

    initialize() {
        // Initialiser le LineManager
        this.lineManager = new LineManager(this.lotNom);
        
        // Charger les données initiales si présentes
        if (window.bordereauData && Array.isArray(window.bordereauData)) {
            this.lineManager = new LineManager(this.lotNom, window.bordereauData);

            // FORCER TOUTES LES LIGNES À ÊTRE EXPANDED À L'OUVERTURE
            this.expandAllLines();
        }
        
        // Initialiser Handsontable
        this.initHandsontable();
        
        // Configurer les raccourcis clavier
        this.setupKeyboardShortcuts();
        this.setupPlainTextPaste();
        this.markDataSaved();
    }

    /**
     * Ajoute une nouvelle ligne vide
     */
    addNewEmptyLine(atEnd = true) {
        let newLine;
        
        if (atEnd) {
            newLine = this.lineManager.addEmptyLine();
        } else {
            const selected = this.hot.getSelected();
            if (selected && selected.length > 0) {
                const index = selected[0][0];
                newLine = this.lineManager.addEmptyLineAt(index + 1);
            } else {
                newLine = this.lineManager.addEmptyLine();
            }
        }
        
        this.refreshTable(true);
        this.markDataChanged();
        
        // Sélectionner la nouvelle ligne
        setTimeout(() => {
            const newIndex = this.lineManager.getLineIndexById(newLine.id);
            if (newIndex !== -1) {
                this.hot.selectCell(newIndex, 4); // Colonne Désignation
                this.hot.scrollViewportTo(newIndex);
            }
        }, 50);
        
        return newLine;
    }
    expandAllLines() {
        this.lineManager.lines.forEach(line => {
            if (line.hasChildren) {
                line.expanded = true;
            }
        });
        this.lineManager.invalidateCache();
    }

    toggleExpandedAll() {
        const shouldExpand = !this.allLinesExpanded;
        this.lineManager.lines.forEach(line => {
            if (line.hasChildren) line.expanded = shouldExpand;
        });
        this.allLinesExpanded = shouldExpand;
        this.lineManager.invalidateCache();
        this.refreshTable();
        this.updateExpandAllButton();
    }

    updateExpandAllButton() {
        const button = document.getElementById('toggle-expanded-all-btn');
        if (!button) return;

        const icon = button.querySelector('i');
        const expand = !this.allLinesExpanded;
        button.title = expand ? 'Développer toutes les lignes filles' : 'Réduire toutes les lignes filles';
        if (icon) icon.className = expand ? 'fas fa-expand-alt' : 'fas fa-compress-alt';
    }

    markDataChanged() {
        this.dataChanged = true;
        const saveBtn = document.getElementById('save-btn');
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            saveBtn.title = 'Enregistrer les modifications';
        }
    }

    markDataSaved() {
        this.dataChanged = false;
        const saveBtn = document.getElementById('save-btn');
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.classList.add('opacity-50', 'cursor-not-allowed');
            saveBtn.title = 'Aucune modification à enregistrer';
        }
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

        // Mettre à jour le total initial
        this.updateTotal();
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
            copyPaste: {
                rowsLimit: Infinity,
                columnsLimit: Infinity,
                pasteMode: 'overwrite',
            },
            hiddenColumns: {columns: [0, 1, 2], indicators: false},
            hiddenRows: {rows: [], indicators: false},
            minSpareRows: 0, // Plus de lignes vides pour faciliter le collage
            height: 'auto',
            width: 'auto',
            rowHeights: 40,
            manualColumnResize: true,
            outsideClickDeselects: false,
            
            // Menu contextuel personnalisé
            contextMenu: {
                items: {
                    row_above: {
                        name: 'Insérer une ligne au-dessus',
                    },
                    row_below: {
                        name: 'Insérer une ligne en dessous',
                    },
                    remove_row: {
                        name: 'Supprimer la(les) ligne(s)',
                        callback: (key, selection) => {
                            const selected = this.getSafeSelection();
                            if (!selected) return;
                            const startRow = selected.startRow;
                            const endRow = selected.endRow;
                            const amount = endRow - startRow + 1;
                            this.handleManualRowDeletion(startRow, amount);
                        }
                    },
                    sep1: { name: '---------' },
                    copy: {
                        name: 'Copier',
                        callback: () => {
                            this.hot.getPlugin('copyPaste').copy();
                        }
                    },
                    paste: {
                        name: 'Coller',
                        callback: () => {
                            // Le paste est déjà géré par beforePaste
                            this.hot.getPlugin('copyPaste').paste();
                        }
                    }
                }
            },
            
            // Raccourcis clavier
            keyboard: {
                keys: [
                    ['Ctrl/Cmd+Enter', () => {
                        this.addNewEmptyLineAtEnd();
                    }],
                    ['Ctrl/Cmd+Shift+Up', () => {
                        this.moveUp();
                    }],
                    ['Ctrl/Cmd+Shift+Down', () => {
                        this.moveDown();
                    }],
                    ['Tab', (e) => {
                        if (!e.shiftKey) {
                            this.indente();
                        } else {
                            this.desindente();
                        }
                        return false; // Empêcher le comportement par défaut
                    }]
                ]
            },

            // Gérer l'ajout manuel de lignes
            beforeCreateRow: (index, amount, source) => {
                if (source === 'auto') {
                    return false; // Empêcher l'ajout automatique
                }
                // Gérer l'ajout manuel (via context menu, Ctrl+C, etc.)
                if (source === 'ContextMenu.row_above' || source === 'ContextMenu.row_below') {
                    // Ajouter des lignes dans LineManager
                    this.handleManualRowInsertion(index, amount, source);
                    return false; // Bloquer l'ajout natif, on gère nous-mêmes
                }
                
                // Pour les autres sources (paste, etc.), on gère aussi nous-mêmes
                if (amount > 0) {
                    this.handleManualRowInsertion(index, amount, source);
                    return false;
                }
                return true;
            },
            
            // Gérer la suppression de lignes
            beforeRemoveRow: (index, amount) => {
                // Ne pas supprimer la dernière ligne si elle est vide
                const flatList = this.lineManager.getFlatList();
                if (flatList.length - amount <= 0) {
                    return false;
                }
                return true;
            },

            // GESTION DES LIGNES
            afterRemoveRow: (index, amount) => {
                this.handleAfterRemoveRow(index, amount);
                
                // Ajouter des lignes vides si nécessaire
                setTimeout(() => {
                    this.lineManager.ensureEmptyLinesForEditing();
                    this.refreshTable(true);
                }, 50);
            },

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

                this.markDataChanged();
                this.scheduleEmptyLineCheck();
            },

            afterRender: () => {
                this.scheduleEmptyLineCheck();
            },

            // GESTION DE LA SELECTION
            afterSelection: () => this.displaySelectionSum(),

            // GESTION DU CLIC SUR LES TRIANGLES
            afterOnCellMouseDown: (event, coords, TD) => {
                if (event.target.classList.contains('toggle-triangle')) {
                    event.preventDefault();
                    event.stopPropagation();
                    
                    const row = parseInt(event.target.getAttribute('data-row'));
                    this.toggleExpansion(row);
                    return false;
                }
            },
        };
    }

    /**
     * Gère l'insertion manuelle de lignes
     */
    handleManualRowInsertion(index, amount, source) {        
        const flatList = this.lineManager.getFlatList();
        const newLines = [];
        // Ajuster l'index selon la source
        let adjustedIndex = index;
        if (source === 'ContextMenu.rowBelow') {
            adjustedIndex = index + 1;
        } else if (source === 'ContextMenu.rowAbove') {
            adjustedIndex = index;
        }


        for (let i = 0; i < amount; i++) {
            let newLine;
            const insertIndex = adjustedIndex + i;
            
            // Déterminer où insérer la ligne
            if (insertIndex >= flatList.length) {
                // Ajouter à la fin
                newLine = this.lineManager.addEmptyLine();
            } else if (insertIndex === 0) {
                // Ajouter au début
                newLine = this.lineManager.addEmptyLineAt(0);
            } else {
                // Insérer à un index spécifique
                const targetLine = flatList[insertIndex];
                if (targetLine && targetLine.parent) {
                    // Insérer avant la ligne cible dans son parent
                    const parent = targetLine.parent;
                    const siblingIndex = parent.children.indexOf(targetLine);
                    
                    newLine = new Line(
                        null,
                        '',
                        '',
                        '',
                        0,
                        0,
                        parent,
                        true
                    );
                    
                    parent.children.splice(siblingIndex, 0, newLine);
                    this.lineManager.lines.set(newLine.id, newLine);
                } else {
                    newLine = this.lineManager.addEmptyLineAt(insertIndex);
                }
            }
            
            if (newLine) {
                newLines.push(newLine);
            }
        }
        
        // Invalider le cache et rafraîchir
        this.lineManager.invalidateCache();
        this.refreshTable();
        this.markDataChanged();
        
        // Sélectionner la première nouvelle ligne
        if (newLines.length > 0) {
            setTimeout(() => {
                const firstNewIndex = this.lineManager.getLineIndexById(newLines[0].id);
                if (firstNewIndex !== -1) {
                    this.hot.selectCell(firstNewIndex, 4);
                    this.hot.scrollViewportTo(firstNewIndex);
                }
            }, 50);
        }
        
        return newLines;
    }

    /**
     * Gère la suppression manuelle de lignes
     */
    handleManualRowDeletion(index, amount) {
        console.log(`Suppression: ${amount} ligne(s) à l'index ${index}`);
        
        const flatList = this.lineManager.getFlatList();
        
        // Vérifier qu'on ne supprime pas toutes les lignes
        if (flatList.length - amount <= 0) {
            this.showMessage("Impossible de supprimer toutes les lignes", "warning");
            return false;
        }
        
        // Supprimer les lignes de la fin vers le début pour ne pas perturber les indices
        for (let i = amount - 1; i >= 0; i--) {
            const lineIndex = index + i;
            const line = flatList[lineIndex];
            
            if (line && line.parent) {
                console.log(`Suppression de la ligne à l'index ${lineIndex}`);
                line.parent.removeChild(line);
                this.lineManager.lines.delete(line.id);
            }
        }
        
        // Invalider le cache et rafraîchir
        this.lineManager.invalidateCache();
        this.refreshTable(true);
        this.markDataChanged();
        
        // Sélectionner la ligne suivante
        setTimeout(() => {
            const newIndex = Math.min(index, this.lineManager.nbLines - 1);
            if (newIndex >= 0) {
                this.hot.selectCell(newIndex, 4);
                this.hot.scrollViewportTo(newIndex);
            }
        }, 50);
        
        return true;
    }

    // ============================================================================
    // GESTION DU COLLAGE (VERSION SIMPLIFIÉE)
    // ============================================================================

    handlePaste(data, coords, fromNativeClipboard = false) {
        if (this.plainTextPasteHandled && !fromNativeClipboard) {
            this.plainTextPasteHandled = false;
            return false;
        }

        
        if (!data || !Array.isArray(data) || data.length === 0) {
            return true; // Laisser Handsontable gérer
        }

        console.info('Handsontable beforePaste:', {
            rowsReceived: data.length,
            columnsReceived: Math.max(...data.map(row => Array.isArray(row) ? row.length : 0)),
            startRow: coords?.[0]?.startRow ?? 0,
            startColumn: coords?.[0]?.startCol ?? 0,
        });
        
        // Déterminer la position de collage
        let startRow = 0;
        if (coords && Array.isArray(coords) && coords.length > 0) {
            startRow = coords[0].startRow;
        }
        
        // Traiter les données Excel
        this.processPastedData(data, startRow);
        
        return false; // Bloquer le traitement natif
    }

    processPastedData(excelData, startRow) {
        // 1. Traiter les données dans le LineManager
        const newIndices = this.lineManager.processExcelPaste(excelData, startRow);
        if (newIndices.length > 0) this.markDataChanged();
        
        // 2. Mettre à jour le tableau en une seule opération
        this.refreshTable();
        
    }

    refreshTable() {
        if (!this.hot) return;
        
        // 1. Mettre à jour les données sans recréer la configuration de la grille
        this.hot.loadData(this.lineManager.toTableData());
        
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

    scheduleEmptyLineCheck() {
        if (this.emptyLineCheckScheduled) return;

        this.emptyLineCheckScheduled = true;
        setTimeout(() => {
            this.emptyLineCheckScheduled = false;

            if (this.lineManager.ensureEmptyLinesForEditing() > 0) {
                this.refreshTable();
            }
        }, 50);
    }

    handleAfterRemoveRow(index, amount, source) {
        this.lineManager.removeLineByIndex(index, amount);
        this.updateTotal();
        this.dataChanged = true;
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
            td.className = (td.className || '') + ` title-row title-row-level-${Math.min(niveau, 4)}`;
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
            td.className = (td.className || '') + ` title-row title-row-level-${Math.min(line.level, 4)}`;
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
            td.className = `htRight title-row title-row-level-${Math.min(line.level, 4)}`;
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

    setupPlainTextPaste() {
        document.addEventListener('paste', (event) => {
            if (!this.hot || !this.hot.isListening()) return;
            if (this.hot.getActiveEditor()?.isOpened()) return;

            const plainText = event.clipboardData?.getData('text/plain');
            if (!plainText || !plainText.includes('\t')) return;

            const selected = this.getSafeSelection();
            if (!selected) return;

            const rows = plainText
                .replace(/\r\n?/g, '\n')
                .split('\n');
            if (rows.length > 1 && rows[rows.length - 1] === '') rows.pop();

            const data = rows.map(row => row.split('\t'));
            if (data.length === 0) return;

            event.preventDefault();
            event.stopImmediatePropagation();
            this.plainTextPasteHandled = true;
            console.info('Presse-papiers texte utilisé pour le collage Excel:', {
                rowsReceived: data.length,
                columnsReceived: Math.max(...data.map(row => row.length)),
            });
            this.handlePaste(data, [{
                startRow: selected.startRow,
                startCol: selected.startCol,
            }], true);
            setTimeout(() => {
                this.plainTextPasteHandled = false;
            }, 0);
        }, true);
    }

    showSumSelectedCells(hotInstance) {
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
                let value = parseFloat(hotInstance.getDataAtCell(row, col)) || 0;
                
                if (!isNaN(value) && value !== 0) {
                    sum += value;
                    cellCount++;
                }
            }
        }
        return { sum, cellCount };
    }

    displaySelectionSum() {
        if (!this.hot) return;
        
        const displayElement = document.getElementById('selectionSumDisplay');
        if (!displayElement) return;

        const result = this.showSumSelectedCells(this.hot);
        if (result && result.cellCount > 1) {
            const formattedSum = this.formatNumber(result.sum);
            const average = this.formatNumber(result.sum / result.cellCount) || 0;
            displayElement.textContent = `Somme : ${formattedSum} | Moyenne : ${average} | (${result.cellCount} cellules)`;
            displayElement.style.display = 'block';
        } else {
            displayElement.style.display = 'none';
        }
    }

    showMessage(message, type = 'info') {
        const container = document.getElementById('dynamic-messages');
        if (!container) {
            console.warn(message);
            return;
        }

        container.innerHTML = '';
        const alert = document.createElement('div');
        alert.className = `alert-${type} p-3 rounded-xl shadow-lg`;
        alert.textContent = message;
        container.appendChild(alert);
    }

    /**
     * Affiche un toast discret dans la barre d'outils (remplace le message des totaux s'il est actif).
     */
    showToolbarToast(message, type = 'success') {
        const sumDisplay = document.getElementById('selectionSumDisplay');
        if (sumDisplay) {
            sumDisplay.style.display = 'none';
        }

        const toast = document.getElementById('toolbarToast');
        if (!toast) {
            console.info(message);
            return;
        }

        clearTimeout(this._toolbarToastTimeout);
        toast.textContent = message;
        toast.className = `toolbar-toast toolbar-toast-${type}`;
        toast.classList.remove('hidden');
        void toast.offsetWidth; // relance l'animation si un toast était déjà visible
        toast.classList.add('toolbar-toast-visible');

        this._toolbarToastTimeout = setTimeout(() => {
            toast.classList.remove('toolbar-toast-visible');
            toast.classList.add('hidden');
        }, 2500);
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
            this.markDataChanged();
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
            this.markDataChanged();
            this.refreshTable();
        }
        else {
            console.log('desindentation failed');
        }
        
    }

    moveDown() {
        const selected = this.getSafeSelection();
        if (!selected || selected.nbRows === 0) {
            alert("Veuillez sélectionner une ligne");
            return;
        }
        const startRow = selected.startRow;
        const newIndex = this.lineManager.moveLineDown(startRow);

        if (newIndex !== -1) {
            this.markDataChanged();
            this.refreshTable();
            // Reselect the moved line
            this.hot.selectCell(newIndex, selected.startCol);
        }
    }

    moveUp() {
        const selected = this.getSafeSelection();
        if (!selected || selected.nbRows === 0) {
            alert("Veuillez sélectionner une ligne");
            return;
        }
        const startRow = selected.startRow;
        const newIndex = this.lineManager.moveLineUp(startRow);

        if (newIndex !== -1) {
            this.markDataChanged();
            this.refreshTable();
            // Reselect the moved line
            this.hot.selectCell(newIndex, selected.startCol);
        }
    }

    saveData() {
        const saveBtn = document.getElementById('save-btn');
        if (!this.dataChanged) return;
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enregistrement...';
        }
        
        const flatList = this.lineManager.getFlatList();

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
                this.showToolbarToast(data.message, 'success');
                if (data.lignes) {
                    Object.entries(data.lignes).forEach(([oldId, newId]) => {
                        const line = this.lineManager.lines.get(oldId);
                        if (!line) return;
                        line.id = newId;
                        this.lineManager.lines.delete(oldId);
                        this.lineManager.lines.set(newId, line);
                    });
                    this.lineManager.invalidateCache();
                }
                this.markDataSaved();
            } else {
                throw new Error(data.message);
            }
        })
        .catch(error => {
            console.error('Erreur:', error);
            this.showToolbarToast("Erreur d'enregistrement : " + error.message, 'error');
        })
        .finally(() => {
            if (saveBtn) {
                saveBtn.innerHTML = '<i class="fas fa-save"></i>';
                if (this.dataChanged) {
                    saveBtn.disabled = false;
                    saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                }
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
window.toggleExpandedAll = function() { window.bordereauManager?.toggleExpandedAll(); };
window.insertChildLine = function() { window.bordereauManager?.insertChildLine(); };
window.indente = function() { window.bordereauManager?.indente(); };
window.desindente = function() { window.bordereauManager?.desindente(); };
window.moveUp = function() { window.bordereauManager?.moveUp(); };
window.moveDown = function() { window.bordereauManager?.moveDown(); };
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