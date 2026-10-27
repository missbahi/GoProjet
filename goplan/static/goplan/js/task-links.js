(function () {
    'use strict';
    if (window.GoPlanTaskLinks) return;

    window.GoPlanTaskLinks = function (root, { getData, csrfToken, setBusy, onSaved }) {
        const dialog = root.querySelector('#gantt-link-dialog');
        const form = dialog.querySelector('form');
        const predecessor = form.querySelector('#gantt-link-predecessor');
        const type = form.querySelector('#gantt-link-type');
        const lag = form.querySelector('#gantt-link-lag');
        const errors = form.querySelector('#gantt-link-errors');
        let activeId = '';
        let busy = false;

        function restoreControls() {
            form.querySelectorAll('button,input,select').forEach(el => { el.disabled = false; });
            const task = getData().editable.find(task => task.id === activeId);
            const empty = !task.possible_predecessors.length;
            predecessor.disabled = empty;
            form.querySelector('[type="submit"]').disabled = empty;
            form.querySelectorAll('[data-incompatible-link]').forEach(el => { el.disabled = true; });
        }

        function populate() {
            const data = getData();
            const editable = new Map(data.editable.map(task => [task.id, task]));
            const task = editable.get(activeId);
            const possible = new Set(task.possible_predecessors);
            form.querySelector('#gantt-link-title').textContent = `Liaisons de ${task.label}`;
            predecessor.replaceChildren(new Option('— Choisir un prédécesseur —', ''));
            data.editable.filter(task => possible.has(task.id)).forEach(task => {
                predecessor.add(new Option(task.label, task.id));
            });
            type.value = 'FS';
            lag.value = '0';
            errors.textContent = possible.size ? '' : 'Aucun prédécesseur compatible disponible pour cette tâche.';
            const list = form.querySelector('#gantt-link-list');
            list.replaceChildren();
            data.links.filter(link => link.successor === activeId).forEach(link => {
                const row = document.createElement('li');
                const label = document.createElement('span');
                label.textContent = `${editable.get(link.predecessor)?.label || 'Tâche hors planning'} — ${link.type} (${link.lag >= 0 ? '+' : ''}${link.lag} j ouvrés)`;
                const modify = document.createElement('button');
                modify.type = 'button';
                // modify.className = 'goplan-modify-btn';
                modify.textContent = 'Modifier';
                if (!possible.has(link.predecessor)) {
                    modify.dataset.incompatibleLink = '';
                    modify.title = 'Liaison devenue incompatible : supprimez-la.';
                }
                modify.addEventListener('click', () => {
                    predecessor.value = link.predecessor;
                    type.value = link.type;
                    lag.value = String(link.lag);
                });
                const remove = document.createElement('button');
                remove.type = 'button';
                // remove.className = 'goplan-delete-btn';
                remove.textContent = 'Supprimer';
                remove.setAttribute('aria-label', `Supprimer la liaison depuis ${editable.get(link.predecessor)?.label}`);
                remove.addEventListener('click', () => persist('delete', link.predecessor));

                const actions = document.createElement('div');
                actions.className = 'gantt-link-actions';
                modify.classList.add('gantt-link-btn', 'gantt-link-btn-edit');
                remove.classList.add('gantt-link-btn', 'gantt-link-btn-delete');
                actions.append(modify, remove);
                row.append(label, actions);

                list.appendChild(row);
            });
            if (!list.children.length) list.textContent = 'Aucun prédécesseur.';
            restoreControls();
        }

        async function persist(action, predecessorId = predecessor.value) {
            if (busy || (action === 'save' && (predecessor.disabled || !form.reportValidity()))) return;
            const payload = new FormData();
            Object.entries({
                action, predecessor: predecessorId, successor: activeId,
                type: type.value, lag: lag.value, revision: getData().revision,
            }).forEach(([key, value]) => payload.set(key, value));
            busy = true;
            setBusy(true);
            form.querySelectorAll('button,input,select').forEach(el => { el.disabled = true; });
            errors.textContent = '';
            try {
                const response = await fetch(form.action, {
                    method: 'POST', body: payload,
                    headers: { 'X-CSRFToken': csrfToken(), 'Accept': 'application/json' },
                });
                if (response.redirected) throw new Error('Session expirée : reconnectez-vous.');
                if (!response.headers.get('content-type')?.includes('application/json')) {
                    throw new Error(`Enregistrement de la liaison refusé (HTTP ${response.status}).`);
                }
                const result = await response.json();
                if (!response.ok) {
                    errors.textContent = Object.values(result.errors).flat().join(' ');
                    return;
                }
                onSaved(result, action);
                populate();
            } catch (error) {
                console.error('[GoPlan] Liaison', error);
                errors.textContent = error.message;
            } finally {
                busy = false;
                setBusy(false);
                restoreControls();
            }
        }

        form.addEventListener('submit', event => { event.preventDefault(); persist('save'); });
        const closeBtn = form.querySelector('#gantt-link-close');
        closeBtn?.addEventListener('click', () => dialog.close());
        dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
        return {
            open(id) {
                if (busy) return;
                activeId = id;
                populate();
                dialog.showModal();
            },
        };
    };
    window.GoPlanTaskLinks.describe = function (data, taskId) {
        const editable = new Map(data.editable.map(task => [task.id, task]));
        const types = { SS: 'DD', SF: 'DF', FS: 'FD', FF: 'FF' };
        return data.links.filter(link => link.successor === taskId).map(link => {
            const task = editable.get(link.predecessor);
            const label = task ? task.values.code || task.label : 'Tâche hors planning';
            const lag = link.lag ? ` ${link.lag > 0 ? '+' : ''}${link.lag} j` : '';
            return `${label} · ${types[link.type] || link.type}${lag}`;
        }).join(' ; ') || '—';
    };
})();
