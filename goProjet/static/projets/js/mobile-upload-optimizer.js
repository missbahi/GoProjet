// static/js/mobile-upload-optimizer.js
/**
 * MOBILE UPLOAD OPTIMIZER v2.0
 * Optimise automatiquement tous les inputs file pour mobile
 * Compatible avec tous les modèles Django
 */

(function() {
    'use strict';
    
    // ============================================
    // CONFIGURATION
    // ============================================
    const CONFIG = {
        debug: true,  // Mettre à false en production
        acceptTypes: 'image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png',
        maxSizeMB: 10,
        enableCamera: true,
        enableGallery: true,
        showPreview: true,
        addHelperText: true
    };
    
    // ============================================
    // UTILITAIRES
    // ============================================
    const Utils = {
        // Détection mobile
        isMobile: function() {
            const ua = navigator.userAgent.toLowerCase();
            return /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini|mobile/i.test(ua);
        },
        
        // Détection iOS
        isIOS: function() {
            const usingSmallScreen = window.matchMedia('only screen and (max-width: 640px)').matches;
            const usingSmartphone = /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
            // console.log('using small screens:', usingSmallScreen);
            // console.log('using smart phones:', usingSmartphone);
            return usingSmallScreen || usingSmartphone;
        },
        
        // Détection Android
        isAndroid: function() {
            return /android/i.test(navigator.userAgent);
        },
        
        // Formatage taille fichier
        formatFileSize: function(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        },
        
        // Générer un ID unique
        generateId: function(prefix = 'mobile') {
            return prefix + '-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        },
        
        // Logger
        log: function(message, type = 'info') {
            if (!CONFIG.debug) return;
            const styles = {
                info: 'color: #3b82f6; font-weight: bold;',
                success: 'color: #10b981; font-weight: bold;',
                warning: 'color: #f59e0b; font-weight: bold;',
                error: 'color: #ef4444; font-weight: bold;'
            };
            console.log(`%c📱 MobileUpload: ${message}`, styles[type] || styles.info);
        }
    };
    
    // ============================================
    // CLASS PRINCIPALE
    // ============================================
    class MobileUploadOptimizer {
        constructor() {
            this.initialized = false;
            this.optimizedInputs = new Set();
            this.filePreviews = new Map();
            
            // Icônes par type de fichier
            this.fileIcons = {
                'image': '📷',
                'video': '🎥',
                'pdf': '📄',
                'word': '📝',
                'excel': '📊',
                'default': '📎'
            };
        }
        
        // Initialisation
        init() {
            if (!Utils.isMobile()) {
                Utils.log('Appareil non mobile - optimisation désactivée', 'warning');
                return;
            }
            
            if (this.initialized) return;
            
            Utils.log('Initialisation Mobile Upload Optimizer...', 'info');
            
            // 1. Optimiser les inputs existants
            this.optimizeExistingInputs();
            
            // 2. Observer les nouveaux inputs
            this.setupMutationObserver();
            
            // 3. Ajouter les styles dynamiques
            this.injectDynamicStyles();
            
            // 4. Événements globaux
            this.setupGlobalEvents();
            
            this.initialized = true;
            Utils.log('Optimisation mobile activée avec succès!', 'success');
        }
        
        // Optimiser tous les inputs file existants
        optimizeExistingInputs() {
            const fileInputs = document.querySelectorAll('input[type="file"]');
            
            Utils.log(`Trouvé ${fileInputs.length} input(s) file à optimiser`, 'info');
            
            fileInputs.forEach(input => {
                this.optimizeFileInput(input);
            });
        }
        
        // Optimiser un input file spécifique
        optimizeFileInput(input) {
            // Éviter la double optimisation
            if (this.optimizedInputs.has(input) || input.dataset.mobileOptimized) {
                return;
            }
            
            const inputId = input.id || Utils.generateId('file-input');
            if (!input.id) input.id = inputId;
            
            // Marquer comme optimisé
            input.dataset.mobileOptimized = 'true';
            this.optimizedInputs.add(input);
            
            // 1. Ajouter les attributs essentiels
            this.addMobileAttributes(input);
            
            // 2. Ajouter le texte d'aide
            if (CONFIG.addHelperText) {
                this.addHelperText(input);
            }
            
            // 3. Ajouter les boutons d'action (optionnel)
            if (CONFIG.enableCamera || CONFIG.enableGallery) {
                this.addActionButtons(input);
            }
            
            // 4. Gestion des événements
            this.setupInputEvents(input);
            
            Utils.log(`Input optimisé: ${input.name || input.id}`, 'success');
        }
        
        // Ajouter les attributs mobile
        addMobileAttributes(input) {
            // Attribut capture (essentiel pour iOS/Android)
            input.setAttribute('capture', 'environment');
            
            // Types acceptés
            if (!input.hasAttribute('accept') || input.getAttribute('accept') === '') {
                input.setAttribute('accept', CONFIG.acceptTypes);
            }
            
            // Classes CSS
            input.classList.add('mobile-optimized-input');
            
            // Attributs ARIA pour accessibilité
            input.setAttribute('aria-label', input.getAttribute('aria-label') || 'Télécharger un fichier depuis votre appareil');
            
            // Data attributes
            input.dataset.mobilePlatform = Utils.isIOS() ? 'ios' : Utils.isAndroid() ? 'android' : 'other';
            input.dataset.optimizedAt = new Date().toISOString();
        }
        
        // Ajouter le texte d'aide
        addHelperText(input) {
            const parent = input.parentElement;
            if (!parent) return;
            
            // Vérifier si l'aide existe déjà
            if (parent.querySelector('.mobile-upload-hint')) return;
            
            const hint = document.createElement('div');
            hint.className = 'mobile-upload-hint';
            
            const icon = Utils.isIOS() ? '📱' : '📲';
            const text = Utils.isIOS() 
                ? 'Appuyez pour utiliser la caméra ou la galerie' 
                : 'Utilisez la caméra, la galerie ou vos fichiers';
            
            hint.innerHTML = `
                <i class="fas fa-info-circle"></i>
                <span>${icon} ${text}</span>
            `;// <small>Max: ${CONFIG.maxSizeMB}MB • ${CONFIG.acceptTypes.split(',').length} formats supportés</small>
            
            // Insérer après l'input
            input.insertAdjacentElement('afterend', hint);
        }
        
        // Ajouter les boutons d'action (alternative à l'input)
        addActionButtons(input) {
            // Masquer l'input original
            input.style.display = 'none';
            
            const container = document.createElement('div');
            container.className = 'mobile-action-buttons';
            
            if (CONFIG.enableCamera) {
                const cameraBtn = document.createElement('button');
                cameraBtn.type = 'button';
                cameraBtn.className = 'mobile-camera-btn';
                cameraBtn.innerHTML = '<i class="fas fa-camera"></i> Prendre une photo';
                cameraBtn.onclick = () => this.triggerCamera(input);
                container.appendChild(cameraBtn);
            }
            
            if (CONFIG.enableGallery) {
                const galleryBtn = document.createElement('button');
                galleryBtn.type = 'button';
                galleryBtn.className = 'mobile-gallery-btn';
                galleryBtn.innerHTML = '<i class="fas fa-images"></i> Choisir un fichier';
                galleryBtn.onclick = () => this.triggerGallery(input);
                container.appendChild(galleryBtn);
            }
            
            // Insérer avant l'input
            input.parentNode.insertBefore(container, input);
        }
        
        // Déclencher la caméra
        triggerCamera(input) {
            Utils.log('Déclenchement caméra', 'info');
            input.setAttribute('capture', 'environment');
            input.click();
        }
        
        // Déclencher la galerie
        triggerGallery(input) {
            Utils.log('Déclenchement galerie', 'info');
            input.removeAttribute('capture');
            input.click();
        }
        
        // Configurer les événements de l'input
        setupInputEvents(input) {
            // Prévisualisation du fichier
            input.addEventListener('change', (e) => {
                this.handleFileSelect(e.target);
            });
            
            // Validation taille
            input.addEventListener('change', (e) => {
                this.validateFileSize(e.target);
            });
            
            // Focus/Blur pour UI
            input.addEventListener('focus', () => {
                input.classList.add('mobile-input-focused');
            });
            
            input.addEventListener('blur', () => {
                input.classList.remove('mobile-input-focused');
            });
        }
        
        // Gérer la sélection de fichier
        handleFileSelect(input) {
            if (!input.files || input.files.length === 0) return;
            
            const file = input.files[0];
            Utils.log(`Fichier sélectionné: ${file.name} (${Utils.formatFileSize(file.size)})`, 'info');
            
            // Validation
            if (!this.validateFile(file)) {
                input.value = ''; // Réinitialiser
                return;
            }
            
            // Afficher la prévisualisation
            if (CONFIG.showPreview) {
                this.showFilePreview(input, file);
            }
        }
        
        // Valider un fichier
        validateFile(file) {
            // Taille
            const maxBytes = CONFIG.maxSizeMB * 1024 * 1024;
            if (file.size > maxBytes) {
                this.showError(`Fichier trop volumineux. Max: ${CONFIG.maxSizeMB}MB`);
                return false;
            }
            
            // Type (validation basique)
            const acceptTypes = CONFIG.acceptTypes.split(',');
            const fileExt = '.' + file.name.split('.').pop().toLowerCase();
            const fileType = file.type;
            
            const isValid = acceptTypes.some(type => {
                if (type.startsWith('.')) {
                    return fileExt === type;
                } else if (type.endsWith('/*')) {
                    const category = type.split('/')[0];
                    return fileType.startsWith(category + '/');
                }
                return fileType === type;
            });
            
            if (!isValid) {
                this.showError(`Type de fichier non supporté. Formats: ${CONFIG.acceptTypes}`);
                return false;
            }
            
            return true;
        }
        
        // Valider la taille du fichier
        validateFileSize(input) {
            if (!input.files || input.files.length === 0) return;
            
            const file = input.files[0];
            const maxBytes = CONFIG.maxSizeMB * 1024 * 1024;
            
            if (file.size > maxBytes) {
                this.showError(`Taille maximale dépassée (${CONFIG.maxSizeMB}MB)`);
                input.value = '';
            }
        }
        
        // Afficher la prévisualisation
        showFilePreview(input, file) {
            // Supprimer l'ancienne prévisualisation
            this.removeFilePreview(input);
            
            const previewId = Utils.generateId('preview');
            const previewContainer = document.createElement('div');
            previewContainer.id = previewId;
            previewContainer.className = 'mobile-preview-container';
            
            // Icône selon le type
            let icon = this.fileIcons.default;
            if (file.type.startsWith('image/')) icon = this.fileIcons.image;
            else if (file.type.startsWith('video/')) icon = this.fileIcons.video;
            else if (file.type === 'application/pdf') icon = this.fileIcons.pdf;
            else if (file.type.includes('word') || file.name.match(/\.docx?$/i)) icon = this.fileIcons.word;
            else if (file.type.includes('excel') || file.name.match(/\.xlsx?$/i)) icon = this.fileIcons.excel;
            
            // Aperçu image (si c'est une image)
            let imagePreview = '';
            if (file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const img = previewContainer.querySelector('.mobile-preview-image');
                    if (img) img.src = e.target.result;
                };
                reader.readAsDataURL(file);
                imagePreview = `<img class="mobile-preview-image" alt="Aperçu" style="max-width: 60px; max-height: 60px; border-radius: 4px; margin-right: 12px;">`;
            }
            
            previewContainer.innerHTML = `
                <div class="mobile-preview">
                    <div class="mobile-preview-icon">${icon}</div>
                    ${imagePreview}
                    <div class="mobile-preview-info">
                        <div class="mobile-preview-name">${this.truncateFileName(file.name, 30)}</div>
                        <div class="mobile-preview-size">${Utils.formatFileSize(file.size)} • ${file.type}</div>
                    </div>
                    <button type="button" class="mobile-remove-preview" data-input-id="${input.id}">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
            
            // Ajouter après l'input
            const reference = input.nextElementSibling || input;
            reference.parentNode.insertBefore(previewContainer, reference.nextSibling);
            
            // Sauvegarder la référence
            this.filePreviews.set(input, previewContainer);
            
            // Bouton de suppression
            previewContainer.querySelector('.mobile-remove-preview').addEventListener('click', () => {
                this.removeFilePreview(input);
                input.value = '';
            });
        }
        
        // Supprimer la prévisualisation
        removeFilePreview(input) {
            const preview = this.filePreviews.get(input);
            if (preview && preview.parentNode) {
                preview.parentNode.removeChild(preview);
                this.filePreviews.delete(input);
            }
        }
        
        // Tronquer le nom de fichier
        truncateFileName(name, maxLength) {
            if (name.length <= maxLength) return name;
            const extension = name.split('.').pop();
            const nameWithoutExt = name.substring(0, name.length - extension.length - 1);
            const truncated = nameWithoutExt.substring(0, maxLength - extension.length - 3);
            return truncated + '...' + extension;
        }
        
        // Afficher une erreur
        showError(message) {
            // Créer une notification temporaire
            const errorDiv = document.createElement('div');
            errorDiv.className = 'mobile-error-message';
            errorDiv.innerHTML = `
                <i class="fas fa-exclamation-triangle"></i>
                <span>${message}</span>
            `;
            
            errorDiv.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #fee2e2;
                color: #dc2626;
                padding: 12px 16px;
                border-radius: 8px;
                border-left: 4px solid #dc2626;
                z-index: 9999;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                animation: slideIn 0.3s ease;
                max-width: 300px;
            `;
            
            document.body.appendChild(errorDiv);
            
            // Supprimer après 5 secondes
            setTimeout(() => {
                if (errorDiv.parentNode) {
                    errorDiv.style.animation = 'slideOut 0.3s ease';
                    setTimeout(() => errorDiv.parentNode.removeChild(errorDiv), 300);
                }
            }, 5000);
            
            Utils.log(`Erreur: ${message}`, 'error');
        }
        
        // Observer les nouveaux éléments DOM
        setupMutationObserver() {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    mutation.addedNodes.forEach((node) => {
                        if (node.nodeType === 1) { // Element node
                            // Vérifier les inputs file dans le nouveau nœud
                            const inputs = node.querySelectorAll 
                                ? node.querySelectorAll('input[type="file"]')
                                : [];
                            
                            inputs.forEach(input => {
                                setTimeout(() => this.optimizeFileInput(input), 10);
                            });
                            
                            // Si le nœud est lui-même un input file
                            if (node.tagName === 'INPUT' && node.type === 'file') {
                                setTimeout(() => this.optimizeFileInput(node), 10);
                            }
                        }
                    });
                });
            });
            
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
            
            Utils.log('MutationObserver activé pour les nouveaux inputs', 'info');
        }
        
        // Injecter les styles dynamiques
        injectDynamicStyles() {
            const styleId = 'mobile-upload-dynamic-styles';
            
            // Supprimer les anciens styles
            const oldStyle = document.getElementById(styleId);
            if (oldStyle) oldStyle.remove();
            
            const style = document.createElement('style');
            style.id = styleId;
            
            style.textContent = `
                /* Animations */
                @keyframes slideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                
                @keyframes slideOut {
                    from { transform: translateX(0); opacity: 1; }
                    to { transform: translateX(100%); opacity: 0; }
                }
                
                /* Styles dynamiques pour prévisualisation */
                .mobile-preview-container {
                    animation: slideIn 0.3s ease;
                }
                
                .mobile-remove-preview {
                    background: none;
                    border: none;
                    color: #6b7280;
                    cursor: pointer;
                    padding: 8px;
                    border-radius: 4px;
                    transition: all 0.2s;
                }
                
                .mobile-remove-preview:hover {
                    background: #f3f4f6;
                    color: #dc2626;
                }
            `;
            
            document.head.appendChild(style);
        }
        
        // Événements globaux
        setupGlobalEvents() {
            // Empêcher le comportement par défaut du drop (pour mobile)
            document.addEventListener('dragover', (e) => e.preventDefault());
            document.addEventListener('drop', (e) => e.preventDefault());
            
            // Log des performances
            window.addEventListener('beforeunload', () => {
                Utils.log(`${this.optimizedInputs.size} input(s) optimisés pendant cette session`, 'info');
            });
        }
    }
    
    // ============================================
    // INITIALISATION AUTOMATIQUE
    // ============================================
    
    // Attendre que le DOM soit chargé
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            const optimizer = new MobileUploadOptimizer();
            optimizer.init();
            
            // Exposer globalement pour debug
            if (CONFIG.debug) {
                window.MobileUploadOptimizer = optimizer;
            }
        });
    } else {
        // DOM déjà chargé
        const optimizer = new MobileUploadOptimizer();
        optimizer.init();
        
        if (CONFIG.debug) {
            window.MobileUploadOptimizer = optimizer;
        }
    }
    
})();