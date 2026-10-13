/**
 * projets/js/ressource-modal.js
 *
 * Contrôleur générique du modal de ressource affectée.
 * - Filtre automatique : l'utilisateur tape un code ou un fragment de nom
 * - Le <input list> natif propose les correspondances
 * - L'ID réel est envoyé au serveur via un <input type="hidden">
 */
(function () {
    'use strict';

    const config = document.getElementById('ressource-config');
    if (!config) return;

    const ADD_URL         = config.dataset.addUrl;
    const EDIT_TEMPLATE   = config.dataset.editTemplate;
    const DELETE_TEMPLATE = config.dataset.deleteTemplate;
    const API_OPTIONS     = config.dataset.apiOptions;
    const API_ATELIERS    = config.dataset.apiAteliers;

    const modal    = document.getElementById('modalRessource');
    const form     = document.getElementById('formRessource');
    const backdrop = document.querySelector('[data-modal-backdrop]');

    const $ = (id) => document.getElementById(id);

    // ------------------------------------------------------------
    // Utilitaires
    // ------------------------------------------------------------
    function urlFromTemplate(tpl, id) {
        return tpl.replace('/0/', `/${id}/`).replace(/\/0$/, `/${id}`);
    }

    function csrfToken() {
        return form?.querySelector('[name=csrfmiddlewaretoken]')?.value
            || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
    }

    function openModal() {
        backdrop?.removeAttribute('hidden');
        modal?.removeAttribute('hidden');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        modal?.setAttribute('hidden', '');
        backdrop?.setAttribute('hidden', '');
        document.body.style.overflow = '';
    }

    function showToast(message, isError = false) {
        const el = document.createElement('div');
        el.textContent = message;
        el.style.cssText = `
            position: fixed; bottom: 1rem; right: 1rem; z-index: 9999;
            padding: 0.75rem 1rem; border-radius: 6px;
            background: ${isError ? '#dc2626' : '#16a34a'};
            color: white; box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            font-size: 0.875rem; max-width: 22rem;
        `;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 3500);
    }

    // ------------------------------------------------------------
    // Chargement dynamique des options (datalist)
    // ------------------------------------------------------------
    async function chargerOptions(code, selectedId = null) {
        const input    = $('ressource-objet-input');
        const datalist = $('ressource-objet-datalist');
        const hidden   = $('ressource-objet');

        if (!input || !datalist || !hidden) return;

        // Reset
        datalist.innerHTML = '';
        hidden.value = '';
        input.value = '';

        if (!code) {
            input.disabled = true;
            input.placeholder = "— Sélectionnez d'abord un type —";
            return;
        }

        input.disabled = true;
        input.placeholder = 'Chargement…';

        try {
            const resp = await fetch(`${API_OPTIONS}?code=${encodeURIComponent(code)}`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            const data = await resp.json();
            const options = data.options || [];

            datalist.innerHTML = options.map(o => {
                const label = o.unite ? `${o.label} (${o.unite})` : o.label;
                return `<option value="${label}"
                                data-id="${o.id}"
                                data-prix="${o.prix || 0}"></option>`;
            }).join('');

            input.disabled = false;
            input.placeholder = 'Tapez le code ou le nom…';

            // Pré-sélection (mode édition)
            if (selectedId) {
                const opt = options.find(o => String(o.id) === String(selectedId));
                if (opt) {
                    const label = opt.unite ? `${opt.label} (${opt.unite})` : opt.label;
                    input.value = label;
                    hidden.value = opt.id;
                }
            }
        } catch (err) {
            console.error('Erreur chargement options:', err);
            input.placeholder = 'Erreur de chargement';
            input.disabled = false;
        }
    }

    // ------------------------------------------------------------
    // Chargement des ateliers (uniquement pour MATERIEL)
    // ------------------------------------------------------------
    async function chargerAteliers(selectedId = null) {
        const selectAtelier = $('ressource-atelier');
        if (!selectAtelier) return;

        selectAtelier.innerHTML = '<option value="">Chargement…</option>';

        try {
            const resp = await fetch(API_ATELIERS, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            const data = await resp.json();
            const ateliers = data.ateliers || [];

            selectAtelier.innerHTML = '<option value="">— Non affecté à un atelier —</option>'
                + ateliers.map(a => {
                    const sel = (selectedId && String(a.id) === String(selectedId)) ? ' selected' : '';
                    return `<option value="${a.id}"${sel}>${a.code} — ${a.libelle}</option>`;
                }).join('');
        } catch (e) {
            selectAtelier.innerHTML = '<option value="">Erreur de chargement</option>';
        }
    }

    // ------------------------------------------------------------
    // Visibilité du champ atelier
    // ------------------------------------------------------------
    function toggleAtelier(code) {
        const wrapper = $('ressource-atelier-wrapper');
        const select  = $('ressource-atelier');
        if (!wrapper || !select) return;

        if (code === 'MATERIEL') {
            wrapper.removeAttribute('hidden');
        } else {
            wrapper.setAttribute('hidden', '');
            select.value = '';
        }
    }

    // ------------------------------------------------------------
    // Synchronisation input visible → hidden id
    // ------------------------------------------------------------
    function syncObjetId() {
        const input    = $('ressource-objet-input');
        const datalist = $('ressource-objet-datalist');
        const hidden   = $('ressource-objet');
        const tarif    = $('ressource-tarif');

        if (!input || !datalist || !hidden) return;

        const value = input.value.trim();
        if (!value) {
            hidden.value = '';
            return;
        }

        const option = Array.from(datalist.options).find(o => o.value === value);
        if (option) {
            hidden.value = option.dataset.id;
            // Auto-remplir le tarif si encore à 0
            if (tarif && option.dataset.prix && parseFloat(tarif.value) === 0) {
                tarif.value = option.dataset.prix;
            }
        } else {
            hidden.value = '';
        }
    }

    // ------------------------------------------------------------
    // Ouverture du modal (ajout OU édition)
    // ------------------------------------------------------------
    document.querySelectorAll('[data-open-ressource-modal]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const mode           = btn.dataset.mode || 'add';
            const categorieId    = btn.dataset.categorieId;
            const categorieCode  = btn.dataset.categorieCode;
            const categorieLabel = btn.dataset.categorieLabel || '—';
            const ressourceId    = btn.dataset.ressourceId;

            // Injection du type (hidden + bandeau)
            $('ressource-categorie').value = categorieId || '';
            $('ressource-categorie-label').textContent = categorieLabel;

            // Titre + libellé du bouton
            const titleEl  = document.querySelector('[data-modal-title-text]');
            const submitEl = document.querySelector('[data-modal-submit-text]');
            if (mode === 'edit') {
                if (titleEl)  titleEl.textContent  = "Modifier l'affectation";
                if (submitEl) submitEl.textContent = 'Enregistrer';
                form.action = urlFromTemplate(EDIT_TEMPLATE, ressourceId);
            } else {
                if (titleEl)  titleEl.textContent  = 'Affecter une ressource';
                if (submitEl) submitEl.textContent = 'Affecter';
                form.action = ADD_URL;
                form.reset();
                $('ressource-debut').value = new Date().toISOString().slice(0, 10);
            }

            // Reset input ressource
            const inputObj = $('ressource-objet-input');
            if (inputObj) {
                inputObj.value = '';
                inputObj.disabled = true;
                inputObj.placeholder = 'Chargement…';
            }
            $('ressource-objet').value = '';

            // Charger les options
            const objetId = mode === 'edit' ? btn.dataset.objetId : null;
            await chargerOptions(categorieCode, objetId);

            // Atelier (uniquement MATERIEL)
            toggleAtelier(categorieCode);
            if (categorieCode === 'MATERIEL') {
                const atelierId = mode === 'edit' ? btn.dataset.atelierId : null;
                await chargerAteliers(atelierId);
            }

            // Pré-remplissage (édition)
            if (mode === 'edit') {
                $('ressource-debut').value       = btn.dataset.dateDebut || '';
                $('ressource-fin').value         = btn.dataset.dateFin || '';
                $('ressource-commentaire').value = btn.dataset.commentaire || '';

                // ⚡ Tarif : forcer format nombre (gère virgule ou point)
                const tarifBrut = btn.dataset.tarif || '';
                const tarifNum  = parseFloat(String(tarifBrut).replace(',', '.'));
                $('ressource-tarif').value = isNaN(tarifNum) ? '0.00' : tarifNum.toFixed(2);
            } else {
                $('ressource-fin').value         = '';
                $('ressource-tarif').value       = '0.00';
                $('ressource-commentaire').value = '';
            }

            openModal();
        });
    });

    // ------------------------------------------------------------
    // Écoute de la saisie dans l'input ressource
    // ------------------------------------------------------------
    document.getElementById('ressource-objet-input')?.addEventListener('input', syncObjetId);
    document.getElementById('ressource-objet-input')?.addEventListener('change', syncObjetId);

    // ------------------------------------------------------------
    // Soumission du formulaire
    // ------------------------------------------------------------
    form?.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Validation : la ressource doit être réellement sélectionnée
        const hidden = $('ressource-objet');
        if (!hidden || !hidden.value) {
            showToast('Sélectionnez une ressource dans la liste.', true);
            $('ressource-objet-input')?.focus();
            return;
        }

        const fd = new FormData(form);

        try {
            const resp = await fetch(form.action, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken(),
                },
                body: fd,
            });
            const data = await resp.json();

            if (data.success) {
                closeModal();
                showToast(data.message || 'Enregistré.');
                setTimeout(() => window.location.reload(), 600);
            } else {
                showToast(data.message || 'Erreur de validation.', true);
                console.warn('Erreurs:', data.errors);
            }
        } catch (err) {
            console.error('Erreur soumission:', err);
            showToast('Erreur réseau.', true);
        }
    });

    // ------------------------------------------------------------
    // Suppression
    // ------------------------------------------------------------
    document.querySelectorAll('[data-delete-ressource-button]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const id = btn.dataset.id;
            const designation = btn.dataset.designation;
            if (!confirm(`Retirer « ${designation} » du projet ?`)) return;

            try {
                const resp = await fetch(urlFromTemplate(DELETE_TEMPLATE, id), {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken(),
                    },
                });
                const data = await resp.json();
                if (data.success) {
                    showToast(data.message || 'Ressource retirée.');
                    setTimeout(() => window.location.reload(), 600);
                } else {
                    showToast(data.message || 'Erreur.', true);
                }
            } catch (err) {
                console.error('Erreur suppression:', err);
                showToast('Erreur réseau.', true);
            }
        });
    });

    // ------------------------------------------------------------
    // Onglets de la page
    // ------------------------------------------------------------
    document.querySelectorAll('.ressource-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const code = tab.dataset.code;

            document.querySelectorAll('.ressource-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.ressource-tab-panel').forEach(p => p.classList.add('hidden'));
            tab.classList.add('active');
            document.getElementById(`tab-${code}`)?.classList.remove('hidden');

            // Sync URL (permet de partager le lien + survit au refresh)
            const url = new URL(window.location.href);
            url.searchParams.set('type', code);
            window.history.replaceState({}, '', url);
        });
    });

    // ------------------------------------------------------------
    // Fermeture
    // ------------------------------------------------------------
    document.querySelectorAll('[data-close-modal]').forEach(b =>
        b.addEventListener('click', closeModal)
    );
    backdrop?.addEventListener('click', closeModal);
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeModal();
    });
})();