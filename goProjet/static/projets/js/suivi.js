(function () {
    'use strict';
    if (window.__suiviInitialized) return;
    window.__suiviInitialized = true;

    const selectedFiles = new WeakMap();
    const maxFileSize = 10 * 1024 * 1024;

    function renderFiles(form, files, focusIndex = null) {
        selectedFiles.set(form, files);
        const input = form.querySelector('[data-suivi-files]');
        const transfer = new DataTransfer();
        files.forEach(file => transfer.items.add(file));
        input.files = transfer.files;
        const invalid = files.filter(file => file.size > maxFileSize);
        const message = invalid.length
            ? `Maximum 10 Mo par fichier : ${invalid.map(file => file.name).join(', ')}.`
            : '';
        input.setCustomValidity(message);
        const error = form.querySelector('[data-suivi-files-error]');
        error.textContent = message;
        error.hidden = !message;
        const list = form.querySelector('[data-suivi-files-list]');
        list.replaceChildren();
        const template = form.querySelector('[data-suivi-file-row]');
        files.forEach((file, index) => {
            const row = template.content.firstElementChild.cloneNode(true);
            row.dataset.fileIndex = String(index);
            row.querySelector('[data-suivi-file-name]').textContent = file.name;
            row.querySelector('[data-suivi-file-size]').textContent =
                `${(file.size / (1024 * 1024)).toLocaleString('fr-FR', { maximumFractionDigits: 2 })} Mo`;
            row.querySelector('[data-suivi-file-replace]').setAttribute('aria-label', `Remplacer ${file.name}`);
            row.querySelector('[data-suivi-file-remove]').setAttribute('aria-label', `Supprimer ${file.name} de la sélection`);
            list.appendChild(row);
        });
        if (focusIndex !== null) {
            const rows = list.querySelectorAll('[data-file-index]');
            const row = rows[Math.min(focusIndex, rows.length - 1)];
            if (row) row.querySelector('[data-suivi-file-replace]').focus();
            else input.focus();
        }
    }

    document.addEventListener('change', event => {
        const input = event.target;
        if (!input.matches('[data-suivi-files], [data-suivi-file-replacement]')) return;
        const form = input.closest('form');
        if (form.dataset.submitting === 'true' || form.dataset.saved === 'true') return;
        const incoming = Array.from(input.files);
        if (!incoming.length) return;
        const files = [...(selectedFiles.get(form) || [])];
        if (input.matches('[data-suivi-file-replacement]')) {
            const index = Number(input.closest('[data-file-index]').dataset.fileIndex);
            files[index] = incoming[0];
            renderFiles(form, files, index);
        } else {
            renderFiles(form, [...files, ...incoming]);
        }
    });

    function setFormVisible(visible) {
        const panel = document.getElementById('suiviFormContainer');
        const toggle = document.getElementById('toggleSuiviForm');
        if (!panel || !toggle) return;
        panel.classList.toggle('hidden', !visible);
        toggle.setAttribute('aria-expanded', String(visible));
        if (visible) {
            panel.querySelector('input:not([type="hidden"])')?.focus();
            panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
            toggle.focus();
        }
    }

    document.addEventListener('click', event => {
        const fileAction = event.target.closest('[data-suivi-file-replace], [data-suivi-file-remove]');
        if (fileAction) {
            const form = fileAction.closest('form');
            if (form.dataset.submitting === 'true' || form.dataset.saved === 'true') return;
            const row = fileAction.closest('[data-file-index]');
            if (fileAction.matches('[data-suivi-file-replace]')) {
                row.querySelector('[data-suivi-file-replacement]').click();
            } else {
                const files = [...(selectedFiles.get(form) || [])];
                const index = Number(row.dataset.fileIndex);
                files.splice(index, 1);
                renderFiles(form, files, index);
            }
        } else if (event.target.closest('#toggleSuiviForm')) {
            document.getElementById('suiviEditContainer')?.replaceChildren();
            const panel = document.getElementById('suiviFormContainer');
            if (panel) setFormVisible(panel.classList.contains('hidden'));
        } else if (event.target.closest('#closeSuiviForm, #cancelSuiviForm')) {
            setFormVisible(false);
        } else if (event.target.closest('[data-cancel-suivi-edit]')) {
            const container = document.getElementById('suiviEditContainer');
            if (!container) return;
            event.preventDefault();
            const id = container.querySelector('[data-editing-suivi]')?.dataset.editingSuivi;
            container.replaceChildren();
            document.querySelector(`[data-edit-suivi="${id}"]`)?.focus();
        }
    });

    document.body.addEventListener('htmx:afterSwap', event => {
        if (event.detail.target.id !== 'suiviEditContainer') return;
        const form = event.detail.target.querySelector('#editSuiviForm');
        if (!form) return;
        setFormVisible(false);
        form.querySelector('input:not([type="hidden"])')?.focus();
        event.detail.target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });

    document.addEventListener('submit', async event => {
        const form = event.target;
        if (form.matches('form[data-suivi-delete]')) {
            if (!confirm('Supprimer ce suivi et tous ses fichiers ?')) event.preventDefault();
            return;
        }
        if (form.matches('form[data-suivi-file-delete]')) {
            if (!confirm('Supprimer ce fichier joint ?')) event.preventDefault();
            return;
        }
        if (!form.matches('form#suiviForm, form#editSuiviForm')) return;
        event.preventDefault();
        if (form.dataset.submitting === 'true' || form.dataset.saved === 'true' || !form.reportValidity()) return;
        const action = event.submitter?.value || 'save_and_close';
        const summary = form.querySelector('[data-suivi-errors]');
        summary.replaceChildren();
        summary.hidden = true;
        form.querySelectorAll('[aria-invalid]').forEach(input => input.removeAttribute('aria-invalid'));
        const data = new FormData(form);
        data.set('action', action);
        const buttons = form.querySelectorAll('button');
        const fileInputs = form.querySelectorAll('input[type="file"]');
        form.dataset.submitting = 'true';
        buttons.forEach(button => { button.disabled = true; });
        fileInputs.forEach(input => { input.disabled = true; });
        try {
            const response = await fetch(form.getAttribute('action'), {
                method: 'POST', body: data,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value,
                },
            });
            if (!(response.headers.get('content-type') || '').includes('application/json')) {
                throw new Error(`HTTP ${response.status}`);
            }
            const result = await response.json();
            if (!response.ok || !result.success) {
                if (result.saved) {
                    form.dataset.saved = 'true';
                    const recovery = document.createElement('a');
                    recovery.href = result.url;
                    recovery.className = 'app-btn-secondary mt-3';
                    recovery.textContent = 'Gérer les fichiers du suivi enregistré';
                    recovery.setAttribute('hx-boost', 'false');
                    summary.appendChild(recovery);
                }
                for (const [name, errors] of Object.entries(result.errors || {})) {
                    form.elements.namedItem(name)?.setAttribute('aria-invalid', 'true');
                    errors.forEach(error => {
                        const line = document.createElement('p');
                        line.textContent = error.message;
                        summary.appendChild(line);
                    });
                }
                throw new Error(result.message || `HTTP ${response.status}`);
            }
            form.dataset.saved = 'true';
            if (result.open_files || !window.htmx
                || (form.matches('form#editSuiviForm') && !document.getElementById('suiviEditContainer'))) {
                window.location.assign(result.url);
            } else {
                await window.htmx.ajax('GET', result.url, { target: '#main-content', swap: 'innerHTML' });
                window.showSuccessMessage?.(result.message);
            }
        } catch (error) {
            console.error('[suivi] Enregistrement impossible', error);
            const line = document.createElement('p');
            line.textContent = form.dataset.saved === 'true'
                ? `Suivi enregistré : ${error.message}. Ne soumettez pas à nouveau ce formulaire.`
                : `Enregistrement impossible : ${error.message}`;
            summary.appendChild(line);
            summary.hidden = false;
            summary.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } finally {
            form.dataset.submitting = 'false';
            buttons.forEach(button => {
                button.disabled = form.dataset.saved === 'true'
                    && (button.type === 'submit' || button.matches('[data-suivi-file-replace], [data-suivi-file-remove]'));
            });
            fileInputs.forEach(input => { input.disabled = form.dataset.saved === 'true'; });
        }
    });
})();
