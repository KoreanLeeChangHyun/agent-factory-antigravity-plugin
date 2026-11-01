// Owned by the Python test supervisor. JSON-line RPC keeps one real browser alive
// across CLI invocations; stdout carries protocol replies only.
const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');

let context, page, directory, tracePath;
const attached = new WeakSet();
const at = () => new Date().toISOString();
function log(event, data) {
  fs.appendFileSync(path.join(directory, 'browser-events.jsonl'), JSON.stringify({ at: at(), event, ...data }) + '\n', { mode: 0o600 });
}
function watch(target) {
  if (attached.has(target)) return;
  attached.add(target);
  target.on('console', message => log('console', { level: message.type(), text: message.text(), url: target.url() }));
  target.on('pageerror', error => log('pageerror', { error: String(error), url: target.url() }));
  target.on('requestfailed', request => log('requestfailed', { url: request.url(), error: request.failure()?.errorText }));
  target.on('response', response => { if (response.status() >= 400) log('http-error', { url: response.url(), status: response.status() }); });
  target.on('close', () => { if (page === target) page = context.pages().find(item => !item.isClosed()); });
}
function url(value) {
  if (!['http:', 'https:', 'file:', 'about:'].includes(new URL(value).protocol)) throw new Error('Unsupported navigation protocol');
  return value;
}
function current() {
  if (!page || page.isClosed()) throw new Error('No open browser page; use tab or reset');
  return page;
}
async function perform(op, input) {
  if (op === 'start') {
    directory = input.directory;
    const { chromium } = require(input.module);
    // A browser chosen in Providers overrides Playwright's own download.
    context = await chromium.launchPersistentContext(path.join(directory, 'browser-profile'), {
      headless: !input.headed, viewport: input.viewport, acceptDownloads: false,
      executablePath: process.env.AGENT_FACTORY_CHROMIUM_PATH || undefined,
    });
    context.setDefaultTimeout(input.timeoutMs);
    context.setDefaultNavigationTimeout(input.timeoutMs);
    tracePath = path.join(directory, 'trace-' + Date.now() + '.zip');
    await context.tracing.start({ screenshots: true, snapshots: true, sources: false });
    context.on('page', target => { watch(target); page = target; });
    page = context.pages()[0] || await context.newPage();
    for (const target of context.pages()) watch(target);
    await page.goto(url(input.url), { waitUntil: 'domcontentloaded' });
    log('browser.ready', { url: page.url(), trace: tracePath });
    return { url: page.url(), trace: tracePath };
  }
  if (op === 'stop') {
    await context.tracing.stop({ path: tracePath });
    await context.close();
    return { stopped: true, trace: tracePath };
  }
  if (op === 'act') {
    const target = input.selector ? current().locator(input.selector) : null;
    log('action.started', { action: input.action, selector: input.selector });
    switch (input.action) {
      case 'click': if (target) await target.click(); else await current().mouse.click(input.x, input.y); break;
      case 'fill': await target.fill(input.text); break;
      case 'type': await current().keyboard.insertText(input.text); break;
      case 'press': await current().keyboard.press(input.key); break;
      case 'scroll': await current().mouse.wheel(input.x || 0, input.y || 0); break;
      case 'navigate': await current().goto(url(input.url), { waitUntil: 'domcontentloaded' }); break;
      case 'reload': await current().reload({ waitUntil: 'domcontentloaded' }); break;
      case 'back': await current().goBack({ waitUntil: 'domcontentloaded' }); break;
      case 'select': await target.selectOption(input.value); break;
      case 'check': await target.setChecked(input.value); break;
      case 'tab': {
        if (input.index < 0 || input.index >= context.pages().length) throw new Error('Tab index is outside the open pages');
        page = context.pages()[input.index];
        await page.bringToFront();
        break;
      }
      default: throw new Error('Unsupported browser action: ' + input.action);
    }
    log('action.completed', { action: input.action, url: current().url() });
    return { url: current().url(), title: await current().title() };
  }
  if (op === 'inspect') {
    if (input.property === 'url') return current().url();
    if (input.property === 'title') return current().title();
    if (!input.selector) throw new Error('This browser property requires a selector');
    const target = current().locator(input.selector);
    switch (input.property) {
      case 'text': return target.innerText();
      case 'value': return target.inputValue();
      case 'visible': return target.isVisible();
      case 'count': return target.count();
      default: throw new Error('Unsupported browser inspection property');
    }
  }
  if (op === 'observe') {
    await current().screenshot({ path: input.path, fullPage: false, animations: 'disabled' });
    const elements = await current().locator('button,input,textarea,select,a,[role],[contenteditable="true"]').evaluateAll(nodes => nodes.map(node => ({
      tag: node.tagName.toLowerCase(), id: node.id || undefined, role: node.getAttribute('role') || undefined,
      label: node.getAttribute('aria-label') || undefined, text: node.innerText || undefined,
      type: node.getAttribute('type') || undefined, testId: node.getAttribute('data-testid') || undefined,
      visible: node.getClientRects().length > 0,
    })));
    return { url: current().url(), title: await current().title(), elements, viewport: current().viewportSize(),
      tabs: context.pages().map((target, index) => ({ index, url: target.url(), active: target === page })),
      browserLog: path.join(directory, 'browser-events.jsonl'), trace: tracePath, traceReady: false };
  }
  throw new Error('Unsupported worker operation: ' + op);
}

const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
let pending = Promise.resolve();
lines.on('line', line => {
  pending = pending.then(async () => {
    let request;
    try {
      request = JSON.parse(line);
      const result = await perform(request.op, request.input);
      process.stdout.write(JSON.stringify({ ok: true, result }) + '\n');
    } catch (error) {
      if (directory) log('operation.failed', { error: String(error) });
      process.stdout.write(JSON.stringify({ ok: false, error: String(error) }) + '\n');
    }
    if (request?.op === 'stop') { lines.close(); process.exitCode = 0; }
  });
});
lines.on('close', () => {
  void pending.finally(async () => { if (context) await context.close().catch(() => {}); });
});
