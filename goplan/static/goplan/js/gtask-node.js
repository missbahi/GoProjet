/**
 * GTaskNode — Tâche GoPlan.
 * Hérite de TreeNode pour la hiérarchie.
 *
 * Règles métier :
 *   - Un JALON ne peut pas être parent
 *   - Un GROUPE DOIT avoir des enfants (en pratique)
 *   - Une tâche ne peut pas sauter un niveau (géré par indent())
 *   - Le level est calculé à partir du parent
 */
class GTaskNode extends TreeNode {
    constructor({
        id = null,
        numero = '',
        designation = '',
        type_tache = 'TACHE',
        duree = 1,
        date_debut = null,
        date_fin = null,
        contrainte = 'ASAP',
        avancement = 0,
        parent = null,
        expanded = true,
    } = {}) {
        super({ id, numero, designation, parent, expanded });

        this.type_tache = type_tache;   // TACHE | JALON | GROUPE | RECUR
        this.duree = Number(duree);
        this.date_debut = date_debut;
        this.date_fin = date_fin;
        this.contrainte = contrainte;   // ASAP | ALAP | FIXE_DEBUT | FIXE_FIN
        this.avancement = parseFloat(avancement) || 0;
    }

    // ══════════════════════════════════════════════════════════
    // Montant = durée cumulée (feuilles)
    // ══════════════════════════════════════════════════════════
    _computeOwnAmount() {
        if (this.type_tache === 'JALON') return 0;
        return this.duree;
    }

    recalculateSchedule(calendar) {
        this.children.forEach(child => child.recalculateSchedule(calendar));
        if (this.type_tache !== 'GROUPE') return;
        const dated = this.children.filter(child =>
            child.date_debut && child.date_fin && child.date_fin >= child.date_debut
        );
        this.date_debut = dated.length
            ? dated.map(child => child.date_debut).sort()[0] : null;
        this.date_fin = dated.length
            ? dated.map(child => child.date_fin).sort().at(-1) : null;
        this.duree = dated.length
            ? calendar.workingDaysBetween(this.date_debut, this.date_fin) : 0;
    }

    // ══════════════════════════════════════════════════════════
    // Ajout, insertion d'enfant → promotion auto en GROUPE
    // ══════════════════════════════════════════════════════════

    insertChildAt(child, index) {
        if (this.type_tache === 'JALON') {
            throw new Error('Un jalon ne peut pas avoir de sous-tâches.');
        }
        if (this.type_tache === 'RECUR') {
            throw new Error('Une tâche récurrente ne peut pas avoir de sous-tâches.');
        }
        
        const inserted = super.insertChildAt(child, index);

        // ⚡ Promotion : TACHE → GROUPE dès le 1er enfant
        if (inserted && this.children.length > 0) {
            this.type_tache = 'GROUPE';
        }
        return inserted;
    }

    // ══════════════════════════════════════════════════════════
    // Suppression d'enfant → rétrogradation auto en TACHE
    // ══════════════════════════════════════════════════════════
    removeChild(child) {
        if (super.removeChild(child)) {
            // ⚡ Rétrogradation : GROUPE → TACHE si plus d'enfant
            if (this.children.length === 0 && this.type_tache === 'GROUPE') {
                this.type_tache = 'TACHE';
            }
            return true;
        }
        return false;
    }

    // ══════════════════════════════════════════════════════════
    // Validation métier (règle JALON pour indent)
    // ══════════════════════════════════════════════════════════
    _validateIndent(previousSibling) {
        if (previousSibling.type_tache === 'JALON') {
            return 'Un jalon ne peut pas être un groupe parent.';
        }
        if (previousSibling.type_tache === 'RECUR') {
            return 'Une tâche récurrente ne peut pas avoir de sous-tâches.';
        }
        return null;
    }

    // ══════════════════════════════════════════════════════════
    // Sérialisation enrichie
    // ══════════════════════════════════════════════════════════
    toJSON() {
        return {
            ...super.toJSON(),
            type_tache: this.type_tache,
            duree: this.duree,
            date_debut: this.date_debut,
            date_fin: this.date_fin,
            contrainte: this.contrainte,
            avancement: this.avancement,
            duree_totale: this.amount,
        };
    }
}

// ══════════════════════════════════════════════════════════════
// EXPORT GLOBAL
// ══════════════════════════════════════════════════════════════
window.GTaskNode = GTaskNode;