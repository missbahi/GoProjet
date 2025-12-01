// notification-handler.js amélioré
(function () {
    'use strict';
    
    // Configuration
    const CONFIG = {
        position: 'bottom-right', // 'top-left', 'top-right', 'bottom-left', 'bottom-right'
        maxNotifications: 3,
        animationDuration: 300,
        successDuration: 3000,
        errorDuration: 5000,
        warningDuration: 4000,
        infoDuration: 3000
    };
    
    // Icônes et couleurs
    const STYLES = {
        success: {
            icon: '✓',
            bgColor: '#4caf50',
            iconColor: '#fff'
        },
        error: {
            icon: '✗',
            bgColor: '#f44336',
            iconColor: '#fff'
        },
        warning: {
            icon: '⚠',
            bgColor: '#ff9800',
            iconColor: '#fff'
        },
        info: {
            icon: 'ℹ',
            bgColor: '#2196f3',
            iconColor: '#fff'
        }
    };
    
    // Durées par type
    const DURATIONS = {
        success: CONFIG.successDuration,
        error: CONFIG.errorDuration,
        warning: CONFIG.warningDuration,
        info: CONFIG.infoDuration
    };
    
    // Queue pour gérer plusieurs notifications
    let notificationQueue = [];
    let activeNotifications = 0;
    
    // Fonction principale
    window.showNotification = function (message, type = 'success', options = {}) {
        const config = {
            duration: options.duration || DURATIONS[type] || CONFIG.successDuration,
            position: options.position || CONFIG.position,
            action: options.action, // { label: 'Voir', callback: function }
            onClose: options.onClose,
            persistent: options.persistent || false
        };
        
        // Ajouter à la queue
        notificationQueue.push({
            message,
            type,
            config
        });
        
        // Traiter la queue
        processQueue();
    };
    
    function processQueue() {
        // Si on a atteint le maximum, attendre
        if (activeNotifications >= CONFIG.maxNotifications) {
            return;
        }
        
        // Si la queue est vide, ne rien faire
        if (notificationQueue.length === 0) {
            return;
        }
        
        // Prendre la prochaine notification
        const nextNotification = notificationQueue.shift();
        createNotification(
            nextNotification.message,
            nextNotification.type,
            nextNotification.config
        );
        
        activeNotifications++;
    }
    
    function createNotification(message, type, config) {
        // Supprimer les notifications existantes si nécessaire
        cleanupOldNotifications();
        
        // Créer l'élément
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.dataset.createdAt = Date.now();
        
        // Style selon la position
        const positionStyle = getPositionStyle(config.position);
        
        // Appliquer les styles
        Object.assign(notification.style, {
            position: 'fixed',
            ...positionStyle,
            padding: '12px 16px',
            borderRadius: '8px',
            backgroundColor: STYLES[type]?.bgColor || '#333',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            zIndex: '9999',
            cursor: 'pointer',
            opacity: '0',
            transform: 'translateY(20px)',
            transition: `opacity ${CONFIG.animationDuration}ms ease, transform ${CONFIG.animationDuration}ms ease`,
            maxWidth: '400px',
            minWidth: '300px',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            fontSize: '14px',
            lineHeight: '1.4'
        });
        
        // Contenu HTML
        const iconSpan = document.createElement('span');
        iconSpan.className = 'notification-icon';
        iconSpan.textContent = STYLES[type]?.icon || '•';
        iconSpan.style.fontSize = '16px';
        iconSpan.style.fontWeight = 'bold';
        iconSpan.style.color = STYLES[type]?.iconColor || '#fff';
        
        const messageSpan = document.createElement('span');
        messageSpan.className = 'notification-message';
        messageSpan.textContent = message;
        messageSpan.style.flex = '1';
        
        // Bouton d'action optionnel
        let actionButton = null;
        if (config.action) {
            actionButton = document.createElement('button');
            actionButton.className = 'notification-action';
            actionButton.textContent = config.action.label;
            actionButton.style.background = 'transparent';
            actionButton.style.border = '1px solid rgba(255,255,255,0.3)';
            actionButton.style.color = '#fff';
            actionButton.style.padding = '4px 8px';
            actionButton.style.borderRadius = '4px';
            actionButton.style.fontSize = '12px';
            actionButton.style.cursor = 'pointer';
            actionButton.style.marginLeft = '10px';
            actionButton.style.transition = 'background 0.2s';
            
            actionButton.addEventListener('click', function(e) {
                e.stopPropagation();
                config.action.callback();
                closeNotification(notification);
            });
            
            actionButton.addEventListener('mouseenter', function() {
                this.style.background = 'rgba(255,255,255,0.1)';
            });
            
            actionButton.addEventListener('mouseleave', function() {
                this.style.background = 'transparent';
            });
        }
        
        // Bouton de fermeture
        const closeButton = document.createElement('button');
        closeButton.className = 'notification-close';
        closeButton.innerHTML = '×';
        closeButton.style.background = 'transparent';
        closeButton.style.border = 'none';
        closeButton.style.color = '#fff';
        closeButton.style.fontSize = '18px';
        closeButton.style.cursor = 'pointer';
        closeButton.style.marginLeft = '8px';
        closeButton.style.opacity = '0.7';
        closeButton.style.transition = 'opacity 0.2s';
        
        closeButton.addEventListener('mouseenter', function() {
            this.style.opacity = '1';
        });
        
        closeButton.addEventListener('mouseleave', function() {
            this.style.opacity = '0.7';
        });
        
        // Assembler
        notification.appendChild(iconSpan);
        notification.appendChild(messageSpan);
        if (actionButton) {
            notification.appendChild(actionButton);
        }
        notification.appendChild(closeButton);
        
        // Ajouter au DOM
        document.body.appendChild(notification);
        
        // Animation d'entrée
        requestAnimationFrame(() => {
            notification.style.opacity = '1';
            notification.style.transform = 'translateY(0)';
        });
        
        // Événements
        notification.addEventListener('click', function(e) {
            if (!e.target.classList.contains('notification-close') && 
                !e.target.classList.contains('notification-action')) {
                if (config.onClose) {
                    config.onClose();
                }
                closeNotification(notification);
            }
        });
        
        closeButton.addEventListener('click', function(e) {
            e.stopPropagation();
            closeNotification(notification);
        });
        
        // Auto-fermeture si pas persistante
        if (!config.persistent) {
            const timeout = setTimeout(() => {
                closeNotification(notification);
            }, config.duration);
            
            // Stocker le timeout pour pouvoir l'annuler
            notification.dataset.timeoutId = timeout;
        }
        
        // Hover pause
        notification.addEventListener('mouseenter', function() {
            if (this.dataset.timeoutId) {
                clearTimeout(parseInt(this.dataset.timeoutId));
            }
        });
        
        notification.addEventListener('mouseleave', function() {
            if (this.dataset.timeoutId && !config.persistent) {
                const timeout = setTimeout(() => {
                    closeNotification(notification);
                }, 1000); // Redémarrer avec 1 seconde après le hover
                this.dataset.timeoutId = timeout;
            }
        });
    }
    
    function closeNotification(notification) {
        if (!notification || !notification.parentNode) {
            activeNotifications = Math.max(0, activeNotifications - 1);
            processQueue();
            return;
        }
        
        // Animation de sortie
        notification.style.opacity = '0';
        notification.style.transform = 'translateY(20px)';
        
        // Suppression après animation
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
            activeNotifications = Math.max(0, activeNotifications - 1);
            processQueue();
        }, CONFIG.animationDuration);
    }
    
    function getPositionStyle(position) {
        const positions = {
            'top-left': { top: '20px', left: '20px' },
            'top-right': { top: '20px', right: '20px' },
            'bottom-left': { bottom: '20px', left: '20px' },
            'bottom-right': { bottom: '20px', right: '20px' }
        };
        
        return positions[position] || positions['bottom-right'];
    }
    
    function cleanupOldNotifications() {
        const notifications = document.querySelectorAll('.notification');
        const now = Date.now();
        const maxAge = 10000; // 10 secondes
        
        notifications.forEach(notification => {
            const createdAt = parseInt(notification.dataset.createdAt);
            if (now - createdAt > maxAge) {
                notification.remove();
            }
        });
    }
    
    // API publique additionnelle
    window.notificationAPI = {
        success: (msg, opts) => showNotification(msg, 'success', opts),
        error: (msg, opts) => showNotification(msg, 'error', opts),
        warning: (msg, opts) => showNotification(msg, 'warning', opts),
        info: (msg, opts) => showNotification(msg, 'info', opts),
        clearAll: () => {
            document.querySelectorAll('.notification').forEach(n => n.remove());
            notificationQueue = [];
            activeNotifications = 0;
        },
        setConfig: (newConfig) => {
            Object.assign(CONFIG, newConfig);
        }
    };
    
    // Initialisation automatique pour les messages Django
    document.addEventListener('DOMContentLoaded', function() {
        // Vérifier les messages Django
        const djangoMessages = document.querySelectorAll('.messages .alert');
        djangoMessages.forEach(message => {
            const text = message.textContent.trim();
            let type = 'info';
            
            if (message.classList.contains('alert-success')) type = 'success';
            if (message.classList.contains('alert-danger')) type = 'error';
            if (message.classList.contains('alert-warning')) type = 'warning';
            if (message.classList.contains('alert-info')) type = 'info';
            
            showNotification(text, type);
            message.remove(); // Nettoyer les messages Django
        });
        
        // Écouter les événements personnalisés
        document.addEventListener('show-notification', function(e) {
            showNotification(e.detail.message, e.detail.type, e.detail.options);
        });
    });
})();