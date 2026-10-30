const { chromium } = require(process.env.ISG_PLAYWRIGHT || 'playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.ISG_CHROMIUM ? { executablePath: process.env.ISG_CHROMIUM } : {}) });
  try {
    const base = process.env.ISG_BASE_URL || 'http://127.0.0.1:8088';
    const output = process.env.ISG_SCREENSHOT_DIR || process.env.TEMP || '.';
    for (const [name, width, height, route] of [
      ['home-desktop', 1440, 900, '/'],
      ['home-mobile', 390, 844, '/'],
      ['product-desktop', 1440, 900, '/products/allvend/'],
      ['product-mobile', 390, 844, '/products/allvend/'],
      ['industries-mobile', 390, 844, '/industries/'],
    ]) {
      const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
      await page.goto(base + route, { waitUntil: 'networkidle' });
      for (const image of await page.locator('img[loading="lazy"]').all()) {
        await image.scrollIntoViewIfNeeded();
        await image.evaluate(element => element.decode().catch(() => {}));
      }
      await page.evaluate(() => scrollTo(0, 0));
      await page.screenshot({ path: path.join(output, `isg-${name}.png`), fullPage: true });
      console.log(`${name} saved`);
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
