(function () {
    'use strict';
    if (window.GoPlanFullscreen) return;
    window.GoPlanFullscreen = true;
    const workspaceSelector = '[data-goplan-inline], [data-goplan-gantt], [data-bordereau-editor], [data-attachement-editor], [data-ca-editor], [data-fiche-controle-editor]';
    let pending = false;
    let revealingFields = false;

    function fullscreenTarget(root) {
        return root.hasAttribute('data-fullscreen-document') ? document.documentElement : root;
    }

    document.addEventListener('invalid', async event => {
        const root = event.target.closest(workspaceSelector);
        if (!root?.hasAttribute('data-workspace-fullscreen')
            || !event.target.closest('[data-fullscreen-fields]')) return;
        event.preventDefault();
        if (revealingFields) return;
        revealingFields = true;
        try {
            await document.exitFullscreen();
            event.target.focus();
            event.target.reportValidity();
        } catch (error) {
            console.error('Impossible de réafficher les champs invalides.', error);
            const errorBox = root.querySelector('[data-planning-fullscreen-error]');
            errorBox.textContent = `Impossible de réafficher les champs. ${error.message}`;
            errorBox.hidden = false;
        } finally {
            revealingFields = false;
        }
    }, true);

    document.addEventListener('fullscreenchange', () => {
        document.querySelectorAll('[data-planning-fullscreen]').forEach(button => {
            const root = button.closest(workspaceSelector);
            if (!root) return;
            const active = document.fullscreenElement === fullscreenTarget(root);
            root.toggleAttribute('data-workspace-fullscreen', active);
            const label = active ? 'Quitter le plein écran' : 'Passer en plein écran';
            button.setAttribute('aria-pressed', String(active));
            button.setAttribute('aria-label', label);
            button.title = `${label} (Échap pour quitter)`;
            button.querySelector('i').classList.toggle('fa-expand', !active);
            button.querySelector('i').classList.toggle('fa-compress', active);
        });
    });

    document.addEventListener('click', async event => {
        const button = event.target.closest('[data-planning-fullscreen]');
        if (!button || pending) return;
        const root = button.closest(workspaceSelector);
        if (!root) return;
        const target = fullscreenTarget(root);
        const errorBox = root.querySelector('[data-planning-fullscreen-error]');
        errorBox.hidden = true;
        pending = true;
        button.disabled = true;
        try {
            if (document.fullscreenElement === target) {
                await document.exitFullscreen();
            } else {
                if (!target.requestFullscreen) {
                    throw new Error('Le plein écran n’est pas disponible dans ce navigateur.');
                }
                await target.requestFullscreen();
            }
        } catch (error) {
            console.error('[GoPlan] Plein écran impossible.', error);
            errorBox.textContent = `Impossible de changer le mode plein écran. ${error.message}`;
            errorBox.hidden = false;
        } finally {
            pending = false;
            button.disabled = false;
        }
    });
})();
