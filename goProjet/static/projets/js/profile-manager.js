/**
 * Profile Manager — Gestion centralisée du profil utilisateur
 * - Prévisualisation avatar
 * - Upload avatar
 * - Rafraîchissement des avatars (navbar, topbar, modals)
 * - Fallback image cassée
 * - Gestion des événements HTMX (profileUpdated, avatarUpdated, closeModal, showMessage)
 */
(function() {
    'use strict';

    // ⚡ Chemin cohérent avec Django : Profile.avatar_url
    const DEFAULT_AVATAR = '/static/images/default.png';
    const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB

    // ============================================================
    // UTILITAIRES
    // ============================================================

    /**
     * Rafraîchit une image en changeant son URL (cache-busting)
     */
    function refreshImage(img) {
        if (!img) return;
        const src = img.src.split('?')[0];
        img.src = src + '?t=' + Date.now();
    }

    /**
     * Rafraîchit TOUS les avatars de la page
     */
    function refreshAllAvatars() {
        document.querySelectorAll(
            '.avatar-img, #navbar-avatar, #avatarPreview, #avatar-preview'
        ).forEach(refreshImage);
    }

    /**
     * Fallback si l'image ne charge pas
     */
    function setFallback(img) {
        if (!img) return;
        img.onerror = null;
        img.src = DEFAULT_AVATAR;
    }

    // ============================================================
    // PRÉVISUALISATION AVATAR
    // ============================================================
    function initPreview() {
        document.addEventListener('change', function(e) {
            const input = e.target.closest('input[type="file"][accept*="image"]');
            if (!input) return;

            const file = input.files && input.files[0];
            const submitBtn = document.getElementById('submitAvatarBtn');

            if (!file) {
                if (submitBtn) submitBtn.classList.add('hidden');
                return;
            }

            // Vérifier la taille
            if (file.size > MAX_FILE_SIZE) {
                const msg = `L'image dépasse ${MAX_FILE_SIZE / 1024 / 1024} Mo.`;
                if (typeof window.showNotification === 'function') {
                    window.showNotification(msg, 'error');
                } else {
                    alert(msg);
                }
                input.value = '';
                if (submitBtn) submitBtn.classList.add('hidden');
                return;
            }

            // Prévisualisation
            const previewId = input.dataset.preview || 'avatarPreview';
            const preview =
                document.getElementById(previewId) ||
                document.getElementById('avatar-preview');
            if (!preview) return;

            const reader = new FileReader();
            reader.onload = function(evt) {
                preview.src = evt.target.result;
                preview.classList.add('ring-2', 'ring-green-400');
                setTimeout(() => preview.classList.remove('ring-2', 'ring-green-400'), 1000);
                if (submitBtn) submitBtn.classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        });
    }

    // ============================================================
    // GESTION DES ERREURS D'IMAGES
    // ============================================================
    function initImageFallback() {
        // ⚡ NE PAS tester complete/naturalHeight au chargement :
        // au DOMContentLoaded, l'image R2 n'a pas encore eu le temps de charger,
        // on forcerait un fallback avant même que l'image ne soit demandée.
        // ⚡ On se contente de BRANCHER onerror (déclenché uniquement en cas d'échec réel).
        document.querySelectorAll(
            '.avatar-img, #navbar-avatar, #avatarPreview, #avatar-preview'
        ).forEach(img => {
            img.onerror = function() { setFallback(this); };
        });

        // Fallback pour les images ajoutées dynamiquement (modals HTMX)
        document.addEventListener('error', function(e) {
            const img = e.target;
            if (img.tagName === 'IMG' && img.id && img.id.toLowerCase().includes('avatar')) {
                setFallback(img);
            }
        }, true);
    }

    // ============================================================
    // GESTION DES ÉVÉNEMENTS HTMX
    // ============================================================
    function initHtmxEvents() {
        // Après un upload d'avatar réussi
        document.body.addEventListener('avatarUpdated', function() {
            refreshAllAvatars();
            closeNestedModals();
        });

        // Après une mise à jour de profil
        document.body.addEventListener('profileUpdated', function() {
            const preview =
                document.getElementById('avatarPreview') ||
                document.getElementById('avatar-preview');
            if (preview) refreshImage(preview);
            refreshAllAvatars();
        });

        // Fermer le modal après un succès
        document.body.addEventListener('closeModal', function() {
            const container = document.getElementById('modals-container');
            if (container) container.innerHTML = '';
            document.body.classList.remove('overflow-hidden');
        });

        // Afficher un message (toast)
        document.body.addEventListener('showMessage', function(e) {
            const detail = e.detail || {};
            const message = detail.value || detail.message || detail;
            const type = detail.type || detail.messageType || 'info';

            if (typeof window.showNotification === 'function') {
                window.showNotification(message, type);
            } else {
                console.log(`[${type.toUpperCase()}] ${message}`);
            }
        });
    }

    /**
     * Ferme les modals imbriqués (upload avatar, password)
     * mais garde le modal profil ouvert.
     */
    function closeNestedModals() {
        const nested = document.getElementById('modals-nested-container');
        if (nested) nested.innerHTML = '';
    }

    // ============================================================
    // NETTOYAGE DES MODALS (au clic sur overlay ou ESC)
    // ============================================================
    function initModalCleanup() {
        document.addEventListener('keydown', function(e) {
            if (e.key !== 'Escape') return;
            const nested = document.getElementById('modals-nested-container');
            const main = document.getElementById('modals-container');

            if (nested && nested.innerHTML.trim() !== '') {
                nested.innerHTML = '';
            } else if (main && main.innerHTML.trim() !== '') {
                main.innerHTML = '';
                document.body.classList.remove('overflow-hidden');
            }
        });
    }

    // ============================================================
    // INITIALISATION
    // ============================================================
    function init() {
        initPreview();
        initImageFallback();
        initHtmxEvents();
        initModalCleanup();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Exposer pour usage externe
    window.ProfileManager = {
        refreshAllAvatars: refreshAllAvatars,
        refreshImage: refreshImage,
    };
})();