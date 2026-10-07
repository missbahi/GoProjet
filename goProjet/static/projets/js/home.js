(function() {
    'use strict';

    // ============================================================
    // Animation des cartes au chargement
    // ============================================================
    function initCardAnimation() {
        const cards = document.querySelectorAll('.dashboard-card');
        cards.forEach((card, index) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            setTimeout(() => {
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, index * 100);
        });
    }

    // ============================================================
    // Charger ApexCharts si nécessaire
    // ============================================================
    function loadApexCharts() {
        return new Promise((resolve) => {
            if (typeof ApexCharts !== 'undefined') return resolve();
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/apexcharts@3.35.0';
            script.async = true;
            script.onload = resolve;
            document.body.appendChild(script);
        });
    }

    // ============================================================
    // Initialiser le graphique d'avancement
    // ============================================================
    function initChart() {
        const chartElement = document.getElementById('avancementChart');
        if (!chartElement) return;

        try {
            const chartData = JSON.parse(chartElement.dataset.chartData || '{}');
            if (!chartData.projets || chartData.projets.length === 0) {
                console.warn('[home.js] Aucune donnée de projet pour le graphique');
                return;
            }

            loadApexCharts().then(() => {
                if (typeof ProjetsChartManager !== 'undefined') {
                    // Détruire l'ancien graphique s'il existe
                    if (window.chartManager && typeof window.chartManager.destroy === 'function') {
                        try { window.chartManager.destroy(); } catch (e) {}
                    }
                    window.chartManager = new ProjetsChartManager(chartData);
                } else {
                    console.warn('[home.js] ProjetsChartManager non défini');
                }
            });
        } catch (error) {
            console.error('[home.js] Erreur initialisation graphique:', error);
        }
    }

    // ============================================================
    // Nettoyer à la fermeture
    // ============================================================
    window.addEventListener('beforeunload', () => {
        if (window.chartManager && typeof window.chartManager.destroy === 'function') {
            try { window.chartManager.destroy(); } catch (e) {}
        }
    });

    // ============================================================
    // Démarrer quand le DOM est prêt
    // ============================================================
    function initAll() {
        initCardAnimation();
        initChart();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }

    // ============================================================
    // Ré-exécuter après un swap HTMX (si vous utilisez le pattern SPA)
    // ============================================================
    document.body.addEventListener('htmx:afterSwap', function(e) {
        if (e.target.id === 'main-content') {
            initCardAnimation();
            initChart();
        }
    });
})();