(function () {
    'use strict';
    if (window.__toastInitialized) return;
    window.__toastInitialized = true;

    const active = new Map();
    const durations = { success: 3500, info: 3500, warning: 6000, error: 8000 };

    function container() {
        let element = document.getElementById('toast-container');
        const dialogs = document.querySelectorAll('dialog[open]');
        const host = dialogs[dialogs.length - 1] || document.body;
        if (!element) {
            element = document.createElement('div');
            element.id = 'toast-container';
        }
        if (element.parentElement !== host) host.appendChild(element);
        return element;
    }

    function showToast(message, type = 'info', duration, options = {}) {
        if (typeof message !== 'string' || !message.trim()) {
            console.error('[toast] Message invalide', message);
            return;
        }
        if (!Object.hasOwn(durations, type)) type = 'info';
        const key = `${type}:${message}`;
        if (active.has(key)) return active.get(key).element;
        if (active.size >= 5) active.values().next().value.close();
        const element = document.createElement('div');
        element.className = `toast toast-${type}`;
        element.setAttribute('role', type === 'error' ? 'alert' : 'status');
        element.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
        element.setAttribute('aria-atomic', 'true');
        const text = document.createElement('span');
        text.className = 'toast-message';
        text.textContent = message;
        element.appendChild(text);
        let timer;
        const close = () => {
            if (!active.has(key)) return;
            clearTimeout(timer);
            active.delete(key);
            element.remove();
            const parent = document.getElementById('toast-container');
            if (parent && !parent.children.length) parent.remove();
            options.onClose?.();
        };
        if (options.action) {
            const action = document.createElement('button');
            action.type = 'button';
            action.className = 'toast-action';
            action.textContent = options.action.label;
            action.addEventListener('click', () => { options.action.callback(); close(); });
            element.appendChild(action);
        }
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'toast-close';
        button.textContent = '\u00d7';
        button.setAttribute('aria-label', 'Fermer la notification');
        button.addEventListener('click', close);
        element.appendChild(button);
        active.set(key, { element, close });
        container().appendChild(element);
        const startTimer = () => {
            clearTimeout(timer);
            if (!options.persistent) timer = setTimeout(close, duration ?? durations[type]);
        };
        element.addEventListener('mouseenter', () => clearTimeout(timer));
        element.addEventListener('mouseleave', startTimer);
        element.addEventListener('focusin', () => clearTimeout(timer));
        element.addEventListener('focusout', startTimer);
        startTimer();
        return element;
    }

    window.showToast = showToast;
    window.showSuccessMessage = message => showToast(message, 'success');
    window.showErrorMessage = message => showToast(message, 'error');
    window.showWarningMessage = message => showToast(message, 'warning');
    window.showInfoMessage = message => showToast(message, 'info');
    window.showNotification = (message, type = 'success', options = {}) =>
        showToast(message, type, options.duration, options);
    window.notificationAPI = {
        success: (message, options) => window.showNotification(message, 'success', options),
        error: (message, options) => window.showNotification(message, 'error', options),
        warning: (message, options) => window.showNotification(message, 'warning', options),
        info: (message, options) => window.showNotification(message, 'info', options),
        clearAll: () => [...active.values()].forEach(item => item.close()),
    };

    function readMessages(raw) {
        if (!raw) return false;
        try {
            JSON.parse(raw).forEach(item => showToast(item.message, item.type));
        } catch (error) {
            console.error('[toast] Réponse de messagerie invalide', error);
            showToast("Impossible d'afficher les messages de l'opération.", 'error');
        }
        return true;
    }

    function readMarkup(root = document) {
        root.querySelectorAll('[data-app-message]').forEach(element => {
            showToast(element.dataset.appMessage, element.dataset.appMessageType);
            element.remove();
        });
    }

    document.addEventListener('close', event => {
        if (event.target.matches('dialog') && active.size) container();
    }, true);
    document.addEventListener('showMessage', event => {
        const detail = event.detail || {};
        showToast(detail.message || detail.value, detail.type || detail.messageType || 'info');
    });
    document.addEventListener('show-notification', event => {
        window.showNotification(event.detail.message, event.detail.type, event.detail.options);
    });
    document.addEventListener('htmx:afterSwap', event => readMarkup(event.detail.target));
    document.addEventListener('htmx:afterRequest', event => {
        readMessages(event.detail.xhr.getResponseHeader('X-App-Messages'));
    });
    document.addEventListener('htmx:responseError', event => {
        const xhr = event.detail.xhr;
        if ([400, 422].includes(xhr.status) || xhr.getResponseHeader('X-App-Messages')) return;
        showToast(`L'opération a échoué (HTTP ${xhr.status}).`, 'error');
    });
    ['htmx:sendError', 'htmx:timeout'].forEach(name => {
        document.addEventListener(name, () => showToast('Connexion au serveur impossible. Réessayez.', 'error'));
    });

    const originalFetch = window.fetch;
    window.fetch = async function (input, options) {
        const url = new URL(typeof input === 'string' || input instanceof URL ? input : input.url, window.location.href);
        if (url.origin !== window.location.origin) return originalFetch.call(this, input, options);
        let response;
        try {
            response = await originalFetch.call(this, input, options);
        } catch (error) {
            if (error.name !== 'AbortError') showToast('Connexion au serveur impossible. Réessayez.', 'error');
            throw error;
        }
        const delivered = readMessages(response.headers.get('X-App-Messages'));
        if (!response.ok && !delivered && ![400, 422].includes(response.status)) {
            showToast(`L'opération a échoué (HTTP ${response.status}).`, 'error');
        }
        return response;
    };

    const originalSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function (...args) {
        this.addEventListener('load', () => {
            if (this.responseURL && new URL(this.responseURL).origin === window.location.origin) {
                readMessages(this.getResponseHeader('X-App-Messages'));
            }
        }, { once: true });
        return originalSend.apply(this, args);
    };

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => readMarkup());
    else readMarkup();
})();
