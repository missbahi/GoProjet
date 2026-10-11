/* static/projets/js/ordres_service.js */
(function () {
    'use strict';

    if (window.__ordresServiceInitialized) return;
    window.__ordresServiceInitialized = true;

    console.log('[ordres_service.js] Initialized');

    // ═══════════════════════════════════════════════════════════
    // TOGGLE FORMULAIRE PLIABLE
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('click', function (e) {
        if (e.target.closest('#os-toggle-add')) {
            e.preventDefault();
            toggleOsPanel();
            return;
        }
        if (e.target.closest('#os-close-add')) {
            e.preventDefault();
            closeOsPanel();
        }
    });

    function toggleOsPanel() {
        const panel = document.getElementById('os-add-panel');
        if (!panel) return;
        if (panel.classList.contains('open')) closeOsPanel();
        else openOsPanel();
    }

    function openOsPanel() {
        const panel = document.getElementById('os-add-panel');
        const btn = document.getElementById('os-toggle-add');
        if (!panel) return;
        panel.classList.add('open');
        btn?.setAttribute('aria-expanded', 'true');
        setTimeout(() => document.getElementById('type_os')?.focus(), 400);
    }

    function closeOsPanel() {
        const panel = document.getElementById('os-add-panel');
        const btn = document.getElementById('os-toggle-add');
        if (!panel) return;
        panel.classList.remove('open');
        btn?.setAttribute('aria-expanded', 'false');
    }

    // ═══════════════════════════════════════════════════════════
    // CHAMPS CONDITIONNELS SELON TYPE OS
    // ═══════════════════════════════════════════════════════════
    const typesOsData = window.TYPES_OS_DATA || {};

    function updateChampsConditionnels() {
        const typeOsSelect = document.getElementById('type_os');
        const champsConditionnels = document.getElementById('champs_conditionnels');
        const champDuree = document.getElementById('champ_duree');
        const champMontant = document.getElementById('champ_montant');
        const typeOsInfo = document.getElementById('type_os_info');
        const prerequisInfo = document.getElementById('prerequis_info');
        const uniciteInfo = document.getElementById('unicite_info');

        if (!typeOsSelect || !champsConditionnels) return;

        const selectedTypeId = typeOsSelect.value;
        const typeData = typesOsData[selectedTypeId];

        if (!typeData) {
            champsConditionnels.classList.add('hidden');
            typeOsInfo?.classList.add('hidden');
            return;
        }

        // Afficher/masquer durée
        if (typeData.showDuree) {
            champDuree?.classList.remove('hidden');
        } else {
            champDuree?.classList.add('hidden');
        }

        // Afficher/masquer montant
        if (typeData.showMontant) {
            champMontant?.classList.remove('hidden');
        } else {
            champMontant?.classList.add('hidden');
        }

        // Masquer la section entière si aucun champ conditionnel
        if (!typeData.showDuree && !typeData.showMontant) {
            champsConditionnels.classList.add('hidden');
        } else {
            champsConditionnels.classList.remove('hidden');
        }

        // Info type
        typeOsInfo?.classList.remove('hidden');

        if (prerequisInfo) {
            if (typeData.prerequis.length > 0) {
                prerequisInfo.innerHTML = `<i class="fas fa-info-circle mr-2"></i> Prérequis: ${typeData.prerequis.join(', ')}`;
            } else {
                prerequisInfo.innerHTML = `<i class="fas fa-info-circle mr-2"></i> Aucun prérequis`;
            }
        }

        if (uniciteInfo) {
            if (typeData.unique) {
                uniciteInfo.innerHTML = `<i class="fas fa-exclamation-triangle mr-2"></i> Type unique par projet`;
            } else {
                uniciteInfo.innerHTML = `<i class="fas fa-info-circle mr-2"></i> Type multiple autorisé`;
            }
        }
    }

    document.addEventListener('change', function (e) {
        if (e.target.id === 'type_os') {
            updateChampsConditionnels();
        }
    });

    // ═══════════════════════════════════════════════════════════
    // ALERTE SUR PASSAGE STATUT → NOTIFIE
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('change', function (e) {
        if (e.target.id !== 'statut' || e.target.value !== 'NOTIFIE') return;

        const typeOsSelect = document.getElementById('type_os');
        const selectedOption = typeOsSelect?.options[typeOsSelect.selectedIndex];
        const typeCode = selectedOption?.getAttribute('data-code') || '';

        if (typeCode && !['OSN'].includes(typeCode)) {
            alert('⚠️ Attention : La notification déclenchera les validations métier. Assurez-vous que tous les prérequis sont remplis.');
        }
    });

    // ═══════════════════════════════════════════════════════════
    // VALIDATION DES DATES + SPINNER SUBMIT
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('submit', function (e) {
        const form = e.target.closest('#ordreServiceForm');
        if (!form) return;

        const datePublication = document.getElementById('date_publication')?.value;
        const dateLimite = document.getElementById('date_limite')?.value;
        const dateEffet = document.getElementById('date_effet')?.value;

        if (dateLimite && datePublication > dateLimite) {
            e.preventDefault();
            alert('La date limite ne peut pas être antérieure à la date de publication.');
            return;
        }

        if (dateEffet && datePublication > dateEffet) {
            e.preventDefault();
            alert('La date d\'effet ne peut pas être antérieure à la date de publication.');
            return;
        }

        const submitBtn = document.getElementById('ordreServiceSubmitBtn');
        if (!submitBtn || submitBtn.disabled) return;

        submitBtn.disabled = true;
        submitBtn.querySelector('.ordre-service-submit-icon')?.classList.add('hidden');
        submitBtn.querySelector('.ordre-service-submit-spinner')?.classList.remove('hidden');
        const label = submitBtn.querySelector('.ordre-service-submit-label');
        if (label) label.textContent = 'Enregistrement...';
    });

    // ═══════════════════════════════════════════════════════════
    // CALCUL DES JOURS DÉCOULÉS (AJAX)
    // ═══════════════════════════════════════════════════════════
    document.addEventListener('change', function (e) {
        if (e.target.id !== 'date-reference') return;
        calculerJoursDecoules(e.target);
    });

    function calculerJoursDecoules(input) {
        const joursResultat = document.getElementById('jours-resultat');
        const dateFinResultat = document.getElementById('date-fin-resultat');
        if (!joursResultat || !input?.dataset.url) return;

        const dateReference = input.value;

        if (!dateReference) {
            joursResultat.textContent = '-';
            joursResultat.style.color = 'var(--text-muted)';
            if (dateFinResultat) dateFinResultat.textContent = 'Non déterminée';
            return;
        }

        // Loading
        joursResultat.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        joursResultat.style.color = 'var(--accent-primary)';

        fetch(`${input.dataset.url}?date=${dateReference}`)
            .then(r => r.json())
            .then(data => {
                if (data.jours !== null && data.jours !== undefined) {
                    joursResultat.textContent = data.jours;
                    joursResultat.style.color = 'var(--accent-green)';
                    // ⚡ Animation de pop quand la valeur change
                    joursResultat.classList.remove('changed');
                    void joursResultat.offsetWidth;  // force reflow
                    joursResultat.classList.add('changed');
                } else {
                    joursResultat.textContent = '-';
                    joursResultat.style.color = 'var(--accent-warning)';
                }
                if (dateFinResultat) {
                    dateFinResultat.textContent = data.date_fin
                        ? new Date(`${data.date_fin}T00:00:00`).toLocaleDateString('fr-FR')
                        : 'Non déterminée';
                }
            })
            .catch(err => {
                console.error('[os] jours découlés:', err);
                joursResultat.textContent = 'Erreur';
                joursResultat.style.color = 'var(--accent-danger)';
                if (dateFinResultat) dateFinResultat.textContent = 'Erreur';
            });
    }

    // ═══════════════════════════════════════════════════════════
    // HELPERS GLOBAUX (utilisés par les templates)
    // ═══════════════════════════════════════════════════════════
    window.updateOriginalFilename = function (input) {
        if (input.files && input.files[0]) {
            const hidden = document.getElementById('original_filename');
            if (hidden) hidden.value = input.files[0].name;
        }
    };

    // ═══════════════════════════════════════════════════════════
    // INIT APRÈS SWAP HTMX
    // ═══════════════════════════════════════════════════════════
    document.body.addEventListener('htmx:afterSwap', function (e) {
        if (e.detail.target.id === 'main-content') {
            updateChampsConditionnels();
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        updateChampsConditionnels();
    });

})();