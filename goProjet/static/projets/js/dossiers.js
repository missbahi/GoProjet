/**
 * Gestion des dossiers — Toggle "Tout sélectionner" pour les projets
 * Utilisé par gerer_dossiers.html et modifier_dossier.html
 */
(function() {
    'use strict';

    function initToggleProjects() {
        const toggleButton = document.getElementById('toggle-projects');
        if (!toggleButton) return;

        const checkboxes = document.querySelectorAll('input[name="projets"]');
        if (checkboxes.length === 0) return;

        function updateButtonText() {
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            toggleButton.textContent = allChecked
                ? 'Tout désélectionner'
                : 'Tout sélectionner';
        }

        // État initial
        updateButtonText();

        // Clic sur "Tout sélectionner" / "Tout désélectionner"
        toggleButton.addEventListener('click', function() {
            const shouldCheck = Array.from(checkboxes).some(cb => !cb.checked);
            checkboxes.forEach(cb => { cb.checked = shouldCheck; });
            updateButtonText();
        });

        // Mettre à jour le texte si l'utilisateur clique manuellement sur une case
        checkboxes.forEach(cb => {
            cb.addEventListener('change', updateButtonText);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initToggleProjects);
    } else {
        initToggleProjects();
    }
})();