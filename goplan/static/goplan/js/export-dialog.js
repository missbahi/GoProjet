(function () {
    'use strict';
    if (window.GoPlanXmlExport) return;
    const dialog = document.getElementById('xml-export-dialog');
    if (!dialog || typeof dialog.showModal !== 'function') return;
    const status = dialog.querySelector('[data-xml-export-status]');
    const errorBox = dialog.querySelector('[data-xml-export-error]');
    const download = dialog.querySelector('[data-xml-export-download]');
    const label = dialog.querySelector('[data-xml-export-label]');
    let trigger = null;
    let busy = false;
    let downloaded = false;

    function canExport() {
        if (document.querySelector('#gantt-task-form[data-dirty="true"], #gantt-task-form[aria-busy="true"], #gantt-appearance-form[aria-busy="true"]')) {
            window.showNotification?.('Enregistrez les modifications du Gantt et attendez la fin de l’enregistrement avant d’exporter un XML.', 'warning');
            return false;
        }
        return document.dispatchEvent(new CustomEvent('goplan:before-export', { cancelable: true }));
    }

    document.addEventListener('click', event => {
        const link = event.target.closest?.('a[data-xml-export]');
        if (!link || event.defaultPrevented || event.button !== 0
            || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        if (dialog.open || !canExport()) return;
        trigger = link;
        downloaded = false;
        download.disabled = false;
        label.textContent = 'Télécharger XML';
        status.textContent = '';
        errorBox.hidden = true;
        dialog.querySelector('[data-xml-export-name]').textContent = link.dataset.planName;
        dialog.querySelector('[data-xml-export-filename]').textContent = link.dataset.exportFilename;
        dialog.showModal();
    });

    dialog.addEventListener('submit', async event => {
        event.preventDefault();
        if (busy || downloaded || !trigger || !canExport()) return;
        busy = true;
        download.disabled = true;
        dialog.setAttribute('aria-busy', 'true');
        label.textContent = 'Génération…';
        status.textContent = 'Génération du fichier XML…';
        errorBox.hidden = true;
        try {
            const response = await fetch(trigger.href, {
                credentials: 'same-origin', cache: 'no-store',
                headers: { 'Accept': 'application/xml' },
            });
            if (response.redirected) throw new Error('Session expirée ou accès refusé. Rechargez la page et reconnectez-vous.');
            if (!response.ok) throw new Error(`Exportation indisponible (HTTP ${response.status}).`);
            if (!/^application\/xml(?:;|$)/i.test(response.headers.get('content-type') || '')) {
                throw new Error('Le serveur n’a pas renvoyé un fichier XML. Rechargez la page avant de réessayer.');
            }
            const blob = await response.blob();
            if (!blob.size) throw new Error('Le fichier XML reçu est vide.');
            const disposition = response.headers.get('content-disposition') || '';
            const filename = disposition.match(/filename="([^"]+)"/i)?.[1] || trigger.dataset.exportFilename;
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            try {
                anchor.href = url;
                anchor.download = filename;
                anchor.hidden = true;
                document.body.appendChild(anchor);
                anchor.click();
            } finally {
                anchor.remove();
                // Laisser au navigateur le temps de prendre en charge le téléchargement.
                setTimeout(() => URL.revokeObjectURL(url), 1000);
            }
            downloaded = true;
            status.textContent = 'Téléchargement lancé.';
            label.textContent = 'Téléchargement lancé';
        } catch (error) {
            console.error('[GoPlan] Exportation XML impossible.', error);
            errorBox.textContent = error.message;
            errorBox.hidden = false;
            status.textContent = '';
            label.textContent = 'Réessayer';
        } finally {
            busy = false;
            download.disabled = downloaded;
            dialog.setAttribute('aria-busy', 'false');
        }
    });
    dialog.addEventListener('click', event => {
        if (!event.target.closest?.('[data-xml-export-cancel]')) return;
        event.preventDefault();
        if (!busy) dialog.close();
    });
    dialog.addEventListener('cancel', event => {
        if (busy) event.preventDefault();
    });
    dialog.addEventListener('close', () => {
        if (trigger?.isConnected) trigger.focus();
        trigger = null;
    });
    window.GoPlanXmlExport = { canExport };
})();
