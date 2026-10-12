import { test } from '@playwright/test';

const BASE_URL = process.env.QA_LOS_BASE_URL || 'https://los.finexusinc.ai';
const ADMIN_USERNAME = process.env.QA_LOS_USERNAME || '';
const ADMIN_PASSWORD = process.env.QA_LOS_PASSWORD || '';

test.describe('LOS Menu & Navigation Discovery', () => {

  test('Scrape entire menu structure after login', async ({ browser }) => {
    console.log('\n📋 LOS SIDE MENU & NAVIGATION DISCOVERY\n');

    const context = await browser.newContext();
    const page = await context.newPage();

    // Login
    console.log('🔐 Logging in...');
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    const usernameInput = page.locator('input[type="text"], input[placeholder*="mail"]').first();
    const passwordInput = page.locator('input[type="password"]').first();

    if (await usernameInput.isVisible()) {
      await usernameInput.fill(ADMIN_USERNAME);
      await passwordInput.fill(ADMIN_PASSWORD);

      const loginBtn = page.locator('button:has-text("SIGN IN"), button:has-text("Sign In")').first();
      if (await loginBtn.isVisible()) {
        await loginBtn.click();
        await page.waitForTimeout(4000);
        await page.waitForLoadState('networkidle');
      }
    }

    console.log('✅ Logged in\n');

    // Scrape sidebar menu
    console.log('📍 SIDE MENU ITEMS:\n');

    const menuItems = await page.locator('[role="navigation"] a, .sidebar a, .menu a, [data-testid*="menu"] a').all();
    console.log(`Found ${menuItems.length} menu items:\n`);

    for (let i = 0; i < menuItems.length; i++) {
      const item = menuItems[i];
      const text = await item.textContent();
      const href = await item.getAttribute('href');
      const icon = await item.locator('svg, [class*="icon"]').count();

      console.log(`${i + 1}. ${text?.trim()}`);
      console.log(`   └─ href: ${href || 'N/A'}`);
      console.log(`   └─ icon: ${icon > 0 ? 'YES' : 'NO'}\n`);
    }

    // Scrape top navigation/buttons
    console.log('\n📍 TOP NAVIGATION BUTTONS:\n');

    const topButtons = await page.locator('header button, .navbar button, [data-testid*="navbar"] button').all();
    console.log(`Found ${topButtons.length} top buttons:\n`);

    for (let i = 0; i < topButtons.length; i++) {
      const btn = topButtons[i];
      const text = await btn.textContent();
      const ariaLabel = await btn.getAttribute('aria-label');

      console.log(`${i + 1}. ${text?.trim() || ariaLabel || 'Unlabeled'}\n`);
    }

    // Scrape tabs/sections
    console.log('\n📍 TABS & SECTIONS:\n');

    const tabs = await page.locator('[role="tab"], .tab, [data-testid*="tab"]').all();
    console.log(`Found ${tabs.length} tabs:\n`);

    for (let i = 0; i < Math.min(tabs.length, 20); i++) {
      const tab = tabs[i];
      const text = await tab.textContent();
      const ariaSelected = await tab.getAttribute('aria-selected');

      console.log(`${i + 1}. ${text?.trim()}`);
      console.log(`   └─ active: ${ariaSelected === 'true' ? 'YES' : 'NO'}\n`);
    }

    // Take screenshot of menu
    console.log('📸 Taking screenshots...\n');
    await page.screenshot({ path: '/tmp/los-menu-screenshot.png', fullPage: true });
    console.log('✓ Full page screenshot saved\n');

    await context.close();
  });
});
