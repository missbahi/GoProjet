(function () {
    'use strict';

    if (!window.SommaireCharts) {
        const APEX_URL = 'https://cdn.jsdelivr.net/npm/apexcharts@3.35.0';
        const number = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 });
        const percent = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 });
        const bound = new WeakSet();
        let apexPromise = null;

        function loadApex() {
            if (typeof ApexCharts !== 'undefined') return Promise.resolve();
            if (!apexPromise) {
                apexPromise = new Promise((resolve, reject) => {
                    const script = document.createElement('script');
                    script.src = APEX_URL;
                    script.onload = resolve;
                    script.onerror = () => {
                        script.remove();
                        apexPromise = null;
                        reject(new Error(`Chargement impossible : ${APEX_URL}`));
                    };
                    document.body.appendChild(script);
                });
            }
            return apexPromise;
        }

        function monthLabel(value) {
            const [year, month] = value.split('-').map(Number);
            return new Date(year, month - 1, 1)
                .toLocaleDateString('fr-FR', { month: 'short', year: '2-digit' });
        }

        function compact(value) {
            if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1).replace('.', ',')} M`;
            if (Math.abs(value) >= 1e3) return `${Math.round(value / 1e3)} k`;
            return number.format(value);
        }

        function base(data, cumul) {
            const textColor = getComputedStyle(document.body).getPropertyValue('--text-secondary').trim() || '#9ca3af';
            return {
                chart: {
                    type: cumul ? 'line' : 'bar', height: '100%', toolbar: { show: false },
                    animations: { enabled: !window.matchMedia('(prefers-reduced-motion: reduce)').matches },
                    foreColor: textColor,
                },
                plotOptions: { bar: { columnWidth: '60%', borderRadius: 3 } },
                dataLabels: { enabled: false },
                xaxis: {
                    categories: data.mois.map(monthLabel),
                    labels: { rotate: -45, rotateAlways: data.mois.length > 12 },
                    tickAmount: Math.min(data.mois.length, 12),
                },
                legend: { position: 'top', horizontalAlign: 'left' },
                grid: { borderColor: '#4b5563', strokeDashArray: 4, xaxis: { lines: { show: false } } },
                noData: { text: 'Aucune donnée' },
            };
        }

        const KINDS = {
            evolution: {
                elementId: 'sommaireEvolutionChart',
                empty: 'Aucune donnée à afficher.',
                options(data, mode) {
                    const cumul = mode === 'cumul';
                    const options = base(data, cumul);
                    return {
                        ...options,
                        chart: { ...options.chart, type: 'line' },
                        series: [
                            { name: "Chiffre d'affaires", type: cumul ? 'line' : 'column', data: cumul ? data.ca_cumul : data.ca },
                            { name: 'Attachements validés', type: cumul ? 'line' : 'column', data: cumul ? data.attachements_cumul : data.attachements },
                            { name: cumul ? 'Résultat cumulé (DH)' : 'Résultat (DH)', type: 'line', data: cumul ? data.resultat_cumul : data.resultat },
                            { name: cumul ? '% résultat cumulé / CA' : '% résultat / CA', type: 'line', data: cumul ? data.pct_cumul : data.pct },
                        ],
                        colors: ['#0ea5e9', '#f59e0b', '#a78bfa', '#22c55e'],
                        stroke: { width: cumul ? [3, 3, 3, 3] : [0, 0, 3, 3], dashArray: [0, 0, 0, 5], curve: 'smooth' },
                        markers: { size: cumul ? 0 : 3 },
                        yaxis: [
                            { seriesName: "Chiffre d'affaires", labels: { formatter: compact }, title: { text: 'Montants (DH)' } },
                            { seriesName: "Chiffre d'affaires", show: false },
                            { seriesName: "Chiffre d'affaires", show: false },
                            {
                                opposite: true, seriesName: cumul ? '% résultat cumulé / CA' : '% résultat / CA',
                                labels: { formatter: value => (value == null ? '' : `${percent.format(value)} %`) },
                                title: { text: 'Résultat (% du CA)', style: { color: '#22c55e' } },
                                axisBorder: { show: true, color: '#22c55e' }, axisTicks: { show: true, color: '#22c55e' },
                            },
                        ],
                        tooltip: {
                            theme: 'dark', shared: true, intersect: false,
                            y: {
                                formatter: (value, { seriesIndex }) => {
                                    if (seriesIndex < 3) return `${number.format(value)} DH`;
                                    return value == null ? 'n/d (CA nul)' : `${percent.format(value)} %`;
                                },
                            },
                        },
                    };
                },
            },
        };

        const instances = {};

        function destroy(kind) {
            const instance = instances[kind];
            if (!instance) return;
            instance.generation++;
            if (instance.chart) {
                try { instance.chart.destroy(); } catch (error) { /* élément déjà retiré du DOM */ }
            }
            instance.chart = null;
            instance.element = null;
        }

        async function render(kind, element, data, mode) {
            const instance = instances[kind] || (instances[kind] = { chart: null, element: null, generation: 0 });
            const version = ++instance.generation;
            if (instance.chart) {
                try { instance.chart.destroy(); } catch (error) { /* ignoré */ }
                instance.chart = null;
            }
            element.replaceChildren();
            await loadApex();
            if (version !== instance.generation || !element.isConnected) return;
            instance.element = element;
            instance.chart = new ApexCharts(element, KINDS[kind].options(data, mode));
            await instance.chart.render();
        }

        function showError(kind, element) {
            destroy(kind);
            element.setAttribute('role', 'alert');
            element.textContent = 'Impossible de charger le graphique.';
        }

        function bindModes(kind, element, data) {
            const root = element.closest('[data-chart-root]') || document;
            root.querySelectorAll('[data-chart-mode]').forEach(button => {
                if (bound.has(button)) return;
                bound.add(button);
                button.addEventListener('click', () => {
                    root.querySelectorAll('[data-chart-mode]').forEach(other => {
                        const active = other === button;
                        other.setAttribute('aria-pressed', String(active));
                        other.style.backgroundColor = active ? 'var(--accent-primary)' : 'var(--bg-elevated)';
                        other.style.color = active ? 'var(--bg-surface)' : 'var(--text-secondary)';
                    });
                    render(kind, element, data, button.dataset.chartMode).catch(() => showError(kind, element));
                });
            });
        }

        function initKind(kind) {
            const element = document.getElementById(KINDS[kind].elementId);
            if (!element) return;
            if (instances[kind]?.element === element && element.firstChild) return;
            destroy(kind);
            const source = document.getElementById(element.dataset.source);
            const data = source ? JSON.parse(source.textContent) : null;
            if (!data || !data.mois.length) {
                element.textContent = KINDS[kind].empty;
                return;
            }
            bindModes(kind, element, data);
            render(kind, element, data, 'mensuel').catch(() => showError(kind, element));
        }

        function init() {
            Object.keys(KINDS).forEach(initKind);
        }

        document.body.addEventListener('htmx:beforeCleanupElement', event => {
            Object.entries(instances).forEach(([kind, instance]) => {
                if (instance.element && event.detail.elt.contains(instance.element)) destroy(kind);
            });
        });
        document.body.addEventListener('htmx:historyRestore', () => {
            Object.keys(instances).forEach(destroy);
            init();
        });
        window.addEventListener('beforeunload', () => Object.keys(instances).forEach(destroy));
        window.SommaireCharts = { init };
    }

    window.SommaireCharts.init();
}());
