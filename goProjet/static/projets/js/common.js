(function() {
    'use strict';

    // ============================================================
    // Menu utilisateur + dropdown notifications
    // ============================================================
    document.addEventListener('DOMContentLoaded', function() {
        const userBtn = document.getElementById('userMenuBtn');
        const userDropdown = document.getElementById('userMenuDropdown');
        const notifBtn = document.getElementById('notificationBtn');
        const notifDropdown = document.getElementById('notificationDropdown');

        if (userBtn && userDropdown) {
            userBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                userDropdown.classList.toggle('hidden');
                if (notifDropdown) notifDropdown.classList.add('hidden');
            });
        }

        if (notifBtn && notifDropdown) {
            notifBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                notifDropdown.classList.toggle('hidden');
                if (userDropdown) userDropdown.classList.add('hidden');
            });
        }

        document.addEventListener('click', function(e) {
            if (userDropdown && !e.target.closest('#userMenuBtn') && !e.target.closest('#userMenuDropdown')) {
                userDropdown.classList.add('hidden');
            }
            if (notifDropdown && !e.target.closest('#notificationBtn') && !e.target.closest('#notificationDropdown')) {
                notifDropdown.classList.add('hidden');
            }
        });

        // Marquer tout comme lu
        const markAllBtn = document.getElementById('markAllReadFromDropdown');
        if (markAllBtn) {
            markAllBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();

                fetch(NOTIFICATION_API_URL, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': CSRF_TOKEN
                    },
                    credentials: 'same-origin'
                }).then(response => {
                    if (response.ok) {
                        const badge = document.querySelector('#notificationBtn span');
                        if (badge) badge.remove();
                        document.querySelectorAll('.notification-item').forEach(item => {
                            item.classList.remove('app-dropdown-item-unread');
                            const dot = item.querySelector('.flex-shrink-0 div');
                            if (dot) dot.classList.replace('bg-cyan-500', 'bg-gray-500');
                        });
                        if (typeof showNotification === 'function') {
                            showNotification('Toutes les notifications ont été marquées comme lues', 'success');
                        }
                    }
                });
            });
        }
    });

    // ============================================================
    // Fallback avatar
    // ============================================================
    window.handleNavbarAvatarError = function(img) {
        img.onerror = null;
        const username = document.body.dataset.username || 'User';
        img.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(username)}&background=10B981&color=fff&size=64`;
    };
})();