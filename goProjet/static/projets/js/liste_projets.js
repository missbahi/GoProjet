(function() {
    'use strict';

    // ============================================================
    // Toggle vue
    // ============================================================
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.vue-btn');
        if (!btn) return;
        e.preventDefault();
        basculerVue(btn.dataset.vue);
    });

    function basculerVue(vue) {
        const url = new URL(window.location.href);
        url.searchParams.set('vue', vue);
        url.searchParams.delete('page');
        const chemin = url.pathname + url.search;

        htmx.ajax('GET', chemin, {
            target: '#liste_projets',
            swap: 'innerHTML',
        });

        document.querySelectorAll('.vue-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.vue === vue);
        });

        window.history.replaceState({}, '', chemin);
    }

    // ============================================================
    // Rechargement après action (soumission, suppression)
    // ============================================================
    window.rechargerListeProjets = function() {
        const url = new URL(window.location.href);
        htmx.ajax('GET', url.pathname + url.search, {
            target: '#liste_projets',
            swap: 'innerHTML',
        });
    };

    // ============================================================
    // Recherche
    // ============================================================
    const searchToggle = document.getElementById('searchToggle');
    const searchBox = document.getElementById('searchBox');
    const searchInput = document.getElementById('searchInput');
    const clearSearch = document.getElementById('clearSearch');
    let searchTimeout = null;

    if (searchToggle && searchBox) {
        searchToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            searchBox.classList.toggle('hidden');
            if (!searchBox.classList.contains('hidden')) {
                setTimeout(() => searchInput && searchInput.focus(), 100);
            }
        });
    }

    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const term = this.value.trim();
            if (clearSearch) {
                clearSearch.classList.toggle('hidden', term.length === 0);
            }
            if (searchTimeout) clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                if (term.length >= 3 || term.length === 0) {
                    performSearch(term);
                }
            }, 500);
        });
    }

    if (clearSearch) {
        clearSearch.addEventListener('click', function() {
            searchInput.value = '';
            clearSearch.classList.add('hidden');
            performSearch('');
        });
    }

    function performSearch(term) {
        const url = new URL(window.location.href);
        if (term.length >= 3) {
            url.searchParams.set('search', term);
        } else {
            url.searchParams.delete('search');
        }
        url.searchParams.delete('page');

        htmx.ajax('GET', url.toString(), {
            target: '#liste_projets',
            swap: 'innerHTML',
        });
    }

    // ============================================================
    // Tri — conservé pour compatibilité avec les en-têtes du tableau
    // ============================================================
    window.sortTable = function(field) {
        const url = new URL(window.location.href);
        const currentSort = url.searchParams.get('sort');
        const currentOrder = url.searchParams.get('order') || 'asc';

        let newOrder = 'asc';
        if (currentSort === field) {
            newOrder = currentOrder === 'asc' ? 'desc' : 'asc';
        }

        url.searchParams.set('sort', field);
        url.searchParams.set('order', newOrder);
        url.searchParams.delete('page');

        htmx.ajax('GET', url.toString(), {
            target: '#liste_projets',
            swap: 'innerHTML',
        });
    };

    window.resetSort = function() {
        const url = new URL(window.location.href);
        url.searchParams.delete('sort');
        url.searchParams.delete('order');
        url.searchParams.delete('page');
        htmx.ajax('GET', url.toString(), {
            target: '#liste_projets',
            swap: 'innerHTML',
        });
    };

    // ============================================================
    // Modal de chargement (pour modifier projet)
    // ============================================================
    window.charger_modal = async function(url) {
        const container = document.getElementById('modals-container');
        try {
            const response = await fetch(url);
            const html = await response.text();
            container.innerHTML = html;
        } catch (error) {
            console.error('Erreur chargement modal:', error);
        }
    };

    // ============================================================
    // Suppression de projet
    // ============================================================
    window.supprimerProjet = function(event, element) {
        event.preventDefault();
        if (!confirm('Supprimer ce projet ?')) return;

        fetch(element.href, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
        })
        .then(response => {
            if (response.ok) {
                htmx.ajax('GET', window.location.href, {
                    target: '#liste_projets',
                    swap: 'innerHTML',
                });
            }
        })
        .catch(error => console.error('Error:', error));
    };

    function getCsrfToken() {
        const el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    // // ============================================================
    // // Gestion générique des modals
    // // ============================================================
    // window.closeModal = function(modalId, options = {}) {
    //     const modal = document.getElementById(modalId);
    //     if (!modal) return;

    //     modal.classList.add('opacity-0', 'scale-95');
    //     setTimeout(() => {
    //         // Si le modal est dans #modals-container, on vide le conteneur
    //         const container = document.getElementById('modals-container');
    //         if (container && container.contains(modal)) {
    //             container.innerHTML = '';
    //         } else {
    //             modal.remove();
    //         }
    //         document.body.classList.remove('overflow-hidden');

    //         if (options.reload) window.location.reload();
    //         if (options.message) {
    //             if (window.showNotification) {
    //                 window.showNotification(options.message, options.type || 'success');
    //             }
    //         }
    //     }, 200);
    // };

    // // Fermeture avec Échap
    // document.addEventListener('keydown', function(e) {
    //     if (e.key !== 'Escape') return;
    //     const container = document.getElementById('modals-container');
    //     if (!container) return;
    //     const openModals = container.querySelectorAll(':scope > div[id]');
    //     openModals.forEach(modal => {
    //         if (modal.id) window.closeModal(modal.id);
    //     });
    // });

    // // Fermeture par clic sur le backdrop
    // document.addEventListener('click', function(e) {
    //     const container = document.getElementById('modals-container');
    //     if (!container) return;
    //     const modal = e.target.closest('#modals-container > div.fixed.inset-0');
    //     if (!modal) return;
    //     if (e.target !== modal) return; // clic à l'intérieur → ignorer
    //     if (modal.id) window.closeModal(modal.id);
    // });

})();
// ============================================================
// Soumission des formulaires projet (ajout + modification)
// ============================================================
document.addEventListener('click', async function(e) {
    const btn = e.target.closest('.btn-save-projet');
    if (!btn) return;
    e.preventDefault();
    const form = btn.closest('form');
    if (!form) return;

    const modal = btn.closest('.modal-projet');
    const modalId = modal ? modal.id : null;
    btn.disabled = true;
    btn.classList.add('opacity-50', 'cursor-not-allowed');
    try {
        const response = await fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (response.ok) {
            if (modalId) window.closeModal(modalId);
            const url = new URL(window.location.href);
            htmx.ajax('GET', url.pathname + url.search, {
                target: '#liste_projets',
                swap: 'innerHTML',
            });

            if (window.showNotification) {
                const msg = form.id === 'nouveauProjetForm'
                    ? 'Nouveau projet créé avec succès'
                    : 'Projet mis à jour avec succès';
                window.showNotification(msg, 'success');
            }
        } else {
            const error = await response.text();
            if (window.showNotification) {
                window.showNotification('Erreur: ' + error, 'error');
            }
        }
    } catch (err) {
        console.error('Erreur:', err);
        if (window.showNotification) {
            window.showNotification('Erreur: ' + err.message, 'error');
        }
    } finally {
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
});

// Gestion du toggle "révisable" → affiche/masque le bouton config
document.addEventListener('change', function(e) {
    if (e.target.name !== 'revisable') return;
    const container = document.getElementById('config-revision-btn-container');
    if (!container) return;
    container.classList.toggle('hidden', !e.target.checked);
    container.classList.toggle('flex', e.target.checked);
});