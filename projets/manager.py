# managers.py
from projets.models import Line, LineBPU


class BordereauTreeManager:
    def __init__(self, lot):
        self.lot = lot
        self.root:Line = None
        self.nodes = {}
        self.build_tree()
    def indent_node(self, node_id)->bool:
        """Indente un node dans l'arbre. Retourne True si l'indentation a fonctionné."""
        node = self.nodes.get(node_id)
        if node:
            # Trouver l'objet line du node
            line:Line = self.root.find_by_id(node_id)
            if line:
                if line.indent():
                    self.build_tree()
                    return True
        return False
    def outdent_node(self, node_id)->bool:
        """Outdent un node dans l'arbre. Retourne True si l'outdent a fonctionné."""
        node = self.nodes.get(node_id)
        if node:
            # Trouver l'objet line du node
            line:Line = self.root.find_by_id(node_id)
            if line:
                if line.outdent():
                    self.build_tree()
                    return True
        return False
    def get_root(self):
        return self.root
    def set_root(self, lot):
        """
        Mise à jour de l'arbre hiérarchique.
        Args : lot (Lot): Nouveau lot.
        Returns : nodes (dict): Dictionnaire des nodes
        """
        self.root = None
        self.lot = lot
        self.build_tree()
        return self.nodes
    def build_tree(self):
        """Construit l'arbre hiérarchique"""
        self.root = Line(numero="Root", designation=self.lot.nom)
        lignes_dict = {}
        
        # Créer les nodes
        for ligne in self.lot.lignes.all():
            lignes_dict[ligne.id] = LineBPU(
                id=ligne.id,
                numero=ligne.numero,
                designation=ligne.designation,
                unite=ligne.unite,
                quantite=ligne.quantite,
                pu=ligne.prix_unitaire,
            )
        
        # Établir les relations
        for ligne in self.lot.lignes.all():
            line_instance = lignes_dict[ligne.id]
            if ligne.parent_id:
                parent_instance = lignes_dict.get(ligne.parent_id)
                if parent_instance:
                    parent_instance.add_child(line_instance)
            else:
                self.root.add_child(line_instance)
            
            self.nodes[ligne.id] = line_instance
    
    def toggle_node(self, node_id, expanded):
        """Bascule l'état d'un node"""
        node = self.nodes.get(node_id)
        if node:
            node._expanded = expanded
            return True
        return False
    
    def get_children_ids(self, node_id):
        """Retourne les IDs des enfants directs"""
        node = self.nodes.get(node_id)
        if node and node.children:
            return [child.id for child in node.children]
        return []
    
    def to_json_data(self):
        """Convertit l'arbre en format pour Handsontable"""
        return [
            {
                'id': ligne.id,
                'numero': ligne.numero,
                'designation': ligne.designation,
                'unite': ligne.unite,
                'quantite': float(ligne.quantite),
                'prix_unitaire': float(ligne.pu),
                'montant': float(ligne.amount()),
                'niveau': ligne.level(),
                'est_titre': ligne.has_children(),
                'parent_id': ligne.parent.id if ligne.parent else None,
                '_expanded': getattr(ligne, '_expanded', True)
            }
            for ligne in self.root.get_children()
        ]