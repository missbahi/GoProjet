// avatar_manager.js
class AvatarManager {
    static init() {
        this.setupErrorHandling();
        this.setupPreview();
    }
    
    static setupErrorHandling() {
        // Gestionnaire d'erreur pour toutes les images avatar
        document.querySelectorAll('.avatar-img, img[src*="avatar"]').forEach(img => {
            img.onerror = function() {
                console.warn('Avatar non trouvé, utilisation de la image par défaut:', this.src);
                this.src = '/static/images/default_avatar.png';
                // Empêcher la boucle d'erreur
                this.onerror = null;
            };
            
            // Vérifier si l'image est déjà en erreur
            if (img.complete && img.naturalHeight === 0) {
                img.src = '/static/images/default_avatar.png';
                img.onerror = null;
            }
        });
    }
    
    static setupPreview() {
        // Prévisualisation lors de la sélection d'un fichier
        document.querySelectorAll('input[type="file"][accept="image/*"]').forEach(input => {
            input.addEventListener('change', function(e) {
                const file = e.target.files[0];
                if (file) {
                    const previewId = this.dataset.preview || 'avatarPreview';
                    const preview = document.getElementById(previewId);
                    if (preview) {
                        const reader = new FileReader();
                        reader.onload = function(event) {
                            preview.src = event.target.result;
                        };
                        reader.readAsDataURL(file);
                    }
                }
            });
        });
    }
    
    static refreshAvatars() {
        // Rafraîchir tous les avatars sur la page avec un timestamp
        document.querySelectorAll('.avatar-img, img[src*="avatar"]').forEach(img => {
            const originalSrc = img.src.split('?')[0];
            img.src = originalSrc + '?' + new Date().getTime();
        });
    }
    
    static checkAvatars() {
        // Vérifier que tous les avatars sont valides
        document.querySelectorAll('.avatar-img, img[src*="avatar"]').forEach(img => {
            if (!img.complete || img.naturalHeight === 0) {
                console.warn('Avatar invalide détecté:', img.src);
                img.src = '/static/images/default_avatar.png';
                img.onerror = null;
            }
        });
    }
}

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    AvatarManager.init();
    
    // Vérifier périodiquement les avatars (pour les dynamiquement chargés)
    setInterval(() => AvatarManager.checkAvatars(), 3000);
});

// Écouter les événements de mise à jour
document.body.addEventListener('avatarUpdated', function() {
    AvatarManager.refreshAvatars();
});

// Exposer globalement pour un accès facile
window.AvatarManager = AvatarManager;