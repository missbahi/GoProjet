const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'goProjet', 'static',
    'projets', 'js', 'notifications.js'), 'utf8');

for (const selector of [
    '.mark-as-read-btn', '.mark-as-unread-btn', '#notifications-container .delete-btn',
    '#markAllRead', '#deleteAllRead', '#markSelectedRead', '#deleteSelected',
]) {
    test(`${selector} requests a server-authoritative panel refresh`, async () => {
        const handlers = [];
        const events = [];
        const refreshes = [];
        const button = { dataset: { notificationId: '42' } };
        const context = {
            window: {
                location: { href: 'http://localhost/notifications/?filter=unread&page=2' },
                htmx: { ajax: (...args) => { refreshes.push(args); return Promise.resolve(); } },
            },
            document: {
                cookie: 'csrftoken=fixture',
                addEventListener: (name, fn) => { if (name === 'click') handlers.push(fn); },
                getElementById: id => id === 'notifications-container' ? {} : null,
                querySelectorAll: () => [{ dataset: { notificationId: '42' } }],
                body: { dispatchEvent: event => events.push(event.type) },
            },
            fetch: async () => ({
                ok: true,
                json: async () => ({ success: true, count: 1 }),
            }),
            CustomEvent: class { constructor(type) { this.type = type; } },
            confirm: () => true,
            console,
        };
        context.htmx = context.window.htmx;
        vm.runInNewContext(source, context);
        const event = { target: { closest: query => query === selector ? button : null } };
        for (const handler of handlers) await handler(event);
        assert.deepEqual(events, ['notifications:changed']);
        assert.equal(refreshes.length, 1);
        assert.equal(refreshes[0][1], context.window.location.href);
        assert.equal(refreshes[0][2].target, '#main-content');
    });
}

test('failed notification mutation shows an error without claiming a successful refresh', async () => {
    const handlers = [];
    const messages = [];
    const events = [];
    const context = {
        window: { showNotification: (message, type) => messages.push(type) },
        document: {
            cookie: 'csrftoken=fixture',
            addEventListener: (name, fn) => { if (name === 'click') handlers.push(fn); },
            body: { dispatchEvent: event => events.push(event) },
        },
        fetch: async () => ({ ok: false, status: 403, json: async () => ({ error: 'Forbidden' }) }),
        console: { error() {} },
    };
    vm.runInNewContext(source, context);
    for (const handler of handlers) {
        await handler({
            target: { closest: query => query === '.mark-as-read-btn'
                ? { dataset: { notificationId: '42' } } : null },
        });
    }
    assert.deepEqual(messages, ['error']);
    assert.equal(events.length, 0);
});
