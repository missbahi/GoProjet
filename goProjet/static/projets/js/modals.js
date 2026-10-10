// static/projets/js/modals.js
(function () {
    'use strict';

    if (window.__modalsInitialized) return;
    window.__modalsInitialized = true;

    // ═══════════════════════════════════════════════════════════
    // FERMETURE D'UN MODAL — gère tous les conteneurs
    // ═══════════════════════════════════════════════════════════
    window.closeModal = function (modalId, options = {}) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        // Animation de sortie
        modal.classList.add('opacity-0', 'scale-95');

        setTimeout(() => {
            // Conteneur HTMX générique
            const genericContainer = document.getElementById('modals-container');
            if (genericContainer && genericContainer.contains(modal)) {
                genericContainer.innerHTML = '';
            }
            // Conteneur dashboard projet
            const dashboardContainer = document.getElementById('dashboard-modal-container');
            if (dashboardContainer && dashboardContainer.contains(modal)) {
                dashboardContainer.innerHTML = '';
                dashboardContainer.classList.add('hidden');
            }
            // Ancien conteneur de liste_projets
            const legacyContainer = document.getElementById('modifierProjetModal-container');
            if (legacyContainer && legacyContainer.contains(modal)) {
                legacyContainer.innerHTML = '';
                legacyContainer.classList.add('hidden');
            }
            // Sinon : simple suppression
            if (modal.parentElement) modal.remove();

            document.body.classList.remove('overflow-hidden');

            if (options.reload) window.location.reload();
            if (options.message && window.showToast) {
                window.showToast(options.message, options.type || 'success');
            }
        }, 200);
    };

    // ═══════════════════════════════════════════════════════════
    // OUVERTURE GÉNÉRIQUE
    // ═══════════════════════════════════════════════════════════
    window.openModal = function (id) {
        const modal = document.getElementById(id);
        if (!modal) return;
        modal.classList.remove('hidden');
        document.body.classList.add('overflow-hidden');
        document.getElementById('userMenuDropdown')?.classList.add('hidden');
    };

    // ═══════════════════════════════════════════════════════════
    // ÉCHAP + BACKDROP
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        document.querySelectorAll('.modal[style*="block"], .modal:not(.hidden)')
            .forEach(m => { if (m.id) window.closeModal(m.id); });
    });

    document.addEventListener('click', function (e) {
        // Backdrop des modals hors-conteneurs
        if (e.target.classList.contains('fixed') && e.target.id?.includes('Modal')) {
            window.closeModal(e.target.id);
        }
    });

    // ═══════════════════════════════════════════════════════════
    // SOUMISSION FORMULAIRE GÉNÉRIQUE (submitForm)
    // ═══════════════════════════════════════════════════════════
    window.submitForm = async function (formId, successMessage, reloadNeeded = false) {
        const form = document.getElementById(formId);
        if (!form) return;
        const submitBtn = form.querySelector('button[type="submit"]');
        submitBtn && (submitBtn.disabled = true);

        try {
            const res = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!res.ok) throw new Error(await res.text());

            const modal = form.closest('[id$="Modal"]');
            if (modal) window.closeModal(modal.id);

            window.showSuccessMessage?.(successMessage);
            if (reloadNeeded) setTimeout(() => window.location.reload(), 1000);
        } catch (err) {
            window.showErrorMessage?.("Erreur : " + err.message);
        } finally {
            submitBtn && (submitBtn.disabled = false);
        }
    };

})();