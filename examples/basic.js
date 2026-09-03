#!/usr/bin/env node
// Default JS example (Playwright): visit TARGET_URL, print title, screenshot.
// Usage:
//   npm install
//   node examples/basic.js
//   TARGET_URL=https://example.com HEADLESS=true node examples/basic.js
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const url = process.env.TARGET_URL || 'https://example.com';
  const headless = (process.env.HEADLESS || 'true').toLowerCase() !== 'false';
  const outDir = process.env.OUTPUT_DIR || 'output';
  fs.mkdirSync(outDir, { recursive: true });

  console.log(`[example] target   : ${url}`);
  console.log(`[example] headless : ${headless}`);

  const browser = await chromium.launch({ headless });
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    console.log(`[example] title    : ${JSON.stringify(await page.title())}`);
    const shot = path.join(outDir, `example_${Date.now()}.png`);
    await page.screenshot({ path: shot });
    console.log(`[example] screenshot: ${shot}`);
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error('[example] FAILED:', e.message); process.exit(1); });
