/**
 * TreeNode — Classe générique pour structures hiérarchiques.
 *
 * Utilisée par :
 *   - GoPlan (GTaskNode)
 *   - Bordereau des prix (Line)
 *   - Autres apps GoSuite
 *
 * Fournit :
 *   - Hiérarchie (parent/enfants)
 *   - Indent/Desindent
 *   - Siblings
 *   - Mouvement (up/down)
 *   - Cache niveau et montant
 *   - Expansion/Collapse
 */
class TreeNode {
    constructor({
        id = null,
        numero = '',
        designation = '',
        parent = null,
        expanded = true,
    } = {}) {
        this.id = id || this._generateId();
        this.numero = numero;
        this.designation = designation;
        this.parent = parent;
        this.children = [];
        this.expanded = expanded;

        // Caches
        this._cachedLevel = null;
        this._cachedAmount = null;
    }

    _generateId() {
        return `node_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
    }

    // ══════════════════════════════════════════════════════════
    // Propriétés dérivées
    // ══════════════════════════════════════════════════════════
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
        return this._computeOwnAmount();
    }

    _computeOwnAmount() {
        return 0;   // à surcharger
    }

    // ══════════════════════════════════════════════════════════
    // Cache
    // ══════════════════════════════════════════════════════════
    invalidateCache() {
        this._cachedAmount = null;
        this._cachedLevel = null;
        this.invalidateChildrenLevel();
        if (this.parent) this.parent.invalidateAmountCache();
    }

    invalidateChildrenLevel() {
        this.children.forEach(child => {
            child._cachedLevel = null;
            child.invalidateChildrenLevel();
        });
    }

    invalidateAmountCache() {
        this._cachedAmount = null;
        if (this.parent) this.parent.invalidateAmountCache();
    }

    // ══════════════════════════════════════════════════════════
    // Navigation
    // ══════════════════════════════════════════════════════════
    getChildIndex(child) {
        return this.children.indexOf(child);
    }

    getIndex() {
        if (!this.parent) return -1;
        return this.parent.getChildIndex(this);
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

    // ══════════════════════════════════════════════════════════
    // Manipulation
    // ══════════════════════════════════════════════════════════
    addChild(child) {
        if (child?.parent === this && this.children.includes(child)) return true;
        return this.insertChildAt(child, this.children.length);
    }

    insertChildAt(child, index) {
        if (!child || !(child instanceof TreeNode)) return false;

        // 1. Auto-ajout interdit
        if (child === this) {
            console.warn('TreeNode.insertChildAt : auto-ajout interdit.');
            return false;
        }

        // 2. Cycle : vérifier si `child` est un ancêtre de `this`
        let current = this;
        while (current) {
            if (current === child) {
                console.warn('TreeNode.insertChildAt : cycle détecté.');
                return false;
            }
            current = current.parent;
        }

        // 3. Retirer de l'ancien parent si présent
        if (child.parent) child.parent.removeChild(child);

        // 4. Borner l'index
        const safeIndex = Math.max(0, Math.min(index, this.children.length));

        // 5. Insérer
        child.parent = this;
        this.children.splice(safeIndex, 0, child);
        child.invalidateCache();
        this.invalidateCache();
        return true;
    }

    removeChild(child) {
        const index = this.children.indexOf(child);
        if (index !== -1) {
            this.children.splice(index, 1);
            child.parent = null;
            child.invalidateCache();
            this.invalidateCache();
            return true;
        }
        return false;
    }

    moveChild(child, newIndex) {
        const currentIndex = this.getChildIndex(child);
        if (currentIndex === -1) return false;
        this.children.splice(currentIndex, 1);
        this.children.splice(newIndex, 0, child);
        this.invalidateCache();
        return true;
    }

    moveChildUp(child) {
        const index = this.getChildIndex(child);
        if (index > 0) return this.moveChild(child, index - 1);
        return false;
    }

    moveChildDown(child) {
        const index = this.getChildIndex(child);
        if (index !== -1 && index < this.children.length - 1) {
            return this.moveChild(child, index + 1);
        }
        return false;
    }

    canMoveUp() {
        const index = this.getIndex();
        return index > 0;
    }

    canMoveDown() {
        const index = this.getIndex();
        if (index === -1) return false;
        return index < this.parent.children.length - 1;
    }

    moveUp() {
        if (!this.parent) return false;
        return this.parent.moveChildUp(this);
    }

    moveDown() {
        if (!this.parent) return false;
        return this.parent.moveChildDown(this);
    }

    // ══════════════════════════════════════════════════════════
    // Indent / Desindent
    // ══════════════════════════════════════════════════════════
    _validateIndent(previousSibling) {
        return null;   // Aucune contrainte par défaut, à surcharger dans les sous-classes si nécessaire
    }

    _validateDesindent() {
        return null;   // Aucune contrainte par défaut, à surcharger dans les sous-classes si nécessaire
    }

    indent() {
        const previousSibling = this.getPreviousSibling();
        if (!previousSibling) return false;

        // Validation
        const error = this._validateIndent(previousSibling);
        if (error) return false;

        const parent = this.parent;
        if (!parent) return false;

        return previousSibling.addChild(this);
    }

    canIndent() {
        const previousSibling = this.getPreviousSibling();
        if (!previousSibling) return false;
        const error = this._validateIndent(previousSibling);
        return !error;
    }

    canDesindent() {
        const parent = this.parent;
        if (!parent || !parent.parent) return false;
        const error = this._validateDesindent();
        return !error;
    }

    desindent() {
        const parent = this.parent;
        if (!parent || !parent.parent) return false;

        const error = this._validateDesindent();
        if (error) return false;

        const grandParent = parent.parent;
        const parentIndex = grandParent.getChildIndex(parent);

        return grandParent.insertChildAt(this, parentIndex + 1);
    }

    // ══════════════════════════════════════════════════════════
    // Descendants
    // ══════════════════════════════════════════════════════════
    get descendantIds() {
        const ids = [];
        const traverse = (node) => {
            node.children.forEach(child => {
                ids.push(child.id);
                traverse(child);
            });
        };
        traverse(this);
        return ids;
    }

    get descendants() {
        const nodes = [];
        const traverse = (node) => {
            node.children.forEach(child => {
                nodes.push(child);
                traverse(child);
            });
        };
        traverse(this);
        return nodes;
    }

    // ══════════════════════════════════════════════════════════
    // Expansion
    // ══════════════════════════════════════════════════════════
    toggleExpanded() {
        if (this.hasChildren) {
            this.expanded = !this.expanded;
            return true;
        }
        return false;
    }

    // ══════════════════════════════════════════════════════════
    // Sérialisation
    // ══════════════════════════════════════════════════════════
    toJSON() {
        return {
            id: this.id,
            parent_id: this.parent ? this.parent.id : null,
            numero: this.numero,
            designation: this.designation,
            level: this.level,
            hasChildren: this.hasChildren,
            expanded: this.expanded,
        };
    }
}

// ══════════════════════════════════════════════════════════════
// EXPORT GLOBAL
// ══════════════════════════════════════════════════════════════
window.TreeNode = TreeNode;