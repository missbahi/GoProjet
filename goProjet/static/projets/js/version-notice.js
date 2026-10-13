(function () {
    'use strict';
    const btn = document.getElementById('versionNoticeClose');
    if (!btn) return;

    btn.addEventListener('click', async () => {
        const url = btn.dataset.markUrl;

        try {
            await fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '',
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });
        } catch (e) {
            console.warn('Mark version seen failed:', e);
        }

        // Fermer le modal, quoi qu'il arrive
        document.getElementById('versionNotice')?.remove();
        document.getElementById('versionNoticeBackdrop')?.remove();
        document.body.style.overflow = '';
    });

    // Bloquer le scroll en arrière-plan
    document.body.style.overflow = 'hidden';
})();