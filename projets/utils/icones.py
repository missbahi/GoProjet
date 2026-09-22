from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders

ICONE_DIR = "images/materiels"
EXTENSIONS = {".png", ".svg", ".jpg", ".jpeg", ".webp", ".avif", ".gif"}
EXCLUS = {"default.avif"}  # fichier de fallback, pas un choix utilisateur

_cache = None


def lister_icones_materiel(force=False):
    """Fichiers réellement présents dans static/images/materiels/."""
    global _cache
    if _cache is not None and not force and not settings.DEBUG:
        return _cache

    trouve = finders.find(ICONE_DIR, all=True)
    chemins = [] if not trouve else ([trouve] if isinstance(trouve, str) else trouve)
    noms = set()
    for chemin in chemins:
        dossier = Path(chemin)
        if not dossier.is_dir():
            continue
        for f in dossier.iterdir():
            if f.is_file() and f.suffix.lower() in EXTENSIONS and f.name not in EXCLUS:
                noms.add(f.name)
    _cache = sorted(noms)
    return _cache


def choix_icones():
    return [("", "— Aucune —")] + [
        (n, Path(n).stem.replace("-", " ").replace("_", " ").title())
        for n in lister_icones_materiel()
    ]