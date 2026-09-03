const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const RECORDING_DIR = process.argv[2];
const KEY = process.argv[3];
if (!KEY) { console.error('Usage: node recorder.js <recording_dir> <vplink_key>'); process.exit(1); }
const SCREENSHOTS_DIR = path.join(RECORDING_DIR, 'screenshots');
const SNAPSHOTS_DIR = path.join(RECORDING_DIR, 'snapshots');

const events = [];
let startTime = Date.now();
let frameCount = 0;

async function captureFrame(page, label) {
  frameCount++;
  const ts = Date.now() - startTime;
  const prefix = String(frameCount).padStart(4, '0');
  try {
    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, `frame_${prefix}.png`),
      fullPage: false,
    });
  } catch {}
  try {
    const html = await page.content();
    fs.writeFileSync(path.join(SNAPSHOTS_DIR, `dom_${prefix}.html`), html);
  } catch {}
  events.push({ ts, type: 'frame', label, url: page.url().substring(0, 200) });
  process.stdout.write(`\r  [frame ${frameCount}] ${ts}ms ${label || ''} — ${page.url().substring(0, 90)}`);
}

function pad(n) { return String(n).padStart(2, '0'); }

async function main() {
  const browser = await chromium.launch({
    headless: false,
    args: [
      '--no-sandbox',
      '--disable-gpu',
      
      '--window-size=1280,720',
    ],
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
  });
  const page = await context.newPage();

  // ── Expose recording function to page context ──
  await page.exposeFunction('__recorderRecord', (data) => {
    data.ts = Date.now() - startTime;
    data.url = page.url().substring(0, 200);
    events.push(data);
    const tag = data.tagName || '';
    const txt = (data.text || '').substring(0, 40);
    const sel = (data.selector || '').substring(0, 60);
    const type = data.type;
    if (type === 'click')
      console.log(`\n  [CLICK]  "${txt}" on <${tag}>  sel=${sel}`);
    else if (type === 'navigation')
      console.log(`\n  [NAV]    ${data.url.substring(0, 100)}`);
    else if (type === 'input')
      console.log(`\n  [INPUT]  <${tag}>${sel ? ' sel=' + sel : ''} val="${(data.value || '').substring(0, 50)}"`);
    else if (type === 'scroll')
      console.log(`\n  [SCROLL] x=${data.x} y=${data.y}`);
  });

  // ── Inject event listeners ──
  await page.addInitScript(() => {
    function getSelector(el) {
      if (!el || el === document) return '';
      if (el.id) return '#' + CSS.escape(el.id);
      if (el === document.body) return 'body';
      if (el === document.documentElement) return 'html';
      const parts = [];
      let cur = el;
      while (cur && cur !== document.body && cur !== document.documentElement) {
        let sel = cur.tagName.toLowerCase();
        if (cur.id) { parts.unshift('#' + CSS.escape(cur.id)); break; }
        if (cur.className && typeof cur.className === 'string') {
          const cls = cur.className.trim().split(/\s+/).filter(Boolean).slice(0, 3).join('.');
          if (cls) sel += '.' + cls;
        }
        const parent = cur.parentElement;
        if (parent) {
          const siblings = Array.from(parent.children).filter(c => c.tagName === cur.tagName);
          if (siblings.length > 1) {
            sel += `:nth-child(${Array.from(parent.children).indexOf(cur) + 1})`;
          }
        }
        parts.unshift(sel);
        cur = cur.parentElement;
      }
      return parts.join(' > ');
    }

    document.addEventListener('click', (e) => {
      const el = e.target;
      window.__recorderRecord({
        type: 'click',
        tagName: (el.tagName || '').toLowerCase(),
        id: el.id || '',
        className: (el.className && typeof el.className === 'string') ? el.className.substring(0, 100) : '',
        selector: getSelector(el),
        text: (el.textContent || '').trim().substring(0, 80),
        href: el.href || el.parentElement?.href || '',
        coords: { x: e.clientX, y: e.clientY },
        trusted: e.isTrusted,
        timeStamp: e.timeStamp,
      });
    }, true);

    document.addEventListener('input', (e) => {
      const el = e.target;
      window.__recorderRecord({
        type: 'input',
        tagName: (el.tagName || '').toLowerCase(),
        selector: getSelector(el),
        value: el.value || '',
        name: el.name || '',
        placeholder: el.placeholder || '',
      });
    }, true);

    window.addEventListener('scroll', (e) => {
      window.__recorderRecord({
        type: 'scroll',
        x: window.scrollX,
        y: window.scrollY,
      });
    }, true);

    // Capture navigation via popstate/hashchange
    window.addEventListener('popstate', () => {
      window.__recorderRecord({ type: 'navigation', subType: 'popstate' });
    });
    window.addEventListener('hashchange', () => {
      window.__recorderRecord({ type: 'navigation', subType: 'hashchange' });
    });
  });

  // ── Track page-level navigation ──
  page.on('framenavigated', frame => {
    if (frame === page.mainFrame()) {
      events.push({
        ts: Date.now() - startTime,
        type: 'navigation',
        url: frame.url().substring(0, 200),
      });
      console.log(`\n  [NAV]    ${frame.url().substring(0, 100)}`);
    }
  });

  page.on('load', () => {
    events.push({
      ts: Date.now() - startTime,
      type: 'load',
      url: page.url().substring(0, 200),
    });
    console.log(`\n  [LOAD]   ${page.url().substring(0, 100)}`);
    captureFrame(page, 'load');
  });

  page.on('popup', popup => {
    events.push({
      ts: Date.now() - startTime,
      type: 'popup',
      url: popup.url().substring(0, 200),
    });
    console.log(`\n  [POPUP]  opened`);
  });

  page.on('console', msg => {
    const text = msg.text();
    if (text.includes('vplink') || text.includes('click') || text.includes('error') || text.includes('redirect')) {
      events.push({
        ts: Date.now() - startTime,
        type: 'console',
        text: text.substring(0, 200),
      });
      console.log(`\n  [CONSOLE] ${text.substring(0, 100)}`);
    }
  });

  // ── Navigate ──
  console.log(`Navigating to https://vplink.in/${KEY} ...`);
  await page.goto(`https://vplink.in/${KEY}`, { waitUntil: 'load', timeout: 60000 });
  await captureFrame(page, 'initial');

  // ── Periodic capture every 1s ──
  const interval = setInterval(() => {
    captureFrame(page, 'tick');
  }, 1000);

  // ── Wait indefinitely ──
  await new Promise(() => {});

  // (never reached, killed by SIGINT)
}

main().catch(err => {
  console.error('\n[recorder ERROR]', err.message);
  process.exit(1);
});
