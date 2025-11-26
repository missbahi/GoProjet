from django.conf import settings
from projets.models import Attachement

def vider_fichiers_selon_stockage():
    """
    Vide les fichiers selon le type de stockage actuel
    """
    USE_CLOUDINARY = getattr(settings, 'USE_CLOUDINARY', False)
    
    if USE_CLOUDINARY:
        print("📁 Mode: Cloudinary (fichier = None)")
        # Pour CloudinaryField, utiliser None
        attachements_avec_fichier = Attachement.objects.exclude(fichier__isnull=True)
        for att in attachements_avec_fichier:
            att.fichier = None
            att.save()
            print(f"✅ {att.numero}: fichier = None")
            
    else:
        print("📁 Mode: Local (fichier = '')")
        # Pour FileField, utiliser une chaîne vide
        attachements_avec_fichier = Attachement.objects.exclude(fichier__isnull=True).exclude(fichier='')
        for att in attachements_avec_fichier:
            att.fichier = ''
            att.save()
            print(f"✅ {att.numero}: fichier = ''")
    
    print("🎉 Tous les fichiers ont été vidés")

vider_fichiers_selon_stockage()