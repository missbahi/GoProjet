const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'goProjet', 'static', 'projets', 'js', 'toast.js'), 'utf8');

function fixture() {
    class Element {
        constructor(tag = 'div') {
            this.tag = tag;
            this.children = [];
            this.dataset = {};
            this.attributes = {};
            this.listeners = {};
        }
        appendChild(child) {
            child.remove();
            child.parentElement = this;
            this.children.push(child);
            return child;
        }
        remove() {
            if (this.parentElement) {
                this.parentElement.children = this.parentElement.children.filter(item => item !== this);
                this.parentElement = null;
            }
        }
        setAttribute(name, value) { this.attributes[name] = value; }
        addEventListener(name, callback) { this.listeners[name] = callback; }
        matches(selector) { return selector === this.tag; }
        contains(element) { return this === element || this.children.some(child => child.contains(element)); }
        querySelectorAll(selector) {
            const all = this.children.flatMap(child => [child, ...child.querySelectorAll('*')]);
            if (selector === '[data-app-message]') return all.filter(child => child.dataset.appMessage);
            if (selector === 'dialog[open]') return all.filter(child => child.tag === 'dialog' && child.open);
            return all;
        }
    }
    const body = new Element('body');
    const events = {};
    const document = {
        body, readyState: 'complete',
        createElement: tag => new Element(tag),
        getElementById: id => body.querySelectorAll('*').find(child => child.id === id),
        querySelectorAll: selector => body.querySelectorAll(selector),
        addEventListener: (name, callback) => { events[name] = callback; },
    };
    const calls = [];
    let result = new Response('{}', { status: 200 });
    class XHR {
        addEventListener(name, listener) { this[name] = listener; }
        open() {}
        setRequestHeader(name, value) { this.requestHeader = [name, value]; }
        send() { this.load?.(); }
        getResponseHeader() { return this.header; }
    }
    const context = {
        document, Headers, Request, URL, XMLHttpRequest: XHR,
        MutationObserver: class { observe() {} },
        window: {
            location: new URL('http://localhost/page/'),
            fetch: async (input, options) => { calls.push({ input, options }); return result; },
        },
        setTimeout: () => 1, clearTimeout() {}, console,
    };
    vm.runInNewContext(source, context);
    const toasts = () => document.getElementById('toast-container')?.children || [];
    return {
        context, events, calls, toasts, Element, body,
        setResponse: response => { result = response; },
    };
}

test('all public message APIs share one safe, deduplicated toast', () => {
    const f = fixture();
    const message = '<img src=x onerror=alert(1)>';
    f.context.window.showToast(message, 'success');
    f.context.window.showNotification(message, 'success');
    assert.equal(f.toasts().length, 1);
    assert.equal(f.toasts()[0].children[0].textContent, message);
    assert.equal(f.toasts()[0].attributes.role, 'status');
    assert.equal(f.toasts()[0].children[0].children.length, 0);
});

test('at most five toasts exist and clearAll removes their container', () => {
    const f = fixture();
    for (let i = 0; i < 8; i++) f.context.window.showInfoMessage(String(i));
    assert.equal(f.toasts().length, 5);
    f.context.window.notificationAPI.clearAll();
    assert.equal(f.toasts().length, 0);
    assert.equal(f.context.document.getElementById('toast-container'), undefined);
});

test('same-origin fetch delivers headers while preserving body and caller headers', async () => {
    const f = fixture();
    f.setResponse(new Response('{"success":true}', {
        headers: { 'X-App-Messages': JSON.stringify([{ message: 'Saved', type: 'success' }]) },
    }));
    const response = await f.context.window.fetch('/action/', { method: 'POST', headers: { 'X-CSRFToken': 'token' } });
    assert.equal(f.calls[0].options.headers.get('X-CSRFToken'), 'token');
    assert.equal(f.calls[0].options.headers.get('X-App-Toast'), 'true');
    assert.deepEqual(await response.json(), { success: true });
    assert.equal(f.toasts().length, 1);
    f.context.window.showSuccessMessage('Saved');
    assert.equal(f.toasts().length, 1);
});

test('third-party fetch is untouched', async () => {
    const f = fixture();
    await f.context.window.fetch('https://example.com/', { method: 'GET' });
    assert.equal(f.calls[0].options.headers, undefined);
    assert.equal(f.toasts().length, 0);
});

test('validation responses do not generate generic toasts', async () => {
    const f = fixture();
    f.setResponse(new Response('{"errors":{"title":["Required"]}}', { status: 400 }));
    const response = await f.context.window.fetch('/form/');
    assert.equal(f.toasts().length, 0);
    assert.deepEqual(await response.json(), { errors: { title: ['Required'] } });
    f.events['htmx:responseError']({ detail: { xhr: { status: 422, getResponseHeader: () => null } } });
    assert.equal(f.toasts().length, 0);
});

test('HTTP failures produce accessible errors', async () => {
    const f = fixture();
    f.setResponse(new Response('failure', { status: 500 }));
    await f.context.window.fetch('/action/');
    assert.equal(f.toasts()[0].attributes.role, 'alert');
    assert.match(f.toasts()[0].children[0].textContent, /500/);
});

test('fragment messages are consumed and cannot replay on another swap', () => {
    const f = fixture();
    const marker = new f.Element();
    marker.dataset = { appMessage: 'Updated', appMessageType: 'warning' };
    f.body.appendChild(marker);
    f.events['htmx:afterSwap']({ detail: { target: f.body } });
    f.context.window.notificationAPI.clearAll();
    f.events['htmx:afterSwap']({ detail: { target: f.body } });
    assert.equal(f.toasts().length, 0);
});

test('dialog notifications move back before HTMX removes the modal', () => {
    const f = fixture();
    const dialog = new f.Element('dialog');
    dialog.open = true;
    f.body.appendChild(dialog);
    f.context.window.showErrorMessage('Modal error');
    assert.equal(f.context.document.getElementById('toast-container').parentElement, dialog);
    f.events['htmx:beforeCleanupElement']({ detail: { elt: dialog } });
    dialog.remove();
    assert.equal(f.toasts().length, 1);
    assert.equal(f.context.document.getElementById('toast-container').parentElement, f.body);
});

test('loading scripts twice cannot duplicate listeners or fetch wrappers', () => {
    const f = fixture();
    const fetch = f.context.window.fetch;
    vm.runInNewContext(source, f.context);
    assert.equal(f.context.window.fetch, fetch);
});

test('native XMLHttpRequest delivers the same notification header', () => {
    const f = fixture();
    const xhr = new f.context.XMLHttpRequest();
    xhr.responseURL = 'http://localhost/action/';
    xhr.header = JSON.stringify([{ message: 'Uploaded', type: 'success' }]);
    xhr.open('POST', '/action/');
    xhr.send();
    assert.deepEqual(xhr.requestHeader, ['X-App-Toast', 'true']);
    assert.equal(f.toasts().length, 1);
    assert.equal(f.toasts()[0].children[0].textContent, 'Uploaded');
});
