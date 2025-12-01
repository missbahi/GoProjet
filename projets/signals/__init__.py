"""
Importe tous les signaux pour les connecter automatiquement.
L'ordre d'import peut être important si des signaux dépendent d'autres.
"""

# Import de base pour éviter les imports circulaires
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Option 1: Importer tous les handlers
from .notifications import *
from .files_handler import *
from .tache_notifications import *
from .tache_echeances import *
from .validation_notifications import *


