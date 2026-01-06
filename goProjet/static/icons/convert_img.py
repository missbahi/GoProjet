
from PIL import Image, ImageDraw
import os

# 1. Créer le dossier


# 2. VOTRE ICÔNE - Modifiez ce chemin
GoIcon = "GoIcon.png"  # ← MODIFIEZ ICI

try:
    # 3. Redimensionner votre icône existante
    img = Image.open(GoIcon)
    
    # 192x192 pour l'écran d'accueil
    img.resize((192, 192)).save('icon-192x192.png')
    
    # 512x512 pour les splash screens
    img.resize((512, 512)).save('icon-512x512.png')
    
    print("✅ Icônes créées à partir de logo existant !")
    print("📁 Dossier: goProjet/static/icons/")
    
except FileNotFoundError:
    print("⚠️  Icône non trouvée. Création par défaut...")
    
    # Créer une icône par défaut
    for size, name in [(192, 'icon-192x192.png'), (512, 'icon-512x512.png')]:
        img = Image.new('RGB', (size, size), (10, 3, 2))  # #0A0302
        draw = ImageDraw.Draw(img)
        
        # Cercle blanc
        margin = size // 10
        draw.ellipse([margin, margin, size-margin, size-margin], 
                     fill=(255, 255, 255))
        
        # Texte
        draw.text((size//2, size//2), "GP", fill=(10, 3, 2), 
                  anchor="mm", font_size=size//4)
        
        img.save(f'goProjet/static/icons/{name}')
    
    print("✅ Icônes par défaut créées.")