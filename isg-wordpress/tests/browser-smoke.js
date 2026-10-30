const { chromium } = require(process.env.ISG_PLAYWRIGHT || 'playwright');

const base = process.env.ISG_BASE_URL || 'http://127.0.0.1:8088';
const routes = ['/', '/news/', '/news/dear-polkadot-validators/', '/products/', '/products/allvend/', '/product-type/developments/', '/services/', '/service-group/web3/', '/downloads/', '/industries/', '/company/', '/company/mission/', '/company/history/', '/company/licenses/', '/company/partnership/', '/company/careers/', '/company/contacts/', '/support/', '/support/feedback/', '/shop/', '/cart/', '/wp-sitemap.xml', '/robots.txt'];

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.ISG_CHROMIUM ? { executablePath: process.env.ISG_CHROMIUM } : {}) });
  let failures = 0;
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    for (const route of routes) {
      const response = await page.goto(base + route, { waitUntil: /\.xml$|\.txt$/.test(route) ? 'domcontentloaded' : 'networkidle' });
      if (route === '/wp-sitemap.xml' || route === '/robots.txt') {
        const good = response.status() === 200 && /sitemap/i.test(await response.text());
        if (!good) failures++;
        console.log(`${viewport.width} ${route} ${response.status()} ${good ? 'OK' : 'FAIL'}`);
        continue;
      }
      const result = await page.evaluate(() => ({
        title: document.title,
        heading: document.querySelector('h1')?.textContent.trim() || '',
        overflow: document.documentElement.scrollWidth > window.innerWidth + 2,
        wide: [...document.querySelectorAll('body *')].filter(element => { const box = element.getBoundingClientRect(); return box.right > window.innerWidth + 2 && getComputedStyle(element).position !== 'fixed'; }).slice(0, 5).map(element => `${element.tagName.toLowerCase()}.${element.className || ''}`),
      }));
      const good = response.status() < 400 && result.heading && !result.overflow;
      if (!good) failures++;
      console.log(`${viewport.width} ${route} ${response.status()} ${good ? 'OK' : 'FAIL'} ${result.heading} ${result.overflow ? 'OVERFLOW ' + result.wide.join(', ') : ''}`);
    }
    if (viewport.width < 500) {
      await page.goto(base + '/', { waitUntil: 'domcontentloaded' });
      const button = page.locator('[data-menu-toggle]');
      await button.click();
      const open = await button.getAttribute('aria-expanded');
      if (open !== 'true' || !(await page.locator('#mobile-navigation').isVisible())) failures++;
      console.log(`mobile menu ${open === 'true' ? 'OK' : 'FAIL'}`);
    } else {
      await page.goto(base + '/', { waitUntil: 'domcontentloaded' });
      await page.locator('.main-nav .isg-menu > li').first().hover();
      const shown = await page.locator('.main-nav .isg-menu > li').first().locator('.sub-menu').isVisible();
      if (!shown) failures++;
      console.log(`desktop mega menu ${shown ? 'OK' : 'FAIL'}`);
    }
    await page.goto(base + '/downloads/?project=allvend&q=demo&count=10', { waitUntil: 'networkidle' });
    const fileNames = await page.locator('.download-item h3').allInnerTexts();
    const filtered = fileNames.length === 1 && fileNames[0].includes('ALLVEND demo');
    if (!filtered) failures++;
    console.log(`${viewport.width} downloads filter ${filtered ? 'OK' : 'FAIL'}`);
    await page.goto(base + '/', { waitUntil: 'networkidle' });
    await page.locator('[data-search-open]').click();
    await page.locator('[data-search-overlay] input[type="search"]').fill('ALLVEND');
    await page.locator('[data-search-overlay] input[type="search"]').press('Enter');
    await page.waitForURL(/\?s=ALLVEND/);
    const searchFound = (await page.locator('main').innerText()).includes('ALLVEND');
    if (!searchFound) failures++;
    console.log(`${viewport.width} site search ${searchFound ? 'OK' : 'FAIL'}`);
    if (errors.length) {
      failures += errors.length;
      console.log('JavaScript errors:', errors.join(' | '));
    }
    await page.close();
  }
  await browser.close();
  if (failures) process.exitCode = 1;
})().catch(error => { console.error(error); process.exitCode = 1; });
