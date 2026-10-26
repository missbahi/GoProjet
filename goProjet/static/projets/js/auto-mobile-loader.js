// static/projets/js/auto-mobile-loader.js
/**
 * Chargeur automatique pour Mobile Upload Optimizer
 * S'assure que les fichiers sont chargés dans le bon ordre
 */

(function() {
    'use strict';
    
    const loadScript = (src, callback) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = callback;
        script.onerror = () => console.error(`❌ Erreur de chargement: ${src}`);
        document.head.appendChild(script);
    };
    
    const loadStyle = (href) => {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = href;
        document.head.appendChild(link);
    };
    
    // Attendre que le DOM soit prêt
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    function init() {        
        // 1. Charger le CSS
        loadStyle('/static/projets/css/mobile-upload-min.css');
        
        // 2. Charger le script principal
        loadScript('/static/projets/js/mobile-upload-optimizer.js');
    }
    
})();