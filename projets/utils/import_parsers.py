"""
Utilitaires de parsing pour l'import de données tabulaires
collées depuis un tableur (Excel, LibreOffice, Google Sheets).
"""

import re
from decimal import Decimal, InvalidOperation
from unicodedata import normalize


# Séparateurs acceptés, par ordre de priorité
SEPARATEURS = ['\t', ';', '|']

# En-têtes reconnus (normalisés : minuscules, sans accents)
ENTETES_ATTENDUS = {
    'designation': 'designation',
    'désignation': 'designation',
    'nom': 'designation',
    'type': 'type',
    'type de materiel': 'type',
    'type materiel': 'type',
    'immatriculation': 'immatriculation',
    'immat': 'immatriculation',
    'numero': 'immatriculation',
    'unite': 'unite',
    'unité': 'unite',
    'prix': 'prix',
    'prix unitaire': 'prix',
    'prix_unitaire': 'prix',
    'actif': 'actif',
    'active': 'actif',
    'actif?': 'actif',
}

# Ordre par défaut si pas d'en-tête
ORDRE_PAR_DEFAUT = ['designation', 'type', 'immatriculation', 'unite', 'prix', 'actif']


def _normaliser(texte):
    """Minuscule + suppression des accents et espaces superflus."""
    if texte is None:
        return ''
    texte = str(texte).strip().lower()
    texte = ''.join(
        c for c in normalize('NFD', texte) if not (0x300 <= ord(c) <= 0x36F)
    )
    return texte


def _detecter_separateur(texte):
    """Détecte le séparateur le plus probable sur la première ligne non vide."""
    premiere_ligne = ''
    for ligne in texte.splitlines():
        if ligne.strip():
            premiere_ligne = ligne
            break

    meilleur = None
    meilleur_count = 0
    for sep in SEPARATEURS:
        count = premiere_ligne.count(sep)
        if count > meilleur_count:
            meilleur = sep
            meilleur_count = count

    # Si aucun des séparateurs n'est présent, on tente la virgule
    if meilleur is None and premiere_ligne.count(',') > 0:
        meilleur = ','

    return meilleur or '\t'


def _parser_bool(valeur):
    """Convertit une valeur en booléen. Retourne True par défaut."""
    if valeur is None:
        return True
    v = _normaliser(valeur)
    if v in ('', 'oui', 'yes', 'true', '1', 'actif', 'active', 'vrai'):
        return True
    if v in ('non', 'no', 'false', '0', 'inactif', 'inactive', 'faux'):
        return False
    return True  # Par défaut, actif


def _parser_prix(valeur):
    """Convertit une valeur en Decimal. Retourne None si invalide."""
    if valeur is None:
        return None
    v = str(valeur).strip()
    if not v:
        return None
    # Retire les symboles monétaires et espaces
    v = re.sub(r'[^\d,.\-]', '', v)
    # Gère la virgule comme séparateur décimal
    if ',' in v and '.' in v:
        # Format "1,234.56" → on retire les virgules
        v = v.replace(',', '')
    else:
        v = v.replace(',', '.')
    try:
        return Decimal(v)
    except (InvalidOperation, ValueError):
        return None


def _detecter_entete(premiere_ligne, sep):
    """Détecte si la première ligne est un en-tête et retourne le mapping colonnes."""
    cellules = [c.strip() for c in premiere_ligne.split(sep)]
    mapping = {}
    for idx, cellule in enumerate(cellules):
        cle = _normaliser(cellule)
        if cle in ENTETES_ATTENDUS:
            mapping[ENTETES_ATTENDUS[cle]] = idx

    # En-tête détecté si au moins 2 colonnes reconnues
    if len(mapping) >= 2:
        return mapping
    return None


def parser_import_materiel(texte, has_header=None):
    """
    Parse un texte collé depuis un tableur.

    Retourne un tuple (lignes, warnings) où chaque ligne est un dict :
        {
            'numero': int (1-indexé),
            'designation': str,
            'type': str,
            'immatriculation': str,
            'unite': str,
            'prix': Decimal|None,
            'actif': bool,
        }

    `has_header` : None = auto-détection, True = forcer, False = pas d'en-tête.
    """
    warnings = []
    if not texte or not texte.strip():
        return [], ['Le texte est vide.']

    sep = _detecter_separateur(texte)
    warnings.append(f"Séparateur détecté : {repr(sep)}")

    lignes_brutes = [l for l in texte.splitlines() if l.strip()]
    if not lignes_brutes:
        return [], ['Aucune ligne de données.']

    # Détection de l'en-tête
    premiere = lignes_brutes[0]
    mapping = None
    if has_header is True:
        mapping = _detecter_entete(premiere, sep)
        if not mapping:
            warnings.append(
                "La première ligne a été marquée comme en-tête, "
                "mais aucun nom de colonne reconnu n'a été trouvé. "
                "Utilisation de l'ordre par défaut."
            )
            mapping = {nom: idx for idx, nom in enumerate(ORDRE_PAR_DEFAUT)}
        lignes_donnees = lignes_brutes[1:]
    elif has_header is False:
        mapping = {nom: idx for idx, nom in enumerate(ORDRE_PAR_DEFAUT)}
        lignes_donnees = lignes_brutes
    else:
        # Auto-détection
        mapping = _detecter_entete(premiere, sep)
        if mapping:
            warnings.append("En-tête détecté et interprété.")
            lignes_donnees = lignes_brutes[1:]
        else:
            warnings.append("Pas d'en-tête détecté. Ordre par défaut utilisé.")
            mapping = {nom: idx for idx, nom in enumerate(ORDRE_PAR_DEFAUT)}
            lignes_donnees = lignes_brutes

    resultats = []
    for idx, ligne in enumerate(lignes_donnees, start=1):
        cellules = [c.strip() for c in ligne.split(sep)]

        def get(nom):
            i = mapping.get(nom)
            if i is None or i >= len(cellules):
                return ''
            return cellules[i]

        resultats.append({
            'numero': idx,
            'designation': get('designation'),
            'type': get('type'),
            'immatriculation': get('immatriculation'),
            'unite': get('unite'),
            'prix': _parser_prix(get('prix')),
            'actif': _parser_bool(get('actif')),
            '_brut': ligne,
        })

    return resultats, warnings