(function () {
    window.showNotification = function (message, type = 'success', duration = 5000) {
        const existing = document.querySelector('.notification');
        if (existing) existing.remove();

        const notification = document.createElement('div');
        notification.className = `notification ${type}`;

        const iconMap = {
            success: '✓',
            error: '✗',
            warning: '⚠',
            info: 'ℹ'
        };

        notification.innerHTML = `
            <span class="notification-icon">${iconMap[type] || '•'}</span>
            <span class="notification-message">${message}</span>
        `;

        const style = notification.style;
        style.position = 'fixed';
        style.bottom = '20px';
        style.right = '20px';
        style.padding = '10px 15px';
        style.borderRadius = '8px';
        style.backgroundColor = {
            success: '#4caf50',
            error: '#f44336',
            warning: '#ff9800',
            info: '#2196f3'
        }[type] || '#333';
        style.color = '#fff';
        style.display = 'flex';
        style.alignItems = 'center';
        style.gap = '8px';
        style.boxShadow = '0 4px 8px rgba(0,0,0,0.2)';
        style.zIndex = 9999;
        style.cursor = 'pointer';
        style.opacity = '0';
        style.transform = 'translateY(20px)';
        style.transition = 'opacity 0.3s ease, transform 0.3s ease';

        document.body.appendChild(notification);

        // Animation d'apparition
        requestAnimationFrame(() => {
            style.opacity = '1';
            style.transform = 'translateY(0)';
        });

        // Disparition après la durée
        setTimeout(() => closeNotification(notification), duration);

        // Fermeture au clic
        notification.addEventListener('click', () => closeNotification(notification));
    };

    function closeNotification(notification) {
        // Animation de sortie
        notification.style.opacity = '0';
        notification.style.transform = 'translateY(20px)';
        // Suppression après la fin de la transition
        setTimeout(() => notification.remove(), 300);
    }
})();
