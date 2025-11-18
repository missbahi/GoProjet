// Prévisualisation avatar
document.getElementById('avatarInput')?.addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(event) {
            document.getElementById('avatarPreview').src = event.target.result;
        };
        reader.readAsDataURL(file);
    }
});
document.body.addEventListener('profileUpdated', function() {
    // Actualiser la prévisualisation avatar
    htmx.trigger('#avatarPreview', 'load');
});
// Gestion des avatars
class AvatarManager {
    static init() {
        this.setupPreview();
        this.setupUpload();
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
    
    static setupUpload() {
        // Gestionnaire d'erreur pour les images
        document.querySelectorAll('.avatar-img').forEach(img => {
            img.onerror = function() {
                this.src = '/static/images/default_avatar.png';
            };
        });
    }
    
    static refreshAvatars() {
        // Rafraîchir tous les avatars sur la page
        document.querySelectorAll('.avatar-img').forEach(img => {
            const originalSrc = img.src.split('?')[0];
            img.src = originalSrc + '?' + Date.now();
        });
    }
}

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    AvatarManager.init();
});

// Écouter les événements de mise à jour
document.body.addEventListener('avatarUpdated', function() {
    AvatarManager.refreshAvatars();
});