(function() {
    'use strict';

    // ============================================================
    // Log après swap HTMX (utile pour debug)
    // ============================================================
    document.body.addEventListener('htmx:afterSwap', function(e) {
        if (e.target.id === 'liste-utilisateurs-container') {
            console.log('[utilisateurs] Liste rafraîchie');
        }
    });

    // ============================================================
    // Réagir aux messages de succès (HX-Trigger)
    // ============================================================
    document.body.addEventListener('refreshListeUtilisateurs', function() {
        const container = document.getElementById('liste-utilisateurs-container');
        if (container && window.htmx) {
            htmx.ajax('GET', window.location.href, {
                target: '#liste-utilisateurs-container',
                swap: 'innerHTML',
            });
        }
    });
    document.addEventListener('click', function(e) {
        if (e.target.closest('#select-all-projets')) {
            document.querySelectorAll('input[name="projets"]').forEach(cb => cb.checked = true);
        }
        if (e.target.closest('#deselect-all-projets')) {
            document.querySelectorAll('input[name="projets"]').forEach(cb => cb.checked = false);
        }
    });
})();