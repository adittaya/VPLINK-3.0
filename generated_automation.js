let chromium;
try {
  ({ chromium } = require('playwright'));
} catch {
  ({ chromium } = require('playwright-core'));
}
const fs = require('fs');
const readline = require('readline');

async function getKey() {
  if (process.argv[2]) return process.argv[2];
  if (process.env.VPLINK_KEY) return process.env.VPLINK_KEY;
  process.stdout.write('Enter vplink URL or key: ');
  return new Promise(resolve => {
    const rl = readline.createInterface({ input: process.stdin });
    rl.on('line', line => {
      rl.close();
      resolve(line.replace(/https?:\/\/vplink\.in\//, '').trim());
    });
  });
}

let browser;

process.on('SIGINT', async () => {
  console.log('\nInterrupted — closing browser...');
  if (browser) await browser.close().catch(() => {});
  process.exit(130);
});

(async () => {
  const VPLINK_KEY = await getKey();
  if (!VPLINK_KEY) { console.error('No key provided'); process.exit(1); }
  const isTermux = process.env.VPLINK_TERMUX === '1';
  const launchOpts = { slowMo: 50 };
  if (isTermux) {
    launchOpts.headless = true;
    launchOpts.executablePath = process.env.CHROMIUM_PATH || '/data/data/com.termux/files/usr/bin/chromium-browser';
    launchOpts.args = ['--no-sandbox', '--disable-gpu'];
  } else {
    launchOpts.headless = false;
  }
  browser = await chromium.launch(launchOpts);
  const ctxOpts = { viewport: { width: 1280, height: 720 } };
  if (process.env.VPLINK_PROXY) {
    ctxOpts.proxy = { server: process.env.VPLINK_PROXY };
    console.log(`  Proxy: ${process.env.VPLINK_PROXY}`);
  }
  const context = await browser.newContext(ctxOpts);
  const page = await context.newPage();

  let destinationUrl = null;
  page.setDefaultNavigationTimeout(60000);

  async function ms(t) { await page.waitForTimeout(t); }

  async function goto(url, opts = {}) {
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        await page.goto(url, { waitUntil: 'domcontentloaded', ...opts, timeout: 45000 });
        return;
      } catch (e) {
        if (attempt === 0) { console.log(`  net slow, retry...`); await ms(4000); }
        else throw e;
      }
    }
  }

  async function clickId(id) {
    try { return await page.evaluate(i => {
      const e = document.getElementById(i); if (!e) return false;
      e.scrollIntoView({ block: 'center' }); e.click(); return true;
    }, id); } catch { return false; }
  }
  async function clickSel(sel) {
    try { return await page.evaluate(s => {
      const e = document.querySelector(s); if (!e) return false;
      e.scrollIntoView({ block: 'center' }); e.click(); return true;
    }, sel); } catch { return false; }
  }
  async function clickText(txt) {
    try { return await page.evaluate(t => {
      const w = document.createTreeWalker(document.body, 4, null, false);
      let n; while (n = w.nextNode()) {
        if (n.textContent.trim() === t) {
          n.parentElement?.scrollIntoView({ block: 'center' });
          n.parentElement?.click(); return true;
        }
      }
      return false;
    }, txt); } catch { return false; }
  }
  async function clickLearnMoreSameDomain() {
    try { return await page.evaluate(d => {
      const links = document.querySelectorAll('a');
      for (const a of links) {
        if (a.href && a.href.includes('learn_more') && a.href.includes(d)) {
          a.scrollIntoView({ block: 'center' }); a.click(); return true;
        }
      }
      return false;
    }, new URL(page.url()).hostname); } catch { return false; }
  }

  function parentDirUrl() {
    const u = page.url().replace(/\/#?.*$/, '').replace(/\/+$/, '');
    const idx = u.lastIndexOf('/');
    if (idx < 10) return null;
    return u.substring(0, idx);
  }

  async function scrollDown() {
    await page.evaluate(() => window.scrollTo({ top: 99999, behavior: 'instant' }));
    await ms(300);
    for (let y = 0; y < 20000; y += 1500) {
      await page.evaluate(yy => window.scrollTo({ top: yy, behavior: 'smooth' }), y);
      await ms(100);
    }
  }

  async function waitUrlChange(secs) {
    const start = page.url();
    for (let i = 0; i < secs; i++) {
      await ms(1000);
      if (page.url() !== start) return true;
    }
    return false;
  }

  // ══════════════════════════════════════════════════════════
  console.log('=== Start funnel ===');
  await goto(`https://vplink.in/${VPLINK_KEY}`);
  await ms(3000);

  for (let cycle = 0; cycle < 20 && !destinationUrl; cycle++) {
    try {
    const url = page.url();
    console.log(`\n[${cycle+1}] ${url.substring(0, 100)}`);

    if (url.includes('wistful') || url.includes('vv53243') || url.includes('casino') || url.includes('one-')) {
      destinationUrl = url; break;
    }

    // ── vplink.in ──────────────────────────────────────────
    if (url.includes('vplink')) {
      console.log('  ★ Find Get Link...');
      for (let i = 0; i < 40; i++) {
        await page.evaluate(() => window.scrollTo({ top: 800, behavior: 'smooth' }));
        await ms(400);
        if (await clickText('Get Link')) {
          console.log('  ✅ Get Link clicked — wait 5s');
          await ms(5000);
          destinationUrl = page.url();
          break;
        }
        await ms(2000);
      }
      if (destinationUrl) console.log('  →', destinationUrl.substring(0, 80));
      continue;
    }

    // ── #startCountdownBtn (verify) ─────────────────────────
    if (await clickId('startCountdownBtn')) {
      console.log('  ✅ verify — wait for timer + ad...');
      let destFound = false;

      for (let i = 0; i < 120; i++) {
        const u = page.url();
        if (u.includes('wistful') || u.includes('vv53243') || u.includes('casino') || u.includes('one-')) {
          destinationUrl = u; destFound = true; break;
        }
        if (u.includes('vplink')) { destFound = true; break; }

        // ~35s: timer done, rewarded ad should appear
        if (i === 35 || i === 45 || i === 55 || i === 65) {
          await page.evaluate(() => {
            document.querySelectorAll('[id*="modal"], [id*="overlay"], [class*="modal"], [class*="overlay"]').forEach(e => e.remove());
            window.scrollTo({ top: 800, behavior: 'smooth' });
          });
          await ms(500);
          // Try various interactions
          await clickText('Continue');
          await clickText('Close');
          await clickText('Get Link');
          // Try clicking any visible button
          await page.evaluate(() => {
            document.querySelectorAll('button, .btn, a.ce-btn, [class*="btn"]').forEach(e => {
              if (e.offsetParent !== null) e.click();
            });
          });
          await ms(1000);

          // If stuck on #goog_rewarded, try learn_more.php
          if (u.includes('#goog_rewarded') || i >= 45) {
            const base = parentDirUrl();
            if (base) {
              console.log('  → learn_more.php attempt');
              await goto(base + '/learn_more.php').catch(() => {});
              await ms(4000);
            }
          }
        }
        await ms(1000);
      }

      if (!destFound) console.log('  ✗ verify handler exhausted');
      if (destinationUrl) console.log('  →', destinationUrl.substring(0, 80));
      continue;
    }

    // ── onlinewish ─────────────────────────────────────────
    if (url.includes('onlinewish')) {
      if (await clickSel('#btn7 > button.ce-btn.ce-blue')) {
        console.log('  ✅ #btn7 Continue');
        await ms(4000);
        if (page.url() === url) {
          console.log('  → same page, learn_more click');
          await clickLearnMoreSameDomain();
          await ms(5000);
        }
        continue;
      }
      await scrollDown();
      if (await clickText('Continue')) { console.log('  ✅ Continue text'); await ms(5000); continue; }
      if (await clickLearnMoreSameDomain()) { console.log('  ✅ learn_more link'); await ms(5000); continue; }
      console.log('  Wait 30s...');
      if (await waitUrlChange(30)) { console.log('  ✓ auto-redirect'); continue; }
      const base = parentDirUrl();
      if (base) { await goto(base + '/learn_more.php').catch(() => {}); await ms(5000); }
      continue;
    }

    // ── whatsgrouphub ──────────────────────────────────────
    if (url.includes('whatsgrouphub')) {
      await scrollDown();
      await ms(500);
      if (await clickId('startCountdownBtn')) { console.log('  ✅ verify on wgh'); await ms(5000); continue; }

      await page.evaluate(() => window.scrollTo({ top: 99999, behavior: 'smooth' }));
      await ms(2000);

      if (await clickLearnMoreSameDomain()) {
        console.log('  ✅ learn_more clicked');
        await ms(8000);
        const moved = await waitUrlChange(10);
        if (moved) { console.log('  ✓ redirected'); continue; }
        continue;
      }

      console.log('  Wait 45s...');
      const startUrl = page.url();
      let moved = false;
      for (let i = 0; i < 45; i++) {
        if (page.url() !== startUrl) { moved = true; break; }
        if (i > 0 && i % 10 === 0) await page.evaluate(() => window.scrollTo({ top: 99999, behavior: 'instant' }));
        await ms(1000);
      }
      if (moved) { console.log('  ✓ auto-redirect'); continue; }

      const base = parentDirUrl();
      if (base) {
        console.log('  → goto learn_more.php');
        await goto(base + '/learn_more.php').catch(() => {});
        await ms(5000);
        if (await waitUrlChange(15)) { console.log('  ✓ lm redirect'); continue; }
      }

      console.log('  → restart');
      await goto(`https://vplink.in/${VPLINK_KEY}`).catch(() => {});
      await ms(3000);
      continue;
    }

    console.log('  ⚠ unknown — restart');
    await goto(`https://vplink.in/${VPLINK_KEY}`).catch(() => {});
    await ms(3000);
  } catch (e) {
    console.log('  ⚠ error in cycle, continuing:', e.message.substring(0, 60));
  }
  }

  if (!destinationUrl) destinationUrl = page.url();
  console.log('\n═════════════════════════════════════════');
  console.log('  ✅ DESTINATION URL:');
  console.log('  ' + destinationUrl);
  const outDir = process.env.VPLINK_DIR || __dirname;
  fs.writeFileSync(outDir + '/destination_url.txt', destinationUrl);
  await ms(5000);
  await browser.close();
})();
