(() => {
    if (window.__caListeInitialized) return;
    window.__caListeInitialized = true;
    let busy = false;
    document.addEventListener('click', async event => {
        const button = event.target.closest('.ca-list-action');
        if (!button) return;
        event.preventDefault();
        if (busy) return;
        const periode = button.dataset.periode;
        const questions = {
            valider: `Valider le CA ${periode} ?\n\nLa rubrique Travaux réalisés des situations en brouillon sera remplacée par le montant du CA. Les autres recettes seront conservées.`,
            devalider: `Remettre le CA ${periode} en brouillon ?\n\nUne situation liée ne pourra pas être validée avant la revalidation du CA.`,
            supprimer: `Supprimer le CA ${periode} ?\n\nToutes ses lignes seront supprimées. Cette action est irréversible.`,
        };
        if (!window.confirm(questions[button.dataset.action])) return;
        busy = true;
        button.disabled = true;
        const errorBox = document.getElementById('ca-list-error');
        errorBox.hidden = true;
        try {
            const response = await fetch(button.dataset.url, {
                method: 'POST', credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': document.querySelector('[name="csrfmiddlewaretoken"]')?.value || '',
                },
            });
            if (!(response.headers.get('content-type') || '').includes('application/json')) {
                throw new Error(`Réponse inattendue (HTTP ${response.status}). Rechargez la page.`);
            }
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(result.message || 'Action CA refusée.');
            window.showSuccessMessage?.(result.message);
            if (window.htmx) {
                await window.htmx.ajax('GET', window.location.href, { target: '#main-content', swap: 'innerHTML' });
            } else {
                window.location.reload();
            }
        } catch (error) {
            errorBox.textContent = error.message;
            errorBox.hidden = false;
            window.showErrorMessage?.(error.message);
        } finally {
            busy = false;
            button.disabled = false;
        }
    });
})();
