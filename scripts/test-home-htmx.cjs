const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'goProjet', 'static',
    'projets', 'js', 'home.js'), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));

function fixture() {
    const events = {};
    const scripts = [];
    const charts = [];
    let element = {
        dataset: { chartData: JSON.stringify({ projets: [{ avancement: 45 }] }) },
        isConnected: true,
        textContent: '',
        setAttribute() {},
        replaceChildren() { this.cleared = true; },
    };
    const context = {
        window: { addEventListener() {} },
        document: {
            readyState: 'complete',
            querySelectorAll: () => [],
            getElementById: () => element,
            createElement: () => ({ remove() {} }),
            body: {
                appendChild: script => scripts.push(script),
                addEventListener: (name, fn) => { events[name] = fn; },
            },
        },
        console: { error() {} },
        setTimeout,
    };
    vm.createContext(context);
    const manager = function () {
        this.chartElement = element;
        this.ready = Promise.resolve();
        this.destroy = () => { this.destroyed = true; };
        charts.push(this);
    };
    return {
        context, scripts, events, charts, manager,
        get element() { return element; },
        swap() {
            const old = element;
            events['htmx:beforeCleanupElement']({ detail: { elt: { contains: el => el === old } } });
            old.isConnected = false;
            element = { ...old, isConnected: true };
            events['htmx:afterSwap']({ detail: { target: { id: 'main-content' } } });
        },
        start() { vm.runInContext(source, context); },
        dependenciesReady() {
            context.ApexCharts = function () {};
            context.window.ProjetsChartManager = manager;
            scripts.forEach(script => script.onload());
        },
    };
}

test('Home loaded by HTMX waits for both dependencies and cleans up on navigation', async () => {
    const f = fixture();
    f.start();
    assert.equal(f.scripts.length, 2);
    assert.equal(f.charts.length, 0);
    f.dependenciesReady();
    await settle();
    assert.equal(f.charts.length, 1);
    f.swap();
    await settle();
    assert.equal(f.charts[0].destroyed, true);
    assert.equal(f.charts.length, 2);
    assert.equal(f.scripts.length, 2);
    f.events['htmx:historyRestore']();
    await settle();
    assert.equal(f.charts[1].destroyed, true);
    assert.equal(f.charts.length, 3);
    assert.equal(f.element.cleared, true);
});

test('pending dependency loading cannot render into an obsolete Home element', async () => {
    const f = fixture();
    f.start();
    f.swap();
    f.dependenciesReady();
    await settle();
    assert.equal(f.charts.length, 1);
    assert.equal(f.charts[0].chartElement, f.element);
});

test('dependency failure is visible and can be retried on the next visit', async () => {
    const f = fixture();
    f.start();
    f.scripts[0].onerror();
    await settle();
    assert.match(f.element.textContent, /Impossible de charger/);
    f.swap();
    f.dependenciesReady();
    await settle();
    assert.equal(f.charts.length, 1);
});

test('empty datasets show an explicit empty state without downloading charts', async () => {
    const f = fixture();
    f.element.dataset.chartData = '{"projets":[]}';
    f.start();
    await settle();
    assert.match(f.element.textContent, /Aucun projet/);
    assert.equal(f.scripts.length, 0);
});

test('duplicate script evaluation does not add listeners or charts', async () => {
    const f = fixture();
    f.context.ApexCharts = function () {};
    f.context.window.ProjetsChartManager = f.manager;
    f.start();
    f.start();
    await settle();
    assert.equal(f.charts.length, 1);
});

test('chart manager removes its resize listener and destroys the chart', async () => {
    const filename = path.join(__dirname, '..', 'goProjet', 'static', 'projets',
        'js', 'charts.js');
    const handlers = new Set();
    let destroyed = 0;
    const context = {
        window: {
            innerWidth: 1024,
            addEventListener: (_, fn) => handlers.add(fn),
            removeEventListener: (_, fn) => handlers.delete(fn),
        },
        document: { getElementById: () => ({}) },
        ApexCharts: function () {
            this.render = () => Promise.resolve();
            this.destroy = () => destroyed++;
        },
        clearTimeout, setTimeout,
    };
    vm.runInNewContext(fs.readFileSync(filename, 'utf8'), context);
    const manager = new context.window.ProjetsChartManager({ projets: [] });
    await manager.ready;
    assert.equal(handlers.size, 1);
    manager.destroy();
    assert.equal(handlers.size, 0);
    assert.equal(destroyed, 1);
});
