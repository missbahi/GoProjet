(function () {
    'use strict';
    if (window.OBSERVER_READ_ONLY) return;
    window.OBSERVER_READ_ONLY = true;
    const policy = JSON.parse(document.getElementById('observer-route-policy').textContent)
        .map(rule => ({ regex: new RegExp(rule.pattern), methods: rule.methods }));

    function allowed(value, method = 'GET') {
        const url = new URL(value || location.href, location.href);
        if (!['http:', 'https:', 'mailto:', 'tel:'].includes(url.protocol)) return false;
        if (url.origin !== location.origin) return method === 'GET';
        return policy.some(rule => rule.methods.includes(method) && rule.regex.test(url.pathname));
    }

    function hide(element) {
        element.setAttribute('data-observer-hidden', '');
        if ('disabled' in element) element.disabled = true;
    }

    function allowedForm(form) {
        if (form.hasAttribute('data-observer-write')) return false;
        const method = (form.getAttribute('method') || 'GET').toUpperCase();
        if (method === 'DIALOG') return form.hasAttribute('data-observer-safe');
        return allowed(form.action || location.href, method);
    }

    const safeButtons = [
        '[data-observer-safe]', '[data-theme-toggle]', '[data-sort]',
        '[data-attachment-trace]', '[data-attachment-dialog-close]', '[data-modal-close]',
        '[data-goplan-view]', '[data-gantt-view]', '[data-gantt-zoom]',
        '[data-view]', '[data-tv-action="fold"]', '.tv-row-header button',
        '.goplan-gantt-group-toggle', '#gantt-zoom-in', '#gantt-zoom-out', '#gantt-today',
        '#toggle-expanded-all-btn', '#ca-help-open', '#ca-help-close',
        '#searchToggle', '#clearSearch', '.vue-btn',
        '.app-modal-close', '.modal-close', '.tree-toggle', '.tv-tree-toggle',
        '#sidebar-toggle', '#sidebar-toggle-mobile', '#topbar-toggle-btn',
    ].join(',');

    function update() {
        document.querySelectorAll('a[href], [hx-get], [data-url]').forEach(element => {
            const url = element.getAttribute('hx-get') || element.getAttribute('href')
                || element.getAttribute('data-url');
            if (url && !url.startsWith('#') && !allowed(url)) hide(element);
        });
        document.querySelectorAll('[hx-post], [hx-put], [hx-patch], [hx-delete]').forEach(element => {
            const url = element.getAttribute('hx-post');
            if (!url || !allowed(url, 'POST')) hide(element);
        });
        document.querySelectorAll('form').forEach(form => {
            if (allowedForm(form)) return;
            form.querySelectorAll('input:not([type="hidden"]), select, textarea').forEach(field => {
                field.disabled = true;
            });
            form.querySelectorAll('[type="submit"]').forEach(hide);
        });
        document.querySelectorAll('[contenteditable="true"]').forEach(element => {
            element.contentEditable = 'false';
        });
        document.querySelectorAll('#main-content button, .main-container button').forEach(button => {
            if (button.matches(safeButtons)) return;
            const form = button.form;
            if (form && allowedForm(form)) return;
            const url = button.getAttribute('hx-get') || button.dataset.url;
            if (url && allowed(url)) return;
            const onclick = button.getAttribute('onclick') || '';
            if (/window\.(print|close)\s*\(|history\.back\s*\(/.test(onclick)) return;
            hide(button);
        });
    }

    document.addEventListener('submit', event => {
        const form = event.target;
        if (!allowedForm(form)) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    }, true);
    document.addEventListener('click', event => {
        const target = event.target.closest('[data-observer-hidden]');
        if (target) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    }, true);
    document.addEventListener('htmx:beforeRequest', event => {
        const config = event.detail.requestConfig;
        if (config && !allowed(config.path, config.verb.toUpperCase())) event.preventDefault();
    });
    let scheduled = false;
    function schedule() {
        if (scheduled) return;
        scheduled = true;
        requestAnimationFrame(() => { scheduled = false; update(); });
    }
    document.addEventListener('DOMContentLoaded', () => {
        update();
        new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
    });
    document.addEventListener('htmx:afterSwap', schedule);
    window.observerCanAccess = allowed;
}());
