import { test, expect } from '@playwright/test';

const BASE_URL = process.env.QA_LOS_BASE_URL || 'https://los.finexusinc.ai';
const ADMIN_USERNAME = process.env.QA_LOS_USERNAME || '';
const ADMIN_PASSWORD = process.env.QA_LOS_PASSWORD || '';

test.describe('LOS Application Discovery', () => {

  test('Discover available applications in LOS', async ({ page }) => {
    console.log('\n📋 LOS APPLICATION DISCOVERY DIAGNOSTIC\n');
    console.log(`🔐 Logging in as: ${ADMIN_USERNAME}`);

    // Navigate to LOS
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    const currentUrl = page.url();
    console.log(`📍 Current URL: ${currentUrl}`);

    // Check if login page
    if (currentUrl.includes('/login')) {
      console.log('✓ On login page - performing authentication...\n');

      // Try to find and fill login form
      const usernameInput = page.locator('input[name*="username"], input[type="text"], input[placeholder*="email"]').first();
      const passwordInput = page.locator('input[type="password"]').first();

      if (await usernameInput.isVisible() && await passwordInput.isVisible()) {
        console.log('✓ Login form elements found');

        await usernameInput.fill(ADMIN_USERNAME);
        await passwordInput.fill(ADMIN_PASSWORD);

        // Find and click login button
        const loginButton = page.locator('button:has-text("Login"), button:has-text("Sign In"), button[type="submit"]').first();

        if (await loginButton.isVisible()) {
          console.log('✓ Clicking login button...');
          await loginButton.click();
          await page.waitForLoadState('networkidle');
          await page.waitForTimeout(2000);

          console.log(`✓ Login completed`);
          console.log(`📍 Post-login URL: ${page.url()}\n`);
        }
      }
    }

    // Now look for applications
    console.log('🔍 SEARCHING FOR APPLICATIONS...\n');

    // Method 1: Look for table rows
    const tableRows = page.locator('table tbody tr, [role="row"]');
    const rowCount = await tableRows.count();
    console.log(`📊 Found ${rowCount} table rows`);

    if (rowCount > 0) {
      console.log('\n📋 APPLICATION LIST:');
      for (let i = 0; i < Math.min(rowCount, 20); i++) {
        const row = tableRows.nth(i);
        const cells = row.locator('td, [role="cell"]');
        const cellCount = await cells.count();

        const rowText = await row.textContent();
        console.log(`   Row ${i + 1}: ${rowText?.trim().substring(0, 100)}`);

        // Try to extract app ID
        const appIdCell = cells.first();
        if (await appIdCell.isVisible()) {
          const appId = await appIdCell.textContent();
          console.log(`      └─ App ID: ${appId?.trim()}`);
        }
      }
    }

    // Method 2: Look for app links/cards
    console.log('\n🔗 SEARCHING FOR APP LINKS/CARDS...\n');
    const appLinks = page.locator('a:has-text("APP-"), [data-testid*="application"], .app-card, [data-app-id]');
    const linkCount = await appLinks.count();
    console.log(`Found ${linkCount} app-related links/cards`);

    if (linkCount > 0) {
      for (let i = 0; i < Math.min(linkCount, 20); i++) {
        const link = appLinks.nth(i);
        const text = await link.textContent();
        const appId = await link.getAttribute('data-app-id');
        console.log(`   ${i + 1}. ${text?.trim()} (data-app-id: ${appId})`);
      }
    }

    // Method 3: Look for any text containing "APP-"
    console.log('\n🔎 SEARCHING FOR "APP-" PATTERN...\n');
    const appPattern = page.locator('text=/APP-[0-9]+/');
    const patternCount = await appPattern.count();
    console.log(`Found ${patternCount} elements with "APP-" pattern`);

    if (patternCount > 0) {
      for (let i = 0; i < Math.min(patternCount, 20); i++) {
        const element = appPattern.nth(i);
        const text = await element.textContent();
        console.log(`   ${i + 1}. ${text?.trim()}`);
      }
    }

    // Method 4: Screenshot for visual inspection
    console.log('\n📸 Taking screenshot for visual inspection...');
    await page.screenshot({ path: '/tmp/los-applications-screenshot.png', fullPage: true });
    console.log('✓ Screenshot saved: /tmp/los-applications-screenshot.png');

    // Method 5: Inspect page HTML for hidden data
    console.log('\n🔬 INSPECTING PAGE DATA...\n');

    // Check for JSON data in page
    const jsonScripts = page.locator('script[type="application/json"]');
    const jsonCount = await jsonScripts.count();
    console.log(`Found ${jsonCount} JSON script tags`);

    // Look for data attributes
    const dataElements = page.locator('[data-*]');
    const dataCount = await dataElements.count();
    console.log(`Found ${dataCount} elements with data attributes`);

    // Summary
    console.log('\n' + '='.repeat(60));
    console.log('SUMMARY');
    console.log('='.repeat(60));
    console.log(`✓ Authentication: ${ADMIN_USERNAME}`);
    console.log(`✓ Portal URL: ${BASE_URL}`);
    console.log(`✓ Current Page: ${page.url()}`);
    console.log(`✓ Table Rows Found: ${rowCount}`);
    console.log(`✓ App Links Found: ${linkCount}`);
    console.log(`✓ APP- Pattern Matches: ${patternCount}`);
    console.log('\n💡 RECOMMENDATIONS:');
    if (rowCount === 0 && linkCount === 0 && patternCount === 0) {
      console.log('   ⚠️  No applications found!');
      console.log('   → Application may not exist in QA');
      console.log('   → User may not have access');
      console.log('   → Need to create test application first');
    } else {
      console.log('   ✓ Applications are visible');
      console.log('   → Choose one from the list above');
      console.log('   → Update QA_APPLICATION_ID environment variable');
    }
    console.log('='.repeat(60) + '\n');
  });
});
