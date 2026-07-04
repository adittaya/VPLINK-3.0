const { chromium } = require('playwright');
const URL = 'http://ipinfo.io/ip';

(async () => {
  const proxyUrl = process.argv[2];
  if (!proxyUrl) { process.exit(1); }

  const t0 = Date.now();
  let browser;
  try {
    browser = await chromium.launch({
      headless: true,
      proxy: { server: proxyUrl },
    });
    const page = await browser.newPage();
    await page.goto(URL, { timeout: 15000 });
    const body = await page.textContent('body');
    const ip = (body || '').trim();
    if (!ip) throw new Error('no ip');
    const ms = Date.now() - t0;
    console.log(ms);
    await browser.close();
    process.exit(0);
  } catch (e) {
    if (browser) await browser.close().catch(() => {});
    process.exit(1);
  }
})();
