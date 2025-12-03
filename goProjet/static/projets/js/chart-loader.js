// static/js/chart-loader.js

class ChartLoader {
    constructor() {
        this.charts = new Map();
        this.apexChartsLoaded = false;
        this.init();
    }

    init() {
        this.loadApexCharts();
        this.setupIntersectionObserver();
    }

    loadApexCharts() {
        if (this.apexChartsLoaded) return Promise.resolve();
        
        return new Promise((resolve, reject) => {
            // Vérifier si ApexCharts est déjà chargé
            if (typeof ApexCharts !== 'undefined') {
                this.apexChartsLoaded = true;
                resolve();
                return;
            }

            // Charger le CSS
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = 'https://cdn.jsdelivr.net/npm/apexcharts@3.35.0/dist/apexcharts.css';
            link.onload = () => {
                // Charger le JS
                const script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/apexcharts@3.35.0';
                script.onload = () => {
                    this.apexChartsLoaded = true;
                    resolve();
                };
                script.onerror = reject;
                document.head.appendChild(script);
            };
            link.onerror = reject;
            document.head.appendChild(link);
        });
    }

    setupIntersectionObserver() {
        if (!('IntersectionObserver' in window)) return;

        this.observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const element = entry.target;
                    const chartId = element.id;
                    
                    if (chartId && !this.charts.has(chartId)) {
                        this.lazyLoadChart(element);
                    }
                }
            });
        }, {
            rootMargin: '50px',
            threshold: 0.1
        });
    }

    lazyLoadChart(element) {
        this.loadApexCharts().then(() => {
            // Attendre que les données soient disponibles
            const dataAttribute = element.dataset.chartData;
            if (dataAttribute) {
                const chartData = JSON.parse(dataAttribute);
                this.initializeChart(element, chartData);
            }
        }).catch(error => {
            console.error('Erreur lors du chargement de ApexCharts:', error);
        });
    }

    initializeChart(element, chartData) {
        const chartId = element.id;
        
        if (chartId === 'avancementChart') {
            this.charts.set(chartId, new ProjetsChartManager(chartData));
        }
        
        // Observer pour le redimensionnement
        this.setupResizeObserver(element);
    }

    setupResizeObserver(element) {
        if (!('ResizeObserver' in window)) return;

        const resizeObserver = new ResizeObserver(ChartUtils.debounce(() => {
            const chartId = element.id;
            const chart = this.charts.get(chartId);
            if (chart && chart.currentChart) {
                chart.currentChart.updateOptions({
                    chart: {
                        width: element.clientWidth
                    }
                }, false, true);
            }
        }, 250));

        resizeObserver.observe(element);
    }

    registerChart(element) {
        if (this.observer) {
            this.observer.observe(element);
        } else {
            // Fallback si IntersectionObserver n'est pas supporté
            this.lazyLoadChart(element);
        }
    }

    destroyChart(chartId) {
        const chart = this.charts.get(chartId);
        if (chart) {
            chart.destroy();
            this.charts.delete(chartId);
        }
    }

    destroyAll() {
        this.charts.forEach((chart, chartId) => {
            this.destroyChart(chartId);
        });
        
        if (this.observer) {
            this.observer.disconnect();
        }
    }
}

// Instance globale
window.ChartLoader = new ChartLoader();