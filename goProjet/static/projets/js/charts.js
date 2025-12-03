
// static/projets/js/charts.js - Version simplifiée

class ProjetsChartManager {
    constructor(chartData) {
        this.chartData = chartData;
        this.currentChart = null;
        this.chartElement = document.getElementById('avancementChart');
        this.init();
    }

    init() {
        if (!this.chartElement) return;
        
        // Créer le graphique
        this.createChart();
        
        // Gérer le redimensionnement
        this.setupResizeHandler();
    }

    createChart() {
        const projets = this.chartData.projets || [];
        
        // Options optimisées pour mobile/desktop
        const options = {
            series: [{
                name: 'Avancement',
                data: projets.map(p => p.avancement)
            }],
            chart: {
                type: 'bar',
                height: '100%',
                toolbar: {
                    show: true,
                    tools: {
                        download: true,
                        selection: false,
                        zoom: false,
                        pan: false
                    }
                },
                animations: {
                    enabled: true,
                    speed: 500
                },
                background: 'transparent',
                foreColor: '#e5e7eb'
            },
            colors: projets.map(p => p.couleur), // Couleurs dynamiques
            plotOptions: {
                bar: {
                    horizontal: false,
                    columnWidth: '70%',
                    borderRadius: 4,
                    distributed: true // Chaque barre a sa couleur
                }
            },
            dataLabels: {
                enabled: true,
                formatter: (val) => `${Math.round(val)}%`,
                style: {
                    colors: ['#fff'],
                    fontSize: '11px',
                    fontWeight: 'bold'
                },
                offsetY: -5
            },
            xaxis: {
                categories: projets.map(p => p.nom_court),
                labels: {
                    style: {
                        colors: '#9ca3af',
                        fontSize: window.innerWidth < 640 ? '10px' : '12px'
                    },
                    rotate: window.innerWidth < 768 ? -45 : 0,
                    rotateAlways: window.innerWidth < 768
                }
            },
            yaxis: {
                min: 0,
                max: 100,
                title: {
                    text: 'Avancement %',
                    style: {
                        color: '#9ca3af',
                        fontSize: '12px'
                    }
                },
                labels: {
                    formatter: (val) => `${val}%`,
                    style: {
                        colors: '#9ca3af'
                    }
                }
            },
            tooltip: {
                theme: 'dark',
                y: {
                    formatter: (val) => `${val}% d'avancement`
                }
            },
            grid: {
                borderColor: '#4b5563',
                strokeDashArray: 4,
                xaxis: {
                    lines: {
                        show: false
                    }
                }
            },
            responsive: [
                {
                    breakpoint: 640,  // Mobile
                    options: {
                        chart: {
                            height: 250
                        },
                        dataLabels: {
                            enabled: false
                        },
                        plotOptions: {
                            bar: {
                                columnWidth: '60%'
                            }
                        }
                    }
                },
                {
                    breakpoint: 768,  // Tablet
                    options: {
                        chart: {
                            height: 300
                        },
                        dataLabels: {
                            enabled: true,
                            style: {
                                fontSize: '10px'
                            }
                        }
                    }
                }
            ]
        };

        // Nettoyer si un graphique existe déjà
        if (this.currentChart) {
            this.currentChart.destroy();
        }

        try {
            this.currentChart = new ApexCharts(this.chartElement, options);
            this.currentChart.render();
            
        } catch (error) {
            console.error('Erreur création graphique:', error);
            this.showFallbackChart(projets);
        }
    }

    showFallbackChart(projets) {
        // Graphique de secours HTML/CSS
        const maxValue = Math.max(...projets.map(p => p.avancement));
        
        this.chartElement.innerHTML = `
            <div style="
                display: flex;
                align-items: flex-end;
                justify-content: space-around;
                height: 100%;
                padding: 20px 10px;
                gap: 10px;
            ">
                ${projets.map(p => `
                    <div style="
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        flex: 1;
                        min-width: 40px;
                    ">
                        <div style="
                            background: ${p.couleur};
                            width: ${window.innerWidth < 640 ? '25px' : '35px'};
                            height: ${(p.avancement / maxValue) * 150}px;
                            border-radius: 4px 4px 0 0;
                            position: relative;
                        ">
                            <div style="
                                position: absolute;
                                top: -20px;
                                width: 100%;
                                text-align: center;
                                color: white;
                                font-size: 10px;
                                font-weight: bold;
                            ">
                                ${Math.round(p.avancement)}%
                            </div>
                        </div>
                        <div style="
                            margin-top: 8px;
                            color: #9ca3af;
                            font-size: ${window.innerWidth < 640 ? '9px' : '11px'};
                            text-align: center;
                            word-break: break-word;
                            max-width: 100%;
                        ">
                            ${p.nom_court}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    setupResizeHandler() {
        let resizeTimeout;
        
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                if (this.currentChart) {
                    this.currentChart.updateOptions({
                        xaxis: {
                            labels: {
                                rotate: window.innerWidth < 768 ? -45 : 0,
                                rotateAlways: window.innerWidth < 768,
                                style: {
                                    fontSize: window.innerWidth < 640 ? '10px' : '12px'
                                }
                            }
                        }
                    }, false, false);
                }
            }, 250);
        });
    }

    destroy() {
        if (this.currentChart) {
            this.currentChart.destroy();
        }
    }
}
// Export pour utilisation dans d'autres fichiers
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ProjetsChartManager };
}