/**
 * projets/js/ressource-modal.js
 *
 * Contrôleur générique du modal de ressource affectée.
 * Lit les data-* du bouton déclencheur et les injecte dans le modal.
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
    // const backdrop = document.querySelector('[data-modal-backdrop]');

    const $ = (id) => document.getElementById(id);

    // ---------- Helpers ----------

    function urlFromTemplate(tpl, id) {
        return tpl.replace(/0\/?$/, `${id}/`);
    }

    function csrfToken() {
        return form.querySelector('[name=csrfmiddlewaretoken]')?.value
            || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
    }

    function openModal() {
        // backdrop?.removeAttribute('hidden');
        modal?.removeAttribute('hidden');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        modal?.setAttribute('hidden', '');
        // backdrop?.setAttribute('hidden', '');
        document.body.style.overflow = '';
    }

    function showToast(msg, isError = false) {
        const el = document.createElement('div');
        el.textContent = msg;
        el.style.cssText = `
            position: fixed; bottom: 1rem; right: 1rem; z-index: 9999;
            padding: 0.75rem 1rem; border-radius: 6px;
            background: ${isError ? '#dc2626' : '#16a34a'};
            color: white; box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            font-size: 0.875rem;
        `;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 3500);
    }

    // ---------- Chargement dynamique ----------

    async function chargerOptions(code, selectEl, selectedId = null) {
        selectEl.disabled = true;
        selectEl.innerHTML = '<option value="">Chargement…</option>';
        try {
            const resp = await fetch(`${API_OPTIONS}?code=${encodeURIComponent(code)}`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            const data = await resp.json();
            const options = data.options || [];
            selectEl.innerHTML = '<option value="">— Sélectionner —</option>'
                + options.map(o => {
                    const sel = (selectedId && String(o.id) === String(selectedId)) ? ' selected' : '';
                    const label = o.unite ? `${o.label} (${o.unite})` : o.label;
                    return `<option value="${o.id}" data-unite="${o.unite}" data-prix="${o.prix}"${sel}>${label}</option>`;
                }).join('');
            selectEl.disabled = false;
        } catch (e) {
            selectEl.innerHTML = '<option value="">Erreur de chargement</option>';
        }
    }

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
            selectAtelier.innerHTML = '<option value="">Erreur</option>';
        }
    }

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

    // ---------- Ouverture du modal (add OU edit) ----------

    document.querySelectorAll('[data-open-ressource-modal]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const mode            = btn.dataset.mode || 'add';
            const categorieId     = btn.dataset.categorieId;
            const categorieCode   = btn.dataset.categorieCode;
            const categorieLabel  = btn.dataset.categorieLabel || '—';
            const ressourceId     = btn.dataset.ressourceId;

            // --- Injection du type (invisible) ---
            $('ressource-categorie').value = categorieId || '';
            $('ressource-categorie-label').textContent = categorieLabel;

            // --- Titre et libellé du bouton ---
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
                // Date de début = aujourd'hui
                $('ressource-debut').value = new Date().toISOString().slice(0, 10);
            }

            // --- Reset des selects ---
            const selectObj = $('ressource-objet');
            selectObj.innerHTML = '<option value="">Chargement…</option>';
            selectObj.disabled = true;

            // --- Chargement des ressources ---
            const objetId = mode === 'edit' ? btn.dataset.objetId : null;
            await chargerOptions(categorieCode, selectObj, objetId);

            // --- Atelier (uniquement MATERIEL) ---
            toggleAtelier(categorieCode);
            if (categorieCode === 'MATERIEL') {
                const atelierId = mode === 'edit' ? btn.dataset.atelierId : null;
                await chargerAteliers(atelierId);
            }

            // --- Pré-remplissage si édition ---
            if (mode === 'edit') {
                $('ressource-debut').value      = btn.dataset.dateDebut || '';
                $('ressource-fin').value        = btn.dataset.dateFin || '';
                $('ressource-tarif').value      = btn.dataset.tarif || '0.00';
                $('ressource-commentaire').value = btn.dataset.commentaire || '';
            } else {
                $('ressource-fin').value        = '';
                $('ressource-tarif').value      = '0.00';
                $('ressource-commentaire').value = '';
            }

            openModal();
        });
    });

    // ---------- Soumission ----------

    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
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
            showToast('Erreur réseau.', true);
        }
    });

    // ---------- Suppression ----------

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
                showToast('Erreur réseau.', true);
            }
        });
    });

    // ---------- Onglets ----------

    document.querySelectorAll('.ressource-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.ressource-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.ressource-tab-panel').forEach(p => p.classList.add('hidden'));
            tab.classList.add('active');
            const panel = document.getElementById(`tab-${tab.dataset.code}`);
            panel?.classList.remove('hidden');
        });
    });

    // ---------- Fermeture ----------

    document.querySelectorAll('[data-close-modal]').forEach(b =>
        b.addEventListener('click', closeModal)
    );
    // backdrop?.addEventListener('click', closeModal);
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeModal();
    });
})();