// static/js/chart-utils.js

class ChartUtils {
    static formatPercentage(value) {
        return `${Math.round(value)}%`;
    }

    static formatCurrency(value, currency = 'MAD') {
        return new Intl.NumberFormat('fr-FR', {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(value);
    }

    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    static throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
}

// Fonctions pour créer des graphiques spécifiques
const ChartFactory = {
    createAvancementChart(elementId, data, options = {}) {
        const defaultOptions = {
            height: 280,
            colors: ['#2B9C62', '#60a5fa'],
            showLegend: true,
            showToolbar: true
        };
        
        const mergedOptions = { ...defaultOptions, ...options };
        
        return {
            render() {
                // Logique de rendu spécifique
                console.log(`Rendu du graphique dans ${elementId}`);
            }
        };
    }
};

// Export pour utilisation dans d'autres fichiers
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ChartUtils, ChartFactory };
}