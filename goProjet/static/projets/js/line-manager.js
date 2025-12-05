// Class Line, LineManager - JS
    class Line {
        constructor(id = null, numero = "N°", designation = "Désignation", unite = "U", quantite = 1, pu = 0, parent = null, _expanded = false) {
            this.id = id;
            this.children = [];
            this.numero = numero;
            this.designation = designation;
            this.unite = unite;
            this.quantite = quantite;
            this.prix_unitaire = pu;
            this.parent = parent;
            this._expanded = _expanded;
        }

        level() {
            let level = 0;
            let currentNode = this;
            while (currentNode.parent) {
                level += 1;
                currentNode = currentNode.parent;
            }
            return level;
        }
        
        forEachChild(callback) {
            self.children.forEach(callback);
        }

        getChildIndex(child) {
            return this.children.indexOf(child);
        }

        findChildById(id) {
            return this.children.find(child => child.id === id);
        }

        getPreviousSibling(child) {
            const index = this.getChildIndex(child);
            return index > 0 ? this.children[index - 1] : null;
        }

        getNextSibling(child) {
            const index = this.getChildIndex(child);
            return index < this.children.length - 1 ? this.children[index + 1] : null;
        }

        getFirstChild() {
            return this.children[0] || null;
        }

        getLastChild() {
            return this.children[this.children.length - 1] || null;
        }

        getChildrenCount() {
            return this.children.length;
        }

        hasChildren() {
            return this.children.length > 0;
        }

        addChild(child) {
            child.parent = this;
            this.children.push(child);
        }

        insertChildAt(child, index) {
            child.parent = this;
            this.children.splice(index, 0, child);
        }

        removeChild(child) {
            const index = this.getChildIndex(child);
            if (index !== -1) {
                this.children.splice(index, 1);
                child.parent = null;
                return true;
            }
            return false;
        }

        isExpanded() {
            return this._expanded;
        }

        toggleExpanded() {
            this._expanded = !this._expanded;
        }


        indent() {
            const parent = this.parent;
            if (!parent) return false;
            
            const currentIndex = parent.getChildIndex(this);
            if (currentIndex === 0) return false;
            
            const previousSibling = parent.children[currentIndex - 1];
            parent.removeChild(this);
            previousSibling.addChild(this);
            
            return true;
        }

        desindent() {
            const parent = this.parent;
            if (!parent) return false;
            // si cette ligne est n'est pas le dernier enfant de son parent, il ne peut pas se déindenter
            if (parent.getLastChild() !== this) return false;
            const grandParent = parent.parent;
            if (!grandParent) return false;
            
            const parentIndex = grandParent.getChildIndex(parent);
            parent.removeChild(this);
            grandParent.insertChildAt(this, parentIndex + 1);
            
            return true;
        }

        amount() {
            if (this.hasChildren()) {
                return this.children.reduce((total, child) => total + child.amount(), 0);
            }
            return this.quantite * this.prix_unitaire;
        }
    }

    class LineManager {
        constructor(lotNom = "Bordereau des prix unitaires", data = []) {
            this.lineMap = {};
            this.rootLine = new Line(null, "Root", lotNom);
            this.indexMap = {}; // Cache des index
            this.cachedFlatList = null; // Cache flatList
            this.cacheValid = false; // Flag de validité
            this.data = data;
            this.dataTable = data ? this.getTableData(data) : [];
        }
        insertChildAt(line, index) { // Insertion d'un enfant à une position index
            // Trouver le parent qui se trouve à la position index dans la liste flatList
            // verfier l'index est valide
            
            const flatList = this.getCachedFlatList();
            
            if (index < 0 || index >= flatList.length) return;
            try {
                const childLine = flatList[index];
                const parentLine = childLine.parent;
                if (!parentLine) return;

                const position= index - this.getIndexById(parentLine.id) - 1;
                parentLine.insertChildAt(line, position);
                this.invalidateCache(); 
            } catch (error) {
                console.error(error);
                return;
            }
            
        }
        
        removeChild(line) { // Suppression d'un enfant
            const parent = line.parent;
            if (!parent) return;
            parent.removeChild(line);
            this.invalidateCache();
        }

        indexOf(line) { // Retourne l'index de la ligne
            const flatList = this.getCachedFlatList();
            return flatList.indexOf(line);
        }

        buildTree(data) {
            this.lineMap = {};
            this.cacheValid = false; 
            // Créer tous les nodes
            data.forEach(row => {
                if (!row || row.id === null || row.id === undefined) return;
                
                let line = new Line(
                    row.id, 
                    row.numero || "",
                    row.designation || "New Line", 
                    row.unite || "", 
                    parseFloat(row.quantite) || 0, 
                    parseFloat(row.prix_unitaire) || 0,
                    null,
                    true // _expanded par défaut pour voir les données
                );
                this.lineMap[row.id] = line;
            });

            // Construire la hiérarchie
            data.forEach(row => {
                if (!row || !this.lineMap[row.id]) return;
                
                const line = this.lineMap[row.id];
                
                if (row.parent_id && this.lineMap[row.parent_id]) {
                    this.lineMap[row.parent_id].addChild(line);
                } else {
                    this.rootLine.addChild(line);
                }
            });
        }
        
        getUpdatedFlatList() {
            const flatList = this.getCachedFlatList();

            return flatList.map(line => ({
                id: line.id,
                parent_id: line.parent ? line.parent.id : null,
                numero: line.numero,
                niveau: line.level(),
                est_titre: line.hasChildren(),
                designation: line.designation,
                unite: line.unite,
                quantite: line.quantite,
                prix_unitaire: line.prix_unitaire,
                montant: line.amount(),
            }));
        }
        buildIndexMap() {
            this.indexMap = {};
            const flatList = this.getCachedFlatList();
            flatList.forEach((line, index) => {
                if (line && line.id) {
                    this.indexMap[line.id] = index;    //(line.id, index);
                }
            });
        }
        // Fonction pour convertir les données en format Handsontable
        getTableData(data) {
            this.buildTree(data);
            const flatList = this.getCachedFlatList();
            return flatList.map(line => ({
                _expanded: line.isExpanded(),
                id: line.id,
                parent_id: line.parent ? line.parent.id : null,
                numero: line.numero,
                niveau: line.level(),
                est_titre: line.hasChildren(),
                designation: line.designation,
                unite: line.unite,
                quantite: line.quantite,
                prix_unitaire: line.prix_unitaire,
                montant: line.amount(),
            }));
        }
        // GETTER optimisé
        getIndexById(id) {
            try {
                return this.indexMap[id];
            } catch (error) {
                return -1;
            }
            
        }
        
        getLineById(id) {
            if (!this.lineMap[id]) return null;
            return this.lineMap[id];
        }

        montantTotal() {
            return this.rootLine.amount();
        }

        getFlatList() {
            const result = [];
            
            const traverse = (line) => {
                result.push(line);

                if (line.children) {
                    line.children.forEach(child => traverse(child));
                }
            };
            
            this.rootLine.children.forEach(traverse);
            return result;
        }
        
        getCachedFlatList() {
            if (!this.cacheValid || !this.cachedFlatList) {
                this.cachedFlatList = this.getFlatList();
                this.cacheValid = true;
            }
            return this.cachedFlatList;
        }

        invalidateCache() {
            this.cacheValid = false;
            this.cachedFlatList = null;
        }
    
        removeLineByIndex(rowIndex) {
            const flatList = this.getCachedFlatList();
            const line = flatList[rowIndex];
            if (line) {
                line.parent.removeChild(line);
                this.invalidateCache();
            }
        }
        
        getLineByIndex(rowIndex) {
            const flatList = this.getCachedFlatList();
            return flatList[rowIndex];
        }
    
        indentLineByIndex(rowIndex) {
            const flatList = this.getCachedFlatList();
            const line = flatList[rowIndex];
            if (line) {
                line.indent();
                this.invalidateCache();
                return true;
            }
            return false;
        }
    
        desindentLineByIndex(rowIndex) {
            const flatList = this.getCachedFlatList();
            const line = flatList[rowIndex];
            if (line) {
                line.desindent();
                this.invalidateCache();
                return true;
            }
            return false;
        }
    }
