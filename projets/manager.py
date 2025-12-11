# managers.py
# Class Line, LineManager - version python

from projets.models import LigneBordereau


def float_or_zero(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def convert_lot_to_table(lot):
    """Convertit un les donnees d'un model django en données tabulaires"""
    
    lignes = lot.lignes.all()
    table = []
    for ligne in lignes:
        table.append({
            'id': ligne.id,
            'parent_id': ligne.parent.id if ligne.parent else None,
            'numero': ligne.numero,
            'designation': ligne.designation,
            'unite': ligne.unite,
            'quantite': float_or_zero(ligne.quantite),
            'prix_unitaire': float_or_zero(ligne.prix_unitaire),
        })
    return table
    
class Line:
    def __init__(self, id = None, numero = "N°", designation = "Désignation", unite = "U", quantite = 1, pu = 0, parent = None, _expanded = False):
            self.id = id
            self.parent = parent
            self.children = []
            self.numero = numero
            self.designation = designation
            self.unite = unite
            self.quantite = quantite
            self.prix_unitaire = pu
            self._expanded = _expanded
            self.lines_attachement = {}  # Dictionnaire pour stocker les lignes d'attachement
   
    def get_ligne_bordereau(self):
        try:
            ligne_bordereau = LigneBordereau.objects.get(id=self.id)
            return ligne_bordereau
        except LigneBordereau.DoesNotExist:
            return None
   
    def set_line_attachement(self, line_attachement):
        if line_attachement:
            self.lignes_attachement[line_attachement.id] = line_attachement
            return True
        return False
    
    def amount_attachement(self, attachement):
        line_attachement = self.lines_attachement.get(attachement.id)
        if line_attachement:
            if not self.hasChildren():
                return line_attachement.quantite_realisee * self.prix_unitaire
            amount = 0.0
            for child in self.children:
                amount += child.amount_attachement(attachement)
            return amount
        return 0.0
    
    def get_line_attachement(self, attachement_id):
        return self.lignes_attachement.get(attachement_id)
    
    def __str__(self):
        level = self.level()
        esp = "  " * level
        return '|' + esp + f"{self.numero} | {self.designation} | {self. unite} | {self.quantite} | {self.prix_unitaire} | {self.amount()}"
    
    def level(self):
            level = 0
            currentNode = self
            while (currentNode.parent):
                level += 1
                currentNode = currentNode.parent
            
            return level
    
    def forEachChild(self, callback):
            self.children.forEach(callback)
        
    def getChildIndex(self, child):
        try:
            return self.children.index(child)
        except ValueError:
            return -1
        
    def findChildById(self, id):
        if not self.children:
            return None
        for child in self.children:
            if child.id == id:
                return child
        return None        

    def getPreviousSibling(self, child):
        index = self.getChildIndex(child)
        return self.children[index - 1] if index > 0 else None        

    def getNextSibling(self, child):
        index = self.getChildIndex(child)
        return self.children[index + 1]  if index < len(self.children) else None
    
    def getChildren(self):
            return self.children

    def getFirstChild(self):
        return self.children[0] if self.children else None
    
    def getLastChild(self):
        return self.children[len(self.children) - 1] if self.children else None
        
    def getChildrenCount(self):
        return len(self.children) 

    def hasChildren(self):
        return self.getChildrenCount() > 0       

    def addChild(self, child):
        if not child or child is self or child in self.children: return
        child.parent = self
        self.children.append(child)

    def insertChildAt(self, child, index):
        if not child or child is self or child in self.children: return
        if 0 <= index <= len(self.children):
            child.parent = self
            self.children.insert(index, child)

    def removeChild(self, child):
        """Supprime un enfant par référence"""
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            return True
        return False

    def isExpanded(self):
        return self._expanded

    def toggleExpanded(self):
        self._expanded = not self._expanded
        
    def indent(self):
        parent:Line = self.parent
        if not parent: return False
        
        currentIndex = parent.getChildIndex(self)
        if currentIndex == 0: return False
        
        previousSibling:Line = parent.children[currentIndex - 1]
        parent.removeChild(self)
        previousSibling.addChild(self)
        
        return True

    def desindent(self):
        parent:Line = self.parent
        if not parent: return False
        # si cette ligne n'est pas le dernier enfant de son parent, il ne peut pas se déindenter
        if parent.getLastChild() != self: return False
        grandParent:Line = parent.parent
        if not grandParent: return False
        
        parentIndex = grandParent.getChildIndex(parent)
        parent.removeChild(self)
        grandParent.insertChildAt(self, parentIndex + 1)
        
        return True
        
    def amount(self):
        if self.hasChildren():
            return sum(child.amount() for child in self.children)
        return self.quantite * self.prix_unitaire
 
class LineManager:
    def __init__(self, lot_nom="Bordereau des prix unitaires", data=None):
        self.line_map = {}
        self.root_line = Line(None, "Root", lot_nom)
        self.index_map = {}  # Cache des index
        self.cached_flat_list = None  # Cache flatList
        self.cache_valid = False  # Flag de validité
        self.data = data or []
        self.data_table = self.get_table_data() if data else []
    def set_model_data(self, lot):
        """Initialise les données à partir d'un modèle Django"""
        self.lot = lot
        self.data = convert_lot_to_table(lot)
        self.build_tree()
        self.build_index_map()
        self.invalidate_cache()
    def get_attachements_from_model(self):
        """Récupère les attachements associés au lot"""
        if not hasattr(self, 'lot'): return []
        lot = self.lot
        if not lot or not lot.projet: return []
        attachements = lot.projet.attachements.all()
        return attachements
    def insert_child_at(self, line, index):
        """Insertion d'un enfant à une position index"""
        # Trouver le parent qui se trouve à la position index dans la liste flat_list
        # vérifier l'index est valide
        
        flat_list = self.get_cached_flat_list()
        
        if index < 0 or index >= len(flat_list):
            return
        
        try:
            child_line:Line = flat_list[index]
            parent_line:Line = child_line.parent
            if not parent_line:
                return

            position = index - self.get_index_by_id(parent_line.id) - 1
            parent_line.insertChildAt(line, position)
            self.invalidate_cache()
        except Exception as error:
            print(f"Erreur: {error}")
            return
    
    def remove_child(self, line):
        """Suppression d'un enfant"""
        parent:Line = line.parent
        if not parent:
            return
        parent.removeChild(line)
        self.invalidate_cache()
    
    def index_of(self, line):
        """Retourne l'index de la ligne"""
        flat_list = self.get_cached_flat_list()
        return flat_list.index(line) if line in flat_list else -1
    
    def build_tree(self):
        """Construit l'arbre à partir des données"""
        self.cache_valid = False
        if not self.data: return
        attachements = self.get_attachements_from_model()
        
        self.line_map = {}
        # Créer tous les nodes
        for row in self.data:
            if not row or row.get('id') is None:
                continue
            
            line = Line(
                row['id'],
                row.get('numero', ""),
                row.get('designation', "New Line"),
                row.get('unite', ""),
                float(row.get('quantite', 0)) or 0,
                float(row.get('prix_unitaire', 0)) or 0,
                None,
                True  # _expanded par défaut pour voir les données
            )
            line_bordereau = line.get_ligne_bordereau()
            if line_bordereau:
                for attachement in attachements:
                    try:
                        line_attachement = line_bordereau.lignes_attachement.get(attachement=attachement)
                        line.set_line_attachement(line_attachement)
                    except Exception:
                        continue
            self.line_map[row['id']] = line
        
        # Construire la hiérarchie
        for row in self.data:
            if not row or not self.line_map.get(row['id']):
                continue
            
            line:Line = self.line_map[row['id']]
            
            if row.get('parent_id') and self.line_map.get(row['parent_id']):
                parent_line:Line = self.line_map[row['parent_id']]
                parent_line.addChild(line)
            else:
                self.root_line.addChild(line)
    
    def get_updated_flat_list(self):
        """Retourne la liste plate mise à jour"""
        flat_list = self.get_cached_flat_list()
        
        return [{
            'id': line.id,
            'parent_id': line.parent.id if line.parent else None,
            'numero': line.numero,
            'niveau': line.level(),
            'est_titre': line.has_children(),
            'designation': line.designation,
            'unite': line.unite,
            'quantite': line.quantite,
            'prix_unitaire': line.prix_unitaire,
            'montant': line.amount(),
        } for line in flat_list]
    
    def build_index_map(self):
        """Construit la map d'index"""
        self.index_map = {}
        flat_list = self.get_cached_flat_list()
        
        for index, line in enumerate(flat_list):
            if line and line.id:
                self.index_map[line.id] = index
    
    def get_table_data(self):
        """Convertit les données en format tableau"""
        self.build_tree()
        flat_list = self.get_cached_flat_list()

        return [{
            '_expanded': line.isExpanded(),
            'id': line.id,
            'parent_id': line.parent.id if line.parent else None,
            'numero': line.numero,
            'niveau': line.level(),
            'est_titre': line.hasChildren(),
            'designation': line.designation,
            'unite': line.unite,
            'quantite': line.quantite,
            'prix_unitaire': line.prix_unitaire,
            'montant': line.amount(),
        } for line in flat_list]
    
    def get_index_by_id(self, id):
        """GETTER optimisé"""
        try:
            return self.index_map.get(id, -1)
        except Exception:
            return -1
    
    def get_line_by_id(self, id):
        """Retourne une ligne par son ID"""
        return self.line_map.get(id)
    
    def montant_total(self):
        """Retourne le montant total"""
        return self.root_line.amount()
    
    def get_flat_list(self):
        """Retourne la liste plate de toutes les lignes"""
        result = []
        
        def traverse(line):
            result.append(line)
            if line.children:
                for child in line.children:
                    traverse(child)
        
        for child in self.root_line.children:
            traverse(child)
        
        return result
    
    def get_cached_flat_list(self):
        """Retourne la liste plate avec cache"""
        if not self.cache_valid or not self.cached_flat_list:
            self.cached_flat_list = self.get_flat_list()
            self.cache_valid = True
        return self.cached_flat_list
    
    def invalidate_cache(self):
        """Invalide le cache"""
        self.cache_valid = False
        self.cached_flat_list = None
    
    def remove_line_by_index(self, row_index):
        """Supprime une ligne par son index"""
        flat_list = self.get_cached_flat_list()
        if 0 <= row_index < len(flat_list):
            line = flat_list[row_index]
            if line and line.parent:
                line.parent.remove_child(line)
                self.invalidate_cache()
    
    def get_line_by_index(self, row_index):
        """Retourne une ligne par son index"""
        flat_list = self.get_cached_flat_list()
        if 0 <= row_index < len(flat_list):
            return flat_list[row_index]
        return None
    
    def indent_line_by_index(self, row_index):
        """Indente une ligne par son index"""
        flat_list = self.get_cached_flat_list()
        if 0 <= row_index < len(flat_list):
            line = flat_list[row_index]
            if line:
                line.indent()
                self.invalidate_cache()
                return True
        return False
    
    def desindent_line_by_index(self, row_index):
        """Désindente une ligne par son index"""
        flat_list = self.get_cached_flat_list()
        if 0 <= row_index < len(flat_list):
            line = flat_list[row_index]
            if line:
                line.desindent()
                self.invalidate_cache()
                return True
        return False  
    
    def expand_line_by_index(self, row_index):
        """Expand une ligne par son index"""
        flat_list = self.get_cached_flat_list()
        if 0 <= row_index < len(flat_list):
            line = flat_list[row_index]
            if line:
                line.setExpanded(True)
                self.invalidate_cache()
                return True
        return False

class LigneHierarchique:
    def __init__(self, data):
        self.id = data.get('id')
        self.parent_id = data.get('parent_id')
        self.numero = data.get('numero')
        self.designation = data.get('designation') 
        self.unite = data.get('unite')
        self.quantite = data.get('quantite')
        self.prix_unitaire =data.get('prix_unitaire')
        self.montant = data.get('montant', 0)
        self.children = []
        self.parent = None
        self.collapsed = True
    def __str__(self):
        return f"(id={self.id}, {self.parent_id}, {self.designation},{self.quantite}, {self.prix_unitaire}, {self.montant})"
    def build_tree_from_data(self, data, parent=None):
        self.children.clear()
        self.parent = None
        self.collapsed = False
        self.parent = parent
        # 1. Créer tous les objets
        lines = {}
        for line in data:
            try:
                child = LigneHierarchique(line)
                lines[child.id] = child
            except KeyError as e:
                print(f"Erreur lors de la création de l'objet LigneHierarchique: {e}")
                continue
        
        # 2. Construire la hiérarchie
        for line in lines.values():
            # print(line)
            if line.parent_id:
                parent = lines.get(line.parent_id)
                if parent: 
                    parent.ajouter_enfant(line)
                else: # ajouter cette ligne à la racine
                    self.ajouter_enfant(line)
            else:
                self.ajouter_enfant(line)
        
        return lines
    
    def ajouter_enfant(self, enfant):
        """Ajoute un enfant et met à jour son niveau"""
        enfant.parent = self
        self.children.append(enfant)
    
    def collapse(self, all=True):
        if self.parent: 
            self.collapsed = True
        else:
            self.collapsed = False
        
        if all:    
            for enfant in self.children:
                enfant.collapse(all)
    @property
    def has_children(self):
        return len(self.children) > 0
    
    @property
    def level(self):
        level = 0
        currentNode = self
        while (currentNode.parent):
            level += 1
            currentNode = currentNode.parent
        
        return level
    
    def collecter_tous_enfants(self):
        """Collecte tous les enfants et petits-enfants de manière récursive"""
        result = [self]
        for enfant in self.children:
            result.extend(enfant.collecter_tous_enfants())
        return result
    
    def collecter_ids_enfants(self):
        """Collecte tous les IDs des enfants (utile pour suppression)"""
        ids = [self.id]
        for enfant in self.children:
            ids.extend(enfant.collecter_ids_enfants())
        return ids
    
    def est_parent(self):
        """Vérifie si la ligne a des enfants"""
        return self.has_children
    
    def amount(self):
        if self.has_children:
            return sum(child.amount() for child in self.children)
        return self.montant
    
    def export_to_table(self):
        """
        Exporte la ligne et ses enfants sous forme de tableau plat
        avec les niveaux hiérarchiques préservés
        """
        result = []
        
        # Ajouter la ligne actuelle
        result.append({
            'id': self.id,
            'parent_id': self.parent_id,
            'numero': self.numero,
            'designation': self.designation,
            'unite': self.unite,
            'quantite': self.quantite,
            'prix_unitaire': self.prix_unitaire,
            'montant': self.amount(),
            'level': self.level,
            'has_children': self.has_children,
            'is_parent': self.est_parent(),
            'children_count': len(self.children),
            'children_ids': [child.id for child in self.children]
        })
        
        # Ajouter récursivement les enfants
        for enfant in self.children:
            result.extend(enfant.export_to_table())
        
        return result
    
    def export_to_json(self):
        """Exporte en format JSON pour le template"""
        return {
            'id': self.id,
            'parent_id': self.parent_id,
            'numero': self.numero,
            'designation': self.designation,
            'unite': self.unite,
            'quantite': self.quantite,
            'prix_unitaire': self.prix_unitaire,
            'montant': self.amount(),
            'level': self.level,
            'has_children': self.has_children,
            'is_parent': self.est_parent(),
            'children': [child.export_to_json() for child in self.children]
        }
    
    def trouver_par_id(self, ligne_id):
        """Trouve une ligne par son ID dans l'arbre"""
        if self.id == ligne_id:
            return self
        
        for enfant in self.children:
            result = enfant.trouver_par_id(ligne_id)
            if result:
                return result
        
        return None
    
#     # Fonction utilitaire pour construire la hiérarchie
# def construire_hierarchie(lignes_data):
    # """
    # Convertit une liste plate de lignes en structure hiérarchique
    
    # Args:
    #     lignes_data: Liste de dictionnaires avec id et parent_id
    
    # Returns:
    #     Tuple: (racines, dict_reference)
    # """
    
    # lignes_objects = {}
    # racines = []
    
    # # Vérifier si la liste est vide
    # if not lignes_data:
    #     return racines, lignes_objects
    
    # # 1. Créer tous les objets
    # for ligne_data in lignes_data:
    #     try:
    #         ligne_obj = LigneHierarchique(ligne_data)
    #         lignes_objects[ligne_obj.id] = ligne_obj
    #     except KeyError as e:
    #         print(f"Erreur lors de la création de l'objet LigneHierarchique: {e}")
    #         continue
    
    # # 2. Construire la hiérarchie
    # for ligne_obj in list(lignes_objects.values()):
    #     if ligne_obj.parent_id:
    #         parent = lignes_objects.get(ligne_obj.parent_id)
    #         if parent:
    #             parent.ajouter_enfant(ligne_obj)
    #         else:
    #             # Parent non trouvé, traiter comme racine
    #             racines.append(ligne_obj)
    #     else:
    #         racines.append(ligne_obj)
    
    # # 3. Trier les racines par ID
    # # racines.sort(key=lambda x: x.id)
    
    # # 4. Trier les enfants récursivement
    # # def trier_enfants(noeud):
    # #     noeud.children.sort(key=lambda x: x.id)
    # #     for enfant in noeud.children:
    # #         trier_enfants(enfant)
    
    # # for racine in racines:
    # #     trier_enfants(racine)
    
    # # 5. collapse les lignes avec montant zéro
    # for racine in racines:
    #     if racine.amount() == 0:
    #         racine.collapse()
    # for ligne in lignes_objects.values():
    #     ligne.montant = ligne.amount()
    #     # if ligne.montant == 0:
    #     #     ligne.collapsed = True

    # return racines, lignes_objects