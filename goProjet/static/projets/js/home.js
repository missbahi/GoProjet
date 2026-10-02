(function() {
    'use strict';

    // ============================================================
    // Animation des cartes
    // ============================================================
    document.addEventListener('DOMContentLoaded', function() {
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
    });

    // ============================================================
    // Graphique ApexCharts
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

    function initChart() {
        const el = document.getElementById('avancementChart');
        if (!el) return;

        try {
            const chartData = JSON.parse(el.dataset.chartData || '{}');
            if (!chartData.projets || chartData.projets.length === 0) return;

            loadApexCharts().then(() => {
                if (typeof ProjetsChartManager !== 'undefined') {
                    window.chartManager = new ProjetsChartManager(chartData);
                }
            });
        } catch (e) {
            console.error('Erreur init graphique:', e);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initChart);
    } else {
        initChart();
    }

    window.addEventListener('beforeunload', () => {
        if (window.chartManager && typeof window.chartManager.destroy === 'function') {
            window.chartManager.destroy();
        }
    });
})();