import { test } from '@playwright/test';

const BASE_URL = process.env.QA_LOS_BASE_URL || 'https://los.finexusinc.ai';
const ADMIN_USERNAME = process.env.QA_LOS_USERNAME || '';
const ADMIN_PASSWORD = process.env.QA_LOS_PASSWORD || '';

test.describe('LOS Complete Menu Scraper', () => {

  test('Scrape ALL visible menus and navigation', async ({ browser }) => {
    console.log('\n🔍 COMPLETE LOS MENU SCRAPER\n');

    const context = await browser.newContext();
    const page = await context.newPage();

    // Login
    console.log('🔐 Logging in...\n');
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

    console.log('✅ Logged in successfully\n');

    // Get ALL text on the page
    const allText = await page.locator('body').textContent();
    const lines = allText?.split('\n').map(l => l.trim()).filter(l => l.length > 0) || [];

    console.log('📄 ALL PAGE CONTENT (Line by line):\n');
    console.log('═'.repeat(70));
    for (let i = 0; i < Math.min(lines.length, 100); i++) {
      const line = lines[i];
      // Highlight potential menu items
      if (line.length < 80 &&
          !line.includes('Lorem') &&
          !line.includes('©') &&
          line.match(/^[A-Z]/)) {
        console.log(`${i}: ${line}`);
      }
    }
    console.log('═'.repeat(70) + '\n');

    // Get structured menu items
    console.log('📍 DETECTED MENU/TAB ITEMS:\n');

    const menuKeywords = [
      'Dashboard', 'Applications', 'Loan', 'Onboarding', 'Analytics',
      'Settings', 'Access', 'Management', 'Profiles', 'Reports',
      'Users', 'Admin', 'Logout', 'LMS', 'Borrowers', 'Lending',
      'Underwriting', 'Closing', 'Portfolio', 'Business'
    ];

    const foundMenus = [];

    for (const keyword of menuKeywords) {
      const elements = await page.locator(`text="${keyword}"`).all();
      if (elements.length > 0) {
        const element = elements[0];
        const isVisible = await element.isVisible().catch(() => false);
        if (isVisible) {
          foundMenus.push(keyword);
          console.log(`✅ ${keyword}`);
        }
      }
    }

    console.log(`\n📊 Total Menu Items Found: ${foundMenus.length}\n`);
    console.log('Items:', foundMenus.join(', '), '\n');

    // Take full page screenshot
    console.log('📸 Taking full page screenshot...');
    await page.screenshot({ path: '/tmp/los-complete-menu.png', fullPage: true });
    console.log('✓ Screenshot saved\n');

    // Get sidebar structure
    console.log('🔎 SIDEBAR STRUCTURE:\n');
    const sidebar = page.locator('[class*="sidebar"], [class*="nav"], aside, [role="navigation"]').first();
    if (await sidebar.isVisible().catch(() => false)) {
      const sidebarText = await sidebar.textContent() || '';
      const sidebarLines = sidebarText.split('\n').filter(l => l.trim().length > 0);
      console.log('Sidebar items:');
      for (const line of sidebarLines.slice(0, 20)) {
        console.log(`  • ${line.trim()}`);
      }
    } else {
      console.log('No sidebar found');
    }

    console.log('\n✅ Scraping complete!\n');

    await context.close();
  });
});
