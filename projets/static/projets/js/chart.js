// projets/static/projets/js/chart.js

document.addEventListener('DOMContentLoaded', function() {
    // La variable "chartData" a été créée dans le template HTML et est disponible ici
    if (typeof chartData !== 'undefined') {
        const ctx = document.getElementById('avancementChart').getContext('2d');
        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: 'Avancement (%)',
                    data: chartData.data,
                    backgroundColor: chartData.avancements.map(av => {
                        if (av < 20) return 'rgba(239, 68, 68, 0.7)';
                        if (av < 40) return 'rgba(249, 115, 22, 0.7)';
                        if (av < 60) return 'rgba(234, 179, 8, 0.7)';
                        if (av < 80) return 'rgba(34, 197, 94, 0.7)';
                        return 'rgba(22, 163, 74, 0.7)';
                    }),
                    borderColor: chartData.avancements.map(av => {
                        if (av < 20) return 'rgba(239, 68, 68, 1)';
                        if (av < 40) return 'rgba(249, 115, 22, 1)';
                        if (av < 60) return 'rgba(234, 179, 8, 1)';
                        if (av < 80) return 'rgba(34, 197, 94, 1)';
                        return 'rgba(22, 163, 74, 1)';
                    }),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    }

    // Gestion des boutons de période (votre code est correct ici)
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const period = this.dataset.period;
            // Exemple simplifié - en réalité, faire un appel AJAX
            console.log('Période sélectionnée:', period);
        });
    });
});