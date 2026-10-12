// Compatibility entry point: toast.js owns the notification API and listeners.
(function () {
    'use strict';
    if (!window.showToast) console.error('[notifications] toast.js doit être chargé avant notification-handler.js');
})();
