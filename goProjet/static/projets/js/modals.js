
// Gestion des modals
function openModal(id) {
    document.getElementById(id).classList.remove('hidden');
    document.body.classList.add('overflow-hidden');
    // Fermer le menu utilisateur si ouvert
    document.getElementById('userMenuDropdown').classList.add('hidden');
}

function closeModal(id) {
    document.getElementById(id).classList.add('hidden');
    document.body.classList.remove('overflow-hidden');
}

// Gestionnaire de soumission de formulaire générique
async function submitForm(formId, successMessage, reloadNeeded = false) {
    const form = document.getElementById(formId);
    const submitBtn = form.querySelector('button[type="submit"]');
    
    if (!form || !submitBtn) return;
    
    // Désactiver le bouton
    submitBtn.disabled = true;
    submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
    
    try {
        const response = await fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        if (response.ok) {
            // Fermer la modale parente
            const modal = form.closest('[id$="Modal"]');
            if (modal) modal.classList.add('hidden');
            
            // Afficher message de succès
            showNotification(successMessage, 'success');
            
            // Recharger si nécessaire
            if (reloadNeeded) {
                setTimeout(() => window.location.reload(), 1000);
            }
        } else {
            const error = await response.text();
            throw new Error(error);
        }
    } catch (error) {
        console.error("Erreur:", error);
        showNotification("Erreur: " + error.message, 'error');
    } finally {
        // Réactiver le bouton
        submitBtn.disabled = false;
        submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
}

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    // Gérer la fermeture des modales avec ESC
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const openModals = document.querySelectorAll('[id$="Modal"]:not(.hidden)');
            openModals.forEach(modal => closeModal(modal.id));
        }
    });
    
    // Fermer en cliquant à l'extérieur
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('fixed') && e.target.id.includes('Modal')) {
            closeModal(e.target.id);
        }
    });
});