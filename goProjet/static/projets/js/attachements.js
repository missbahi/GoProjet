/* static/projets/js/attachements.js
   Liste des attachements : recherche, tri, traçabilité, suppression.
   Délégation sur document : fonctionne après chaque swap HTMX sans réinitialisation. */
(function () {
    'use strict';

    if (window.__attachementsInitialized) return;
    window.__attachementsInitialized = true;

    const TRACE_LABELS = {
        validateur: 'Validé par',
        date_validation: 'Date',
        commentaires: 'Remarques',
        motifs_rejet: 'Motif du refus',
    };

    function normalize(value) {
        return (value || '').toString().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    }

    // ── Recherche ──────────────────────────────────────────────
    function filterRows(input) {
        const table = document.getElementById('attachment-table');
        if (!table) return;
        const term = normalize(input.value.trim());
        let visible = 0;
        table.querySelectorAll('tbody tr').forEach(row => {
            const match = !term || normalize(row.textContent).includes(term);
            row.hidden = !match;
            if (match) visible += 1;
        });
        const count = document.getElementById('attachment-count');
        if (count) count.textContent = visible;
        const empty = document.getElementById('attachment-search-empty');
        if (empty) empty.hidden = visible > 0;
    }

    // ── Tri ────────────────────────────────────────────────────
    function sortTable(header) {
        const table = header.closest('table');
        const tbody = table && table.tBodies[0];
        if (!tbody) return;

        const field = header.dataset.sort;
        const descending = header.classList.contains('active') && !header.classList.contains('desc');
        table.querySelectorAll('th.sortable').forEach(th => th.classList.remove('active', 'desc'));
        header.classList.add('active');
        header.classList.toggle('desc', descending);

        const key = 'sort' + field.charAt(0).toUpperCase() + field.slice(1);
        const numeric = field === 'montant';
        const rows = Array.from(tbody.rows);
        rows.sort((a, b) => {
            const va = a.dataset[key] || '';
            const vb = b.dataset[key] || '';
            const result = numeric
                ? (parseFloat(va) || 0) - (parseFloat(vb) || 0)
                : va.localeCompare(vb, 'fr', { sensitivity: 'base' });
            return descending ? -result : result;
        });
        rows.forEach(row => tbody.appendChild(row));
    }

    // ── Dialogues ──────────────────────────────────────────────
    function openDialog(dialog) {
        dialog.hidden = false;
        dialog.classList.add('is-open');
        document.body.style.overflow = 'hidden';
    }

    function closeDialog(dialog) {
        if (!dialog || dialog.hidden) return;
        dialog.hidden = true;
        dialog.classList.remove('is-open');
        if (!document.querySelector('.attachment-dialog.is-open')) {
            document.body.style.overflow = '';
        }
    }

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function renderTrace(content, data) {
        content.replaceChildren(el('p', '', `Attachement : ${data.attachement}`));

        if (!data.validations || !data.validations.length) {
            content.appendChild(el('p', 'attachment-trace-card', 'Aucune validation n’a encore été enregistrée.'));
            return;
        }

        data.validations.forEach(validation => {
            const card = el('section', 'attachment-trace-card');
            card.appendChild(el('h3', '', `${validation.type} - ${validation.statut}`));

            const details = el('dl');
            Object.keys(TRACE_LABELS).forEach(key => {
                if (!validation[key]) return;
                details.append(el('dt', '', TRACE_LABELS[key]), el('dd', '', validation[key]));
            });
            card.appendChild(details);

            if (validation.document_url) {
                const docs = el('p', 'attachment-trace-docs');
                const view = el('a', '', 'Consulter');
                view.href = `${validation.document_url}?download=false`;
                view.target = '_blank';
                view.rel = 'noopener';
                const download = el('a', '', 'Télécharger');
                download.href = `${validation.document_url}?download=true`;
                download.target = '_blank';
                download.rel = 'noopener';
                docs.append(el('span', '', validation.document_nom || 'Document'), view, download);
                card.appendChild(docs);
            }

            if (validation.etapes && validation.etapes.length) {
                const steps = el('ul', 'attachment-trace-steps');
                validation.etapes.forEach(etape => {
                    const who = etape.validateur ? ` (${etape.validateur})` : '';
                    const note = etape.commentaire ? ` : ${etape.commentaire}` : '';
                    steps.appendChild(el('li', '', `${etape.nom} - ${etape.statut}${who}${note}`));
                });
                card.appendChild(steps);
            }
            content.appendChild(card);
        });
    }

    async function openTrace(url) {
        const dialog = document.getElementById('attachment-trace-dialog');
        const content = document.getElementById('attachment-trace-content');
        if (!dialog || !content) return;
        content.textContent = 'Chargement de la traçabilité…';
        openDialog(dialog);
        try {
            const response = await fetch(url, { headers: { Accept: 'application/json' } });
            if (!response.ok) throw new Error('Impossible de charger la traçabilité.');
            renderTrace(content, await response.json());
        } catch (error) {
            content.textContent = error.message;
            if (typeof window.showErrorMessage === 'function') window.showErrorMessage(error.message);
        }
    }

    function openDelete(button) {
        const dialog = document.getElementById('attachment-delete-dialog');
        const form = document.getElementById('attachment-delete-form');
        const label = document.getElementById('attachment-delete-label');
        if (!dialog || !form) return;
        form.action = button.dataset.attachmentDelete;
        if (label) label.textContent = button.dataset.attachmentLabel || '';
        openDialog(dialog);
    }

    // ── Délégation ─────────────────────────────────────────────
    document.addEventListener('input', event => {
        if (event.target.id === 'attachment-search-input') filterRows(event.target);
    });

    document.addEventListener('click', event => {
        const target = event.target;

        const header = target.closest('#attachment-table th.sortable');
        if (header) { sortTable(header); return; }

        const trace = target.closest('[data-attachment-trace]');
        if (trace) { openTrace(trace.dataset.attachmentTrace); return; }

        const remove = target.closest('[data-attachment-delete]');
        if (remove) { openDelete(remove); return; }

        if (target.closest('[data-attachment-dialog-close]')) {
            closeDialog(target.closest('.attachment-dialog'));
            return;
        }

        if (target.classList.contains('attachment-dialog')) closeDialog(target);
    });

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            document.querySelectorAll('.attachment-dialog.is-open').forEach(closeDialog);
        }
    });

    // Un swap HTMX remplace la page : ne pas laisser le défilement bloqué.
    document.addEventListener('htmx:beforeSwap', event => {
        if (event.detail.target && event.detail.target.id === 'main-content'
            && document.querySelector('.attachment-dialog.is-open')) {
            document.body.style.overflow = '';
        }
    });
})();
