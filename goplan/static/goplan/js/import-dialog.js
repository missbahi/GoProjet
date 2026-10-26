(function () {
    'use strict';
    if (window.GoPlanXmlImport) return;
    const dialog = document.getElementById('xml-import-dialog');
    if (!dialog || typeof dialog.showModal !== 'function') return;
    const content = dialog.querySelector('[data-xml-import-content]');
    const status = dialog.querySelector('[data-xml-import-status]');
    const errorBox = dialog.querySelector('[data-xml-import-error]');
    let busy = false;
    let trigger = null;

    function canOpen() {
        if (document.querySelector('#gantt-task-form[data-dirty="true"], #gantt-task-form[aria-busy="true"], #gantt-appearance-form[aria-busy="true"]')) {
            window.showNotification?.('Enregistrez les modifications du Gantt et attendez la fin de l’enregistrement avant d’importer un XML.', 'warning');
            return false;
        }
        return document.dispatchEvent(new CustomEvent('goplan:before-import', { cancelable: true }));
    }

    async function load(url, body) {
        if (busy) return;
        busy = true;
        dialog.setAttribute('aria-busy', 'true');
        status.textContent = body ? 'Traitement du fichier XML…' : 'Chargement…';
        errorBox.hidden = true;
        const controls = Array.from(dialog.querySelectorAll('button,input,select,textarea'))
            .map(control => [control, control.disabled]);
        controls.forEach(([control]) => { control.disabled = true; });
        try {
            const response = await fetch(url, {
                method: body ? 'POST' : 'GET',
                body,
                credentials: 'same-origin',
                headers: { 'X-GoPlan-Dialog': 'xml-import', 'Accept': 'application/json' },
            });
            if (response.redirected) throw new Error('Session expirée ou accès refusé. Rechargez la page et reconnectez-vous.');
            if (!response.ok) throw new Error(`Importation indisponible (HTTP ${response.status}).`);
            if (!response.headers.get('content-type')?.includes('application/json')) {
                throw new Error('Réponse inattendue du serveur. Rechargez la page avant de réessayer.');
            }
            const result = await response.json();
            if (result.redirect) {
                const destination = new URL(result.redirect, window.location.href);
                if (destination.origin !== window.location.origin) throw new Error('Destination d’importation invalide.');
                window.location.assign(destination.href);
                return;
            }
            if (typeof result.html !== 'string') throw new Error('Formulaire d’importation absent de la réponse.');
            content.innerHTML = result.html;
            dialog.setAttribute('aria-labelledby', 'xml-import-title');
            content.querySelector('#xml-import-title').focus();
        } catch (error) {
            console.error('[GoPlan] Importation XML impossible.', error);
            errorBox.textContent = error.message;
            errorBox.hidden = false;
        } finally {
            busy = false;
            dialog.setAttribute('aria-busy', 'false');
            status.textContent = '';
            controls.forEach(([control, disabled]) => { control.disabled = disabled; });
        }
    }

    document.addEventListener('click', event => {
        const link = event.target.closest?.('a[data-xml-import]');
        if (!link || event.defaultPrevented || event.button !== 0
            || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        if (dialog.open || !canOpen()) return;
        trigger = link;
        content.replaceChildren();
        dialog.removeAttribute('aria-labelledby');
        dialog.showModal();
        load(link.href);
    });

    dialog.addEventListener('click', event => {
        if (!event.target.closest?.('[data-xml-import-cancel]')) return;
        event.preventDefault();
        if (!busy) dialog.close();
    });
    dialog.addEventListener('cancel', event => {
        if (busy) event.preventDefault();
    });
    dialog.addEventListener('close', () => {
        content.replaceChildren();
        if (trigger?.isConnected) trigger.focus();
        trigger = null;
    });
    dialog.addEventListener('submit', event => {
        const form = event.target.closest?.('[data-xml-import-form]');
        if (!form) return;
        event.preventDefault();
        if (busy || !form.reportValidity() || !canOpen()) return;
        load(form.action, new FormData(form));
    });
    window.GoPlanXmlImport = { canOpen };
})();
