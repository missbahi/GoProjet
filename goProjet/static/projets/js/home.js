(function () {
    'use strict';

    if (window.__homeInitialized) return;
    window.__homeInitialized = true;
    let dependencies = null;
    let generation = 0;
    let pendingElement = null;

    function loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = () => {
                script.remove();
                reject(new Error(`Chargement impossible : ${src}`));
            };
            document.body.appendChild(script);
        });
    }

    function loadDependencies() {
        if (!dependencies) {
            dependencies = Promise.all([
                typeof ApexCharts !== 'undefined' ? Promise.resolve()
                    : loadScript('https://cdn.jsdelivr.net/npm/apexcharts@3.35.0'),
                window.ProjetsChartManager ? Promise.resolve()
                    : loadScript('/static/projets/js/charts.js'),
            ]).catch(error => {
                dependencies = null;
                throw error;
            });
        }
        return dependencies;
    }

    function destroyChart() {
        generation++;
        pendingElement = null;
        if (window.chartManager) {
            window.chartManager.destroy();
            window.chartManager = null;
        }
    }

    async function initChart() {
        const element = document.getElementById('avancementChart');
        if (!element || pendingElement === element || window.chartManager?.chartElement === element) return;
        destroyChart();
        pendingElement = element;
        const version = generation;
        try {
            const data = JSON.parse(element.dataset.chartData);
            if (!data.projets.length) {
                element.textContent = 'Aucun projet disponible pour le graphique.';
                return;
            }
            await loadDependencies();
            if (version !== generation || !element.isConnected) return;
            window.chartManager = new window.ProjetsChartManager(data);
            await window.chartManager.ready;
        } catch (error) {
            console.error('[home] Graphique indisponible', error);
            if (version === generation && element.isConnected) {
                destroyChart();
                element.setAttribute('role', 'alert');
                element.textContent = "Impossible de charger le graphique d'avancement. Revenez sur Home pour réessayer.";
            }
        } finally {
            if (pendingElement === element) pendingElement = null;
        }
    }

    function initAll() {
        document.querySelectorAll('.dashboard-card').forEach((card, index) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            setTimeout(() => {
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, index * 100);
        });
        initChart();
    }

    document.body.addEventListener('htmx:beforeCleanupElement', event => {
        const element = document.getElementById('avancementChart');
        if (element && event.detail.elt.contains(element)) destroyChart();
    });
    document.body.addEventListener('htmx:afterSwap', event => {
        if (event.detail.target.id === 'main-content') initAll();
    });
    document.body.addEventListener('htmx:historyRestore', () => {
        destroyChart();
        // History may contain the rendered SVG of the previous instance.
        document.getElementById('avancementChart')?.replaceChildren();
        initAll();
    });
    window.addEventListener('beforeunload', destroyChart);

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }
})();
