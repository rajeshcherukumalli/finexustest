import { test } from '@playwright/test';

const BASE_URL = process.env.QA_LOS_BASE_URL || 'https://los.finexusinc.ai';
const ADMIN_USERNAME = process.env.QA_LOS_USERNAME || '';
const ADMIN_PASSWORD = process.env.QA_LOS_PASSWORD || '';

test.describe('LOS Complete Menu Discovery', () => {

  test('Detailed menu and navigation exploration', async ({ browser }) => {
    console.log('\n🔍 DETAILED LOS MENU DISCOVERY\n');

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

    // Get all clickable elements on the page
    console.log('📍 ALL CLICKABLE ELEMENTS ON PAGE:\n');

    // Find all links
    const allLinks = await page.locator('a').all();
    console.log(`\n🔗 LINKS (${allLinks.length}):`);
    for (let i = 0; i < Math.min(allLinks.length, 30); i++) {
      const link = allLinks[i];
      const text = await link.textContent();
      const href = await link.getAttribute('href');
      const visible = await link.isVisible().catch(() => false);
      if (visible && text?.trim()) {
        console.log(`   ${i + 1}. ${text.trim()}`);
        if (href) console.log(`      └─ ${href}`);
      }
    }

    // Find all buttons
    const allButtons = await page.locator('button').all();
    console.log(`\n🔘 BUTTONS (${allButtons.length}):`);
    for (let i = 0; i < Math.min(allButtons.length, 30); i++) {
      const btn = allButtons[i];
      const text = await btn.textContent();
      const ariaLabel = await btn.getAttribute('aria-label');
      const visible = await btn.isVisible().catch(() => false);
      const label = text?.trim() || ariaLabel || '';
      if (visible && label) {
        console.log(`   ${i + 1}. ${label.substring(0, 60)}`);
      }
    }

    // Look for sidebar
    console.log(`\n📋 SIDEBAR/NAVIGATION SECTION:`);
    const sidebar = page.locator('[class*="sidebar"], [class*="nav"], [role="navigation"], aside').first();
    if (await sidebar.isVisible().catch(() => false)) {
      const sidebarText = await sidebar.textContent();
      console.log(sidebarText?.substring(0, 500) || 'No sidebar text');
    }

    // Look for specific menu items in sidebar
    console.log(`\n🔎 LOOKING FOR SPECIFIC MENU ITEMS:`);

    const menuTexts = [
      'Applications', 'Loan Applications', 'Onboarding', 'Dashboard',
      'Reports', 'Analytics', 'Settings', 'Users', 'Admin', 'Access',
      'Business', 'Borrowers', 'Profiles', 'Loan Origination'
    ];

    for (const menuText of menuTexts) {
      const element = page.locator(`text="${menuText}"`).first();
      const exists = await element.isVisible().catch(() => false);
      if (exists) {
        console.log(`   ✓ Found: "${menuText}"`);
      }
    }

    // Check for expandable/collapsible menus
    console.log(`\n📂 EXPANDABLE MENU SECTIONS:`);

    const expandableButtons = await page.locator('button[aria-expanded]').all();
    console.log(`Found ${expandableButtons.length} expandable buttons:\n`);

    for (let i = 0; i < expandableButtons.length; i++) {
      const btn = expandableButtons[i];
      const text = await btn.textContent();
      const expanded = await btn.getAttribute('aria-expanded');
      console.log(`${i + 1}. ${text?.trim()}`);
      console.log(`   └─ expanded: ${expanded}\n`);
    }

    // Look for dropdown menus
    console.log(`\n📊 DASHBOARD CARDS/SECTIONS:\n`);

    const cards = await page.locator('[class*="card"], [class*="panel"], [role="region"]').all();
    console.log(`Found ${cards.length} card/panel elements:\n`);

    for (let i = 0; i < Math.min(cards.length, 15); i++) {
      const card = cards[i];
      const text = await card.textContent();
      const heading = await card.locator('h1, h2, h3, h4, h5').first().textContent();
      if (heading?.trim()) {
        console.log(`${i + 1}. ${heading.trim()}\n`);
      }
    }

    // Get page title and main headings
    console.log(`\n📄 PAGE STRUCTURE:\n`);
    console.log(`Title: ${await page.title()}`);

    const h1 = await page.locator('h1').first().textContent();
    console.log(`H1: ${h1?.trim() || 'None'}`);

    const h2 = await page.locator('h2').first().textContent();
    console.log(`H2: ${h2?.trim() || 'None'}\n`);

    // Save full page screenshot
    console.log('📸 Saving full page screenshot...\n');
    await page.screenshot({ path: '/tmp/los-full-page.png', fullPage: true });
    console.log('✓ Screenshot saved to /tmp/los-full-page.png');

    await context.close();
  });
});
