
// ============================================================================
// CLASSES DE BASE OPTIMISÉES
// ============================================================================

class Line extends TreeNode {
    constructor(id = null, numero = "", designation = "", unite = "", 
                quantite = 0, pu = 0, parent = null, expanded = true) {
        super({
            id: id || `line_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`,
            numero,
            designation,
            parent,
            expanded,
        });
        this.unite = unite;
        this.quantite = parseFloat(quantite) || 0;
        this.prix_unitaire = parseFloat(pu) || 0;
    }

    get amount() {
        if (this._cachedAmount !== null) return this._cachedAmount;

        if (this.hasChildren) {
            this._cachedAmount = this.children.reduce((sum, child) => sum + child.amount, 0);
        } else {
            this._cachedAmount = this._computeOwnAmount();
        }
        return this._cachedAmount;
    }

    _computeOwnAmount() {
        return this.quantite * this.prix_unitaire;
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
        return this.flatIndex.get(id) ?? -1;
    }

    invalidateCache() {
        this.cachedFlatList = null;
        this.flatIndex.clear();
    }

    get totalAmount() {
        return this.root.amount;
    }

    /**
     * Convertit toutes les lignes en données pour le tableau
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

        siblings.forEach(line => line.indent());

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
        // Ne garder que les vraies lignes sœurs de la première (voir indentLine).
        const siblings = lines.filter(line => line.parent === oldParent);

        // Insérer à chaque fois après le parent inverse l'ordre si on avance.
        [...siblings].reverse().forEach(line => line.desindent());

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
        this.emptyLineThreshold = 1;
    }
    
    /**
     * Vérifie si une ligne est vide
     */
    isEmptyLine(line) {
        return [line.numero, line.designation, line.unite].every(
            value => !value || value.trim() === ''
        ) && line.quantite === 0 && line.prix_unitaire === 0;
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
        const rootLines = this.lineManager.root.children;
        let emptyLinesCount = 0;

        for (let index = rootLines.length - 1; index >= 0; index--) {
            if (!this.isRemovableEmptyLine(rootLines[index])) break;
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
        this.tableView = null;
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
        }
        
        if (!window.TableView) {
            throw new Error('TableView n’est pas chargé.');
        }
        this.initTableView();
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
            const selection = this.getSafeSelection();
            if (selection) {
                newLine = this.lineManager.addEmptyLineAt(selection.startRow + 1);
            } else {
                newLine = this.lineManager.addEmptyLine();
            }
        }
        
        this.refreshTable(true);
        this.markDataChanged();
        
        // Sélectionner la nouvelle ligne
        setTimeout(() => {
            const newIndex = this.lineManager.getLineIndexById(newLine.id);
            if (newIndex !== -1) this.focusCell(newIndex, 1);
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
        const parents = Array.from(this.lineManager.lines.values()).filter(line => line.hasChildren);
        if (parents.length === 0) return;
        const shouldExpand = parents.some(line => !line.expanded);
        this.lineManager.lines.forEach(line => {
            if (line.hasChildren) line.expanded = shouldExpand;
        });
        this.allLinesExpanded = shouldExpand;
        this.lineManager.invalidateCache();
        this.refreshTable();
        this.markDataChanged();
        this.updateExpandAllButton();
    }

    updateExpandAllButton() {
        this.allLinesExpanded = Array.from(this.lineManager.lines.values())
            .every(line => !line.hasChildren || line.expanded);
        const button = document.getElementById('toggle-expanded-all-btn');
        if (!button) return;

        const icon = button.querySelector('i');
        const expand = !this.allLinesExpanded;
        button.title = expand ? 'Développer toutes les lignes filles' : 'Réduire toutes les lignes filles';
        if (icon) icon.className = expand ? 'fas fa-expand-alt' : 'fas fa-compress-alt';
    }

    markDataChanged() {
        this.dataChanged = true;
        this.changeRevision = (this.changeRevision || 0) + 1;
        const saveBtn = document.getElementById('save-btn');
        if (saveBtn) {
            saveBtn.disabled = Boolean(this.saving);
            saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            if (!this.saving) saveBtn.title = 'Enregistrer les modifications';
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
 
    initTableView() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`Container #${this.containerId} non trouvé`);
            return;
        }
        const appearanceElement = document.getElementById('bdp-appearance-data');
        this.appearanceData = appearanceElement
            ? JSON.parse(appearanceElement.textContent)
            : { values: {}, defaults: {}, revision: '' };
        this.appearance = { ...this.appearanceData.values };

        this.tableView = new window.TableView(container, {
            label: 'Détail des prix unitaires',
            data: this.lineManager.toTableData(),
            rowKey: 'id',
            locale: 'fr-FR',
            selectionMode: 'multi',
            rowHeaders: this.appearance.row_headers === true,
            freezeColumns: 0,
            resizableHeader: true,
            headerResizeLabel: 'Redimensionner la hauteur de l’en-tête',
            onHeaderResize: ({ height }) => {
                this.appearance.header_height = height;
            },
            clipboard: { copy: true, paste: true, parseTsv: true, includeHiddenRows: true },
            createRow: () => ({
                id: new Line().id, numero: '', designation: '', unite: '',
                quantite: 0, prix_unitaire: 0, niveau: 1, est_titre: false,
                _expanded: true, montant: 0,
            }),
            onSort: ({ rows }) => {
                const children = new Map();
                rows.forEach(row => {
                    const line = this.lineManager.lines.get(row.id);
                    if (!line?.parent) throw new Error('Ligne inconnue lors du tri du bordereau.');
                    if (!children.has(line.parent)) children.set(line.parent, []);
                    children.get(line.parent).push(line);
                });
                children.forEach((ordered, parent) => {
                    if (ordered.length !== parent.children.length) {
                        throw new Error('Tri incomplet du bordereau.');
                    }
                });
                children.forEach((ordered, parent) => { parent.children.splice(0, parent.children.length, ...ordered); });
                this.lineManager.invalidateCache();
                this.markDataChanged();
            },
            rowHeaders: true,
            rowHeaderWidth: 50,
            freezeRowHeaders: true,
            liveEdit: false,
            appearance: this.getTableAppearance(),
            columns: this.getTableColumns(),
            hierarchy: {
                columnKey: 'designation',
                isGroup: row => row.est_titre,
                getLevel: row => Math.max(0, row.niveau - 1),
                isExpanded: row => row._expanded,
                onToggle: rowIndex => this.toggleExpansion(rowIndex),
            },
            rowActions: {
                contextMenu: true,
                items: () => this.getRowActions().map(action => ({
                    id: action.id,
                    label: action.label,
                    group: action.group,
                    inline: false,
                    enabled: action.id === 'delete' || action.enabled,
                })),
                onAction: action => this.executeRowAction(action),
            },
            rowClassName: row => row.est_titre
                ? `native-bdp-title-row title-row-level-${Math.min(row.niveau, 4)}` : '',
            isCellEditable: ({ column, row }) => {
                if (['numero', 'designation', 'unite'].includes(column.key)) return true;
                return !row.est_titre && ['quantite', 'prix_unitaire'].includes(column.key);
            },
            onCellChange: ({ rowIndex, column, value }) => {
                if ((column.key === 'quantite' || column.key === 'prix_unitaire')
                    && (value === '' || value < 0)) {
                    this.showMessage('Les quantités et prix doivent être des nombres positifs.', 'warning');
                    return false;
                }
                this.handleCellChange(rowIndex, column.key, value);
                this.markDataChanged();
                this.updateTotal();
                this.scheduleEmptyLineCheck();
            },
            onDataChange: event => {
                if (event.phase === 'paste') {
                    event.newRows.forEach(row => {
                        const line = new Line(row.id);
                        this.lineManager.root.addChild(line);
                        this.lineManager.lines.set(line.id, line);
                    });
                    this.lineManager.invalidateCache();
                    event.changes.forEach(({ row, column, value }) => {
                        this.handleCellChange(this.lineManager.getLineIndexById(row.id), column.key, value);
                    });
                    this.markDataChanged();
                    this.refreshTable();
                } else if (event.phase === 'commit') {
                    this.lineManager.getFlatList().forEach((line, index) => {
                        if (line.hasChildren) this.tableView.refreshRow(index);
                    });
                }
            },
            onClipboardError: error => this.showMessage(error.message, 'warning'),
            onSelectionChange: () => {
                this.displaySelectionSum();
                this.updateToolbar();
            },
            onValidationError: ({ column }) => {
                if (column.type === 'number') {
                    this.showMessage('Saisir un nombre positif ou nul.', 'warning');
                }
            },
        });
        this.updateHiddenRows();
        this.setupAppearanceDialog();
        this.refreshTable();
    }

    // Return the column definitions for the table, including appearance settings and validation rules.
    getTableColumns() {
        const appearance = this.appearance || this.appearanceData?.values || {};
        return [
            { key: 'numero', label: 'N°', sortable: true, width: appearance.width_numero || 100,
                minWidth: 60, maxWidth: 200, editable: true },
            { key: 'designation', label: 'Désignation', sortable: true, width: appearance.width_designation || 500,
                minWidth: 240, maxWidth: 1200, editable: true },
            { key: 'unite', label: 'Unité', sortable: false, width: appearance.width_unite || 100,
                minWidth: 55, maxWidth: 180, align: 'center', editable: true },
            { key: 'quantite', label: 'Quantité', type: 'number', sortable: false,
                width: appearance.width_quantite || 120, minWidth: 80, maxWidth: 220,
                decimals: 3, hideZero: true, allowEmpty: false,
                validate: value => value >= 0 || 'La quantité doit être positive ou nulle.' },
            { key: 'prix_unitaire', label: 'PU (DH)', type: 'number', sortable: false,
                width: appearance.width_prix_unitaire || 140, minWidth: 100, maxWidth: 260,
                decimals: 2, hideZero: true, allowEmpty: false,
                validate: value => value >= 0 || 'Le prix doit être positif ou nul.' },
            { key: 'montant', label: 'Montant (DH)', type: 'number', sortable: true,
                width: appearance.width_montant || 160, minWidth: 100, maxWidth: 260,
                decimals: 2, hideZero: true, className: 'native-bdp-amount',
                editable: false, getValue: (_row, rowIndex) =>
                    this.lineManager.getLineByFlatIndex(rowIndex)?.amount ?? 0 },
        ];
    }

    // Return the appearance settings for the table, including row, header, and active row colors.
    getTableAppearance(values = this.appearance || {}) {
        const rowColor = values.row_color || '#f8f6ef';
        const headerColor = values.header_color || '#f0ede5';
        const activeColor = values.active_color || '#7baec1';
        const computedTextColor = this.getContrastingInk([
            rowColor,
            this.blendColor(activeColor, rowColor, 0.14),
            this.blendColor(activeColor, rowColor, 0.22),
        ]);
        return {
            rowColor,
            textColor: values.text_color_auto === false
                ? values.text_color || computedTextColor : computedTextColor,
            headerColor,
            headerTextColor: this.getContrastingInk(headerColor),
            titleColor: values.title_color || '#24485a',
            amountColor: values.amount_color || '#15803d',
            activeColor,
            selectionColor: values.selection_color_auto === false
                ? values.selection_color || this.blendColor(activeColor, rowColor, 0.14)
                : this.blendColor(activeColor, rowColor, 0.14),
            borderColor: values.border_color || '#a9cad6',
            rowHeight: Number(values.row_height) || 26,
            headerHeight: Number(values.header_height) || 42,
            fontSize: Number(values.font_size) || 13,
            stickyHeader: values.sticky_header !== false,
        };
    }

    getContrastingInk(colors) {
        const parsed = (Array.isArray(colors) ? colors : [colors]).map(value => {
            const match = /^#([0-9a-f]{6})$/i.exec(String(value || ''));
            return match ? [0, 2, 4].map(index =>
                parseInt(match[1].slice(index, index + 2), 16)) : null;
        }).filter(Boolean);
        if (!parsed.length) return '#24485a';
        const luminance = channels => channels
            .map(channel => {
                channel /= 255;
                return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
            })
            .reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0);
        const contrast = (foreground, background) => {
            const first = luminance(foreground);
            const second = luminance(background);
            return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
        };
        const darkInk = [36, 72, 90];
        const lightInk = [248, 246, 239];
        const minimumContrast = ink => Math.min(...parsed.map(background =>
            contrast(ink, background)));
        return minimumContrast(darkInk) >= minimumContrast(lightInk) ? '#24485a' : '#f8f6ef';
    }

    blendColor(foreground, background, opacity) {
        const parse = color => [0, 2, 4].map(index =>
            parseInt(color.slice(index + 1, index + 3), 16));
        const front = parse(foreground);
        const back = parse(background);
        return `#${front.map((value, index) =>
            Math.round(value * opacity + back[index] * (1 - opacity))
            .toString(16).padStart(2, '0')).join('')}`;
    }

    applyTableAppearance(values) {
        if (!this.tableView) return;
        const configuration = this.tableView.getConfiguration();
        configuration.rowHeaders = values.row_headers === true;
        configuration.appearance = {
            ...configuration.appearance,
            ...this.getTableAppearance(values),
        };
        this.tableView.applyConfiguration(configuration);
    }

    setupAppearanceDialog() {
        const dialog = document.getElementById('bdp-appearance-dialog');
        const form = document.getElementById('bdp-appearance-form');
        const errorBox = document.getElementById('bdp-appearance-errors');
        if (!dialog || !form || !errorBox) return;

        const fields = Array.from(form.querySelectorAll('input[name]:not([type="hidden"])'));
        const cancel = document.getElementById('bdp-appearance-cancel');
        const close = document.getElementById('bdp-appearance-close');
        const defaults = document.getElementById('bdp-appearance-defaults');
        const colorFields = new Map(Array.from(form.querySelectorAll('input[type="color"]'))
            .map(field => [field.name, field]));
        const hexFields = new Map(Array.from(form.querySelectorAll('[data-hex-for]'))
            .map(field => [field.dataset.hexFor, field]));
        const autoColorFields = {
            text_color_auto: 'text_color',
            selection_color_auto: 'selection_color',
        };
        let openingValues;
        const updateHexFields = () => colorFields.forEach((field, name) => {
            const hex = hexFields.get(name);
            if (!hex) return;
            hex.value = field.value;
            hex.setCustomValidity('');
            hex.removeAttribute('aria-invalid');
        });
        const updateAutoColorState = () => Object.entries(autoColorFields).forEach(([toggleName, colorName]) => {
            const toggle = form.elements.namedItem(toggleName);
            const color = colorFields.get(colorName);
            const hex = hexFields.get(colorName);
            const automatic = toggle.checked;
            color.closest('.bdp-appearance-color-inputs').classList.toggle('is-auto', automatic);
            color.disabled = automatic;
            hex.disabled = automatic;
            color.title = automatic ? 'La couleur est calculée automatiquement.' : '';
            hex.title = color.title;
        });
        const fill = values => {
            fields.forEach(field => {
                if (values[field.name] === undefined) return;
                if (field.type === 'checkbox') field.checked = Boolean(values[field.name]);
                else field.value = values[field.name];
            });
            updateHexFields();
            updateAutoColorState();
            this.previewAppearance(fields);
        };

        document.getElementById('bdp-open-appearance')?.addEventListener('click', () => {
            errorBox.textContent = '';
            openingValues = {
                ...this.appearanceData.values,
                header_height: this.tableView.getConfiguration().appearance.headerHeight,
            };
            fill(openingValues);
            dialog.showModal();
        });
        fields.forEach(field => field.addEventListener('input', () => {
            if (field.type === 'color') {
                const hex = hexFields.get(field.name);
                if (hex) hex.value = field.value;
            }
            if (field.type === 'checkbox') updateAutoColorState();
            this.previewAppearance(fields);
        }));
        hexFields.forEach((hex, colorName) => hex.addEventListener('input', () => {
            const color = colorFields.get(colorName);
            const value = hex.value.trim();
            const valid = /^#[\da-f]{6}$/i.test(value);
            hex.setCustomValidity(valid ? '' : 'Utilisez une couleur au format #RRGGBB.');
            hex.toggleAttribute('aria-invalid', !valid);
            if (!valid) return;
            color.value = value.toLowerCase();
            this.previewAppearance(fields);
        }));
        defaults?.addEventListener('click', () => fill(this.appearanceData.defaults));
        const dismiss = () => {
            if (form.getAttribute('aria-busy') === 'true') return;
            fill(openingValues);
            dialog.close();
        };
        cancel?.addEventListener('click', dismiss);
        close?.addEventListener('click', dismiss);
        dialog.addEventListener('cancel', event => {
            event.preventDefault();
            dismiss();
        });
        form.addEventListener('submit', async event => {
            event.preventDefault();
            if (!form.reportValidity()) return;
            errorBox.textContent = '';
            const widthFields = {
                numero: 'width_numero',
                designation: 'width_designation',
                unite: 'width_unite',
                quantite: 'width_quantite',
                prix_unitaire: 'width_prix_unitaire',
                montant: 'width_montant',
            };
            this.tableView.getConfiguration().columns.forEach(column => {
                const fieldName = widthFields[column.key];
                if (fieldName) {
                    form.elements.namedItem(fieldName).value = String(Math.round(column.width));
                }
            });
            const payload = new FormData(form);
            colorFields.forEach((field, name) => payload.set(name, field.value));
            payload.set('revision', this.appearanceData.revision);
            form.setAttribute('aria-busy', 'true');
            form.querySelector('fieldset').disabled = true;
            form.querySelector('[type="submit"]').disabled = true;
            if (cancel) cancel.disabled = true;
            if (close) close.disabled = true;

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: payload,
                    headers: {
                        'X-CSRFToken': form.elements.namedItem('csrfmiddlewaretoken').value,
                        Accept: 'application/json',
                    },
                });
                const result = await response.json();
                if (!response.ok) {
                    errorBox.textContent = Object.values(result.errors || {}).flat().join(' ')
                        || `Enregistrement refusé (HTTP ${response.status}).`;
                    return;
                }
                this.appearanceData = result;
                fill(result.values);
                dialog.close();
                this.showToolbarToast('Configuration du bordereau enregistrée.');
            } catch (error) {
                errorBox.textContent = error.message || 'Impossible d’enregistrer la configuration.';
            } finally {
                form.setAttribute('aria-busy', 'false');
                form.querySelector('fieldset').disabled = false;
                form.querySelector('[type="submit"]').disabled = false;
                if (cancel) cancel.disabled = false;
                if (close) close.disabled = false;
            }
        });
    }

    previewAppearance(fields) {
        const values = Object.fromEntries(fields.map(field => [
            field.name,
            field.type === 'checkbox' ? field.checked
                : field.type === 'number' ? Number(field.value) : field.value,
        ]));
        this.appearance = { ...this.appearance, ...values };
        this.applyTableAppearance(this.appearance);
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
                if (firstNewIndex !== -1) this.focusCell(firstNewIndex, 1);
            }, 50);
        }
        
        return newLines;
    }

    /**
     * Gère la suppression manuelle de lignes
     */
    handleManualRowDeletion(index, amount) {
        // console.log(`Suppression: ${amount} ligne(s) à l'index ${index}`);
        
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
                // console.log(`Suppression de la ligne à l'index ${lineIndex}`);
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
            if (newIndex >= 0) this.focusCell(newIndex, 1);
        }, 50);
        
        return true;
    }

    handleSelectedRowDeletion() {
        const selectedIds = new Set(this.getSelectedLineIds());
        if (selectedIds.size === 0) return false;

        const flatList = this.lineManager.getFlatList();
        const selectedLines = flatList.filter(line => selectedIds.has(line.id));
        if (selectedLines.some(line => line.hasChildren)
            && !window.confirm('Supprimer également les sous-lignes des groupes sélectionnés ?')) {
            return false;
        }

        const roots = selectedLines.filter(line => {
            for (let parent = line.parent; parent; parent = parent.parent) {
                if (selectedIds.has(parent.id)) return false;
            }
            return true;
        });
        const removedLines = new Set();
        roots.forEach(line => {
            removedLines.add(line);
            line.descendants.forEach(descendant => removedLines.add(descendant));
        });

        if (removedLines.size >= flatList.length) {
            this.showMessage('Impossible de supprimer toutes les lignes', 'warning');
            return false;
        }

        const nextIndex = Math.min(...roots.map(line => flatList.indexOf(line)));
        roots
            .sort((left, right) => flatList.indexOf(right) - flatList.indexOf(left))
            .forEach(line => line.parent?.removeChild(line));
        removedLines.forEach(line => this.lineManager.lines.delete(line.id));

        this.lineManager.invalidateCache();
        this.refreshTable(true);
        this.markDataChanged();

        setTimeout(() => {
            const row = Math.min(nextIndex, this.lineManager.nbLines - 1);
            if (row >= 0) this.focusCell(row, 1);
        }, 50);

        return true;
    }

    // ============================================================================
    // GESTION DU COLLAGE (VERSION SIMPLIFIÉE)
    // ============================================================================

    processPastedData(excelData, startRow) {
        // 1. Traiter les données dans le LineManager
        const newIndices = this.lineManager.processExcelPaste(excelData, startRow);
        if (newIndices.length > 0) this.markDataChanged();
        
        // 2. Mettre à jour le tableau en une seule opération
        this.refreshTable();
        
    }

    refreshTable() {
        if (!this.tableView) return;
        const viewport = this.tableView.captureViewport?.();
        this.lineManager.ensureEmptyLinesForEditing();
        this.tableView.setData(this.lineManager.toTableData());
        
        this.updateHiddenRows();
        this.updateTotal();
        this.updateToolbar();
        this.updateExpandAllButton();
        this.tableView.restoreViewport?.(viewport);
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

    // ============================================================================
    // GESTION DE L'EXPANSION/HIERARCHIE
    // ============================================================================

    toggleExpansion(row) {
        if (this.lineManager.toggleExpansion(row)) {
            this.refreshTable();
            this.markDataChanged();
        }
    }

    updateHiddenRows() {
        if (!this.tableView?.setHiddenRows) return;
        this.tableView.setHiddenRows(this.lineManager.getHiddenRows());
    }

    // ============================================================================
    // FONCTIONS UTILITAIRES
    // ============================================================================

    getSafeSelection() {
        const selection = this.tableView?.getSelection();
        if (!selection?.ranges?.length) return null;
        const activeRow = selection.activeCell?.rowIndex;
        return selection.ranges.find(range => activeRow >= range.startRow && activeRow <= range.endRow)
            || selection.ranges[0];
    }

    getSelectedLineIds() {
        return this.tableView?.getSelection()?.rowKeys || [];
    }

    getRowActions() {
        const selection = this.tableView?.getSelection();
        const range = this.getSafeSelection();
        const line = range ? this.lineManager.getLineByFlatIndex(range.startRow) : null;
        const hasSingleRange = selection?.ranges?.length === 1;
        const canMove = Boolean(line && range?.nbRows === 1 && hasSingleRange);
        const selectedIds = new Set(selection?.rowKeys || []);
        const removedLines = new Set();
        this.lineManager.getFlatList().forEach(item => {
            if (!selectedIds.has(item.id)) return;
            removedLines.add(item);
            item.descendants.forEach(descendant => removedLines.add(descendant));
        });
        return [
            { id: 'add-child', toolbarId: 'toolbar-add-child', method: 'insertChildLine',
                label: 'Insérer une ligne avant', icon: 'fas fa-plus', group: 0,
                enabled: !selection || canMove },
            { id: 'delete', toolbarId: 'toolbar-delete', method: 'handleSelectedRowDeletion',
                label: 'Supprimer cette ligne', icon: 'fas fa-trash', group: 0,
                enabled: removedLines.size > 0 && removedLines.size < this.lineManager.nbLines },
            { id: 'up', toolbarId: 'toolbar-up', method: 'moveUp',
                label: 'Monter en haut', icon: 'fas fa-arrow-up', group: 1,
                enabled: Boolean(canMove && line.canMoveUp()) },
            { id: 'down', toolbarId: 'toolbar-down', method: 'moveDown',
                label: 'Descendre en bas', icon: 'fas fa-arrow-down', group: 1,
                enabled: Boolean(canMove && line.canMoveDown()) },
            { id: 'indent', toolbarId: 'toolbar-indent', method: 'indente',
                label: 'Avancer (Indenter) →', icon: 'fas fa-indent', group: 2,
                enabled: Boolean(line && hasSingleRange && line.getPreviousSibling()) },
            { id: 'outdent', toolbarId: 'toolbar-outdent', method: 'desindente',
                label: 'Reculer (Désindenter) ←', icon: 'fas fa-outdent', group: 2,
                enabled: Boolean(line && hasSingleRange && line.parent?.parent) },
        ];
    }

    executeRowAction(id) {
        const action = this.getRowActions().find(item => item.id === id);
        if (!action?.enabled) {
            this.showMessage('Cette action n’est pas disponible pour la sélection actuelle.', 'warning');
            return false;
        }
        return this[action.method]();
    }

    updateToolbar() {
        if (!this.tableView) return;

        this.getRowActions().forEach(action => {
            const button = document.getElementById(action.toolbarId);
            if (!button) return;
            button.disabled = !action.enabled;
            button.setAttribute('aria-disabled', String(!action.enabled));
            button.title = action.label;
            button.setAttribute('aria-label', action.label);
            const icon = button.querySelector('i');
            if (icon) icon.className = action.icon;
        });
        const states = {
            'toggle-expanded-all-btn': Array.from(this.lineManager.lines.values()).some(item => item.hasChildren),
        };

        Object.entries(states).forEach(([id, enabled]) => {
            const button = document.getElementById(id);
            if (!button) return;
            button.disabled = !enabled;
            button.setAttribute('aria-disabled', String(!enabled));
        });
    }

    focusCell(row, column = 1) {
        if (!this.tableView?.selectCell) return false;
        this.tableView.selectCell(row, column);
        this.tableView.scrollToRow?.(row);
        return true;
    }

    formatNumber(value, decimals = 2) {
        return value.toLocaleString('fr-FR', {
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

    showSumSelectedCells() {
        const values = this.tableView?.getSelectedCellValues?.() || [];
        let sum = 0;
        let cellCount = 0;

        values.forEach(value => {
            const numericValue = Number.parseFloat(value) || 0;
            if (Number.isFinite(numericValue) && numericValue !== 0) {
                sum += numericValue;
                cellCount++;
            }
        });

        return { sum, cellCount };
    }

    displaySelectionSum() {
        if (!this.tableView) return;

        const displayElement = document.getElementById('selectionSumDisplay');
        if (!displayElement) return;

        const result = this.showSumSelectedCells();
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
        const selected = this.getSafeSelection();
        const activeRow = this.tableView?.getSelection()?.activeCell?.rowIndex ?? selected?.startRow;
        const currentLine = activeRow === undefined ? null : this.lineManager.getLineByFlatIndex(activeRow);
        const parent = currentLine?.parent || this.lineManager.root;
        const index = currentLine ? parent.children.indexOf(currentLine) : parent.children.length;
        const newLine = new Line(null, '', 'Nouvelle ligne', '', 1, 0);
        if (!parent.insertChildAt(newLine, index)) {
            this.showMessage('Impossible d’insérer une ligne.', 'warning');
            return false;
        }
        this.lineManager.lines.set(newLine.id, newLine);
        this.lineManager.invalidateCache();
        this.markDataChanged();
        this.refreshTable();
        this.focusCell(this.lineManager.getLineIndexById(newLine.id), 1);
        return newLine;
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
            this.focusCell(newIndex, selected.startCol);
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
            this.focusCell(newIndex, selected.startCol);
        }
    }

    saveData() {
        const saveBtn = document.getElementById('save-btn');
        if (!this.dataChanged || this.saving) return;
        this.saving = true;
        const savedRevision = this.changeRevision;
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i>';
            saveBtn.setAttribute('aria-busy', 'true');
            saveBtn.setAttribute('aria-label', 'Enregistrement en cours');
            saveBtn.title = 'Enregistrement en cours';
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
            _expanded: line.expanded,
            parent_id: line.parent ? line.parent.id : null
        }));

        return fetch(this.saveUrl, {
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
                if (this.changeRevision === savedRevision) this.markDataSaved();
            } else {
                throw new Error(data.message);
            }
        })
        .catch(error => {
            console.error('Erreur:', error);
            this.showToolbarToast("Erreur d'enregistrement : " + error.message, 'error');
        })
        .finally(() => {
            this.saving = false;
            if (saveBtn) {
                saveBtn.innerHTML = '<i class="fas fa-save"></i>';
                saveBtn.removeAttribute('aria-busy');
                saveBtn.setAttribute('aria-label', 'Enregistrer les modifications');
                saveBtn.title = this.dataChanged
                    ? 'Enregistrer les modifications' : 'Aucune modification à enregistrer';
                if (this.dataChanged) {
                    saveBtn.disabled = false;
                    saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                }
            }
        });
    }

    getExportRows() {
        return this.lineManager.getFlatList().map(line => [
            line.numero,
            line.designation,
            line.unite,
            line.quantite,
            line.prix_unitaire,
            line.amount,
        ]);
    }

    exportExcel() {
        const exportData = this.getExportRows();
        const wb = XLSX.utils.book_new();
        const wsData = [
            ['N°', 'Désignation', 'Unité', 'Quantité', 'PU (DH)', 'Montant (DH)'],
            ...exportData,
        ];
        const ws = XLSX.utils.aoa_to_sheet(wsData);
        XLSX.utils.book_append_sheet(wb, ws, "Bordereau");
        XLSX.writeFile(wb, `bordereau_${this.lotNom.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.xlsx`);
    }

    exportPDF() {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        const exportData = this.getExportRows();
        const headers = ['N°', 'Désignation', 'Unité', 'Quantité', 'PU (DH)', 'Montant (DH)'];
        const body = exportData;
        
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
window.runBordereauAction = function(action) { return window.bordereauManager?.executeRowAction(action); };
window.addBordereauEmptyLine = function() { return window.bordereauManager?.addNewEmptyLine(); };
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
                saveUrl: window.saveUrl || '',
            });
        }, 100);
    }
});