(function() {
    'use strict';

    const CSRF = getCookie('csrftoken');

    // ============================================================
    // Marquer comme lu
    // ============================================================
    document.addEventListener('click', async function(e) {
        const btn = e.target.closest('.mark-as-read-btn');
        if (!btn) return;

        const id = btn.dataset.notificationId;
        const item = btn.closest('.notification-item');

        try {
            const response = await fetch(`/notifications/marquer-lue/${id}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': CSRF,
                    'Content-Type': 'application/json',
                },
            });
            const data = await response.json();
            if (data.success) {
                item.classList.remove('unread');
                item.dataset.read = 'true';
                item.querySelector('.notification-actions').innerHTML = renderUnreadBtn(id);
                updateUnreadCount(-1);
                showNotification('Notification marquée comme lue', 'success');
            }
        } catch (err) {
            console.error('[notif]', err);
        }
    });

    // ============================================================
    // Marquer comme non lu
    // ============================================================
    document.addEventListener('click', async function(e) {
        const btn = e.target.closest('.mark-as-unread-btn');
        if (!btn) return;

        const id = btn.dataset.notificationId;
        const item = btn.closest('.notification-item');

        try {
            const response = await fetch(`/notifications/marquer-non-lue/${id}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': CSRF,
                    'Content-Type': 'application/json',
                },
            });
            const data = await response.json();
            if (data.success) {
                item.classList.add('unread');
                item.dataset.read = 'false';
                item.querySelector('.notification-actions').innerHTML = renderReadBtn(id);
                updateUnreadCount(1);
                showNotification('Notification marquée comme non lue', 'success');
            }
        } catch (err) {
            console.error('[notif]', err);
        }
    });

    // ============================================================
    // Supprimer une notification
    // ============================================================
    document.addEventListener('click', async function(e) {
        const btn = e.target.closest('.delete-btn');
        if (!btn) return;

        if (!confirm('Supprimer cette notification ?')) return;

        const id = btn.dataset.notificationId;
        const item = btn.closest('.notification-item');

        try {
            const response = await fetch(`/notifications/supprimer/${id}/`, {
                method: 'DELETE',
                headers: { 'X-CSRFToken': CSRF },
            });
            const data = await response.json();
            if (data.success) {
                item.style.transition = 'opacity 0.3s';
                item.style.opacity = '0';
                setTimeout(() => item.remove(), 300);
                showNotification('Notification supprimée', 'success');
            }
        } catch (err) {
            console.error('[notif]', err);
        }
    });

    // ============================================================
    // Actualiser
    // ============================================================
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('#refreshBtn');
        if (!btn) return;

        e.preventDefault();

        const icon = btn.querySelector('i');
        if (icon) icon.classList.add('animate-spin');

        const container = document.getElementById('notifications-container');
        if (container && window.htmx) {
            htmx.ajax('GET', window.location.href, {
                target: '#notifications-container',
                swap: 'innerHTML',
            }).then(() => {
                if (icon) icon.classList.remove('animate-spin');
            }).catch(() => {
                if (icon) icon.classList.remove('animate-spin');
            });
        } else {
            window.location.reload();
        }
    });

    // ============================================================
    // Tout marquer comme lu
    // ============================================================
    document.addEventListener('click', async function(e) {
        if (!e.target.closest('#markAllRead')) return;

        try {
            const response = await fetch('/notifications/marquer-toutes-lues/', {
                method: 'POST',
                headers: { 'X-CSRFToken': CSRF },
            });
            const data = await response.json();
            if (data.success) {
                refreshNotificationsList();
                showNotification(`Toutes marquées comme lues (${data.count})`, 'success');
            }
        } catch (err) {
            console.error('[notif]', err);
        }
    });

    // ============================================================
    // Supprimer toutes les lues
    // ============================================================
    document.addEventListener('click', async function(e) {
        if (!e.target.closest('#deleteAllRead')) return;

        if (!confirm('Supprimer toutes les notifications lues ?')) return;

        try {
            const response = await fetch('/notifications/supprimer-toutes-lues/', {
                method: 'POST',
                headers: { 'X-CSRFToken': CSRF },
            });
            const data = await response.json();
            if (data.success) {
                refreshNotificationsList();
                showNotification(`${data.count} notifications supprimées`, 'success');
            }
        } catch (err) {
            console.error('[notif]', err);
        }
    });

    // ============================================================
    // Tout sélectionner
    // ============================================================
    document.addEventListener('change', function(e) {
        const selectAll = e.target.closest('#selectAll');
        if (!selectAll) return;

        const checkboxes = document.querySelectorAll('.notification-checkbox');
        checkboxes.forEach(cb => {
            cb.checked = selectAll.checked;
        });

        updateBulkActions();
    });

    // ============================================================
    // Cocher/décocher individuel
    // ============================================================
    document.addEventListener('change', function(e) {
        if (e.target.classList && e.target.classList.contains('notification-checkbox')) {
            updateBulkActions();
        }
    });

    // ============================================================
    // Marquer la sélection comme lue
    // ============================================================
    document.addEventListener('click', async function(e) {
        if (!e.target.closest('#markSelectedRead')) return;

        const ids = getSelectedIds();
        if (ids.length === 0) return;

        try {
            const response = await fetch('/notifications/marquer-selection-lues/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': CSRF,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ notification_ids: ids }),
            });
            const data = await response.json();
            if (data.success) {
                refreshNotificationsList();
                showNotification(`${data.count} notification(s) marquée(s)`, 'success');
            }
        } catch (err) {
            console.error('[notif]', err);
        }
    });

    // ============================================================
    // Supprimer la sélection
    // ============================================================
    document.addEventListener('click', async function(e) {
        if (!e.target.closest('#deleteSelected')) return;

        const ids = getSelectedIds();
        if (ids.length === 0) return;

        if (!confirm(`Supprimer ${ids.length} notification(s) ?`)) return;

        try {
            const response = await fetch('/notifications/supprimer-selection/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': CSRF,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ notification_ids: ids }),
            });
            const data = await response.json();
            if (data.success) {
                refreshNotificationsList();
                showNotification(`${data.count} notification(s) supprimée(s)`, 'success');
            }
        } catch (err) {
            console.error('[notif]', err);
        }
    });

    // ============================================================
    // Fonctions utilitaires
    // ============================================================
    function refreshNotificationsList() {
        const container = document.getElementById('notifications-container');
        if (!container) return;

        if (window.htmx) {
            htmx.ajax('GET', window.location.href, {
                target: '#notifications-container',
                swap: 'innerHTML',
            });
        } else {
            window.location.reload();
        }
    }

    function updateBulkActions() {
        const checked = document.querySelectorAll('.notification-checkbox:checked');
        const bulkActions = document.getElementById('bulkActions');
        const selectedCount = document.getElementById('selectedCount');
        const selectAll = document.getElementById('selectAll');

        if (bulkActions) {
            bulkActions.style.display = checked.length > 0 ? 'flex' : 'none';
        }
        if (selectedCount) {
            selectedCount.textContent = `${checked.length} sélectionnée(s)`;
        }
        if (selectAll) {
            const total = document.querySelectorAll('.notification-checkbox').length;
            selectAll.checked = (total > 0 && checked.length === total);
            selectAll.indeterminate = (checked.length > 0 && checked.length < total);
        }
    }

    function getSelectedIds() {
        return Array.from(
            document.querySelectorAll('.notification-checkbox:checked')
        ).map(cb => cb.dataset.notificationId);
    }

    function renderReadBtn(id) {
        return `
            <button type="button"
                    class="action-btn mark-as-read-btn"
                    data-notification-id="${id}"
                    title="Marquer comme lu"
                    style="background-color: var(--accent-primary);">
                <i class="fas fa-check text-white"></i>
            </button>`;
    }

    function renderUnreadBtn(id) {
        return `
            <button type="button"
                    class="action-btn mark-as-unread-btn"
                    data-notification-id="${id}"
                    title="Marquer comme non lu"
                    style="background-color: var(--bg-elevated);">
                <i class="fas fa-undo" style="color: var(--text-primary);"></i>
            </button>`;
    }

    function updateUnreadCount(delta) {
        const badge = document.querySelector('#notificationBtn span');
        if (!badge) return;
        const current = parseInt(badge.textContent.trim()) || 0;
        const next = Math.max(0, current + delta);
        if (next === 0) {
            badge.remove();
        } else {
            badge.textContent = next;
        }
    }

    function getCookie(name) {
        for (const c of document.cookie.split(';')) {
            const [k, v] = c.trim().split('=');
            if (k === name) return decodeURIComponent(v);
        }
        return null;
    }

    function showNotification(message, type) {
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type);
        }
    }
})();