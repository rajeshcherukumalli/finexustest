import { test, expect } from '@playwright/test';

const BASE_URL = process.env.QA_LOS_BASE_URL || 'https://los.finexusinc.ai';
const ADMIN_USERNAME = process.env.QA_LOS_USERNAME || '';
const ADMIN_PASSWORD = process.env.QA_LOS_PASSWORD || '';

test.describe('LOS Login & Application Discovery (v2)', () => {

  test('Improved login and application discovery', async ({ page }) => {
    console.log('\n📋 LOS LOGIN & APPLICATION DISCOVERY (v2)\n');

    // Navigate to LOS
    await page.goto(BASE_URL);
    await page.waitForTimeout(2000);

    console.log('🔐 Attempting login...\n');

    // Find and fill login form
    const usernameInput = page.locator('input[placeholder*="mail"], input[name*="email"], input[type="text"]').first();
    const passwordInput = page.locator('input[type="password"]').first();

    if (await usernameInput.isVisible()) {
      console.log('✓ Found username input');
      await usernameInput.clear();
      await usernameInput.fill(ADMIN_USERNAME);

      console.log('✓ Found password input');
      await passwordInput.clear();
      await passwordInput.fill(ADMIN_PASSWORD);

      // Find login button
      const signInButton = page.locator('button:has-text("Signing In"), button:has-text("Sign In"), button:has-text("Login")').first();

      if (await signInButton.isVisible()) {
        console.log('✓ Clicking sign-in button...');
        await signInButton.click();

        // Wait much longer for login to complete
        console.log('⏳ Waiting for login to complete (up to 15 seconds)...');

        // Wait for either:
        // 1. URL to change from login
        // 2. A new page element to appear
        // 3. Loading spinner to disappear
        let loginCompleted = false;

        for (let attempt = 0; attempt < 30; attempt++) {
          await page.waitForTimeout(500);

          const currentUrl = page.url();
          const isStillLogin = currentUrl.includes('/login');
          const hasApplications = await page.locator('table, [role="grid"], [data-testid*="application"]').count() > 0 ||
                                   await page.locator('text=/APP-[0-9]+/').count() > 0;
          const hasDashboard = await page.locator('h1, .dashboard-title, [data-testid*="dashboard"]').count() > 0;
          const hasError = await page.locator('[role="alert"], .error-message').count() > 0 ||
                           await page.locator('text=/error|failed|invalid/i').count() > 0;

          if (hasError) {
            console.log(`⚠️  ERROR DETECTED: Login may have failed`);
            const errorText = await page.locator('[role="alert"], .error-message').first().textContent();
            console.log(`   Error: ${errorText}`);
            break;
          }

          if (!isStillLogin && hasApplications) {
            console.log(`✅ Login successful! Found applications at ${currentUrl}`);
            loginCompleted = true;
            break;
          }

          if (!isStillLogin && hasDashboard) {
            console.log(`✅ Login successful! Dashboard loaded at ${currentUrl}`);
            loginCompleted = true;
            break;
          }

          if (!isStillLogin) {
            console.log(`✅ Login successful! Moved to ${currentUrl}`);
            loginCompleted = true;
            break;
          }

          process.stdout.write('.');
        }

        console.log('\n');
        console.log(`📍 Final URL: ${page.url()}`);
        console.log(`✓ Login completed: ${loginCompleted}`);
      }
    }

    // Now check what's on the page
    await page.waitForTimeout(2000);

    console.log('\n🔍 SEARCHING FOR APPLICATIONS...\n');

    // Check page title and main content
    const title = await page.title();
    const heading = await page.locator('h1, h2, .page-title').first().textContent();
    console.log(`📄 Page Title: ${title}`);
    console.log(`📄 Page Heading: ${heading}`);

    // Look for any table data
    const allText = await page.locator('body').textContent();
    console.log(`\n📄 Page contains "APP-" references: ${allText?.includes('APP-') ? 'YES' : 'NO'}`);
    console.log(`📄 Page contains "application": ${allText?.includes('application') ? 'YES' : 'NO'}`);
    console.log(`📄 Page contains "loan": ${allText?.includes('loan') ? 'YES' : 'NO'}`);

    // Screenshot current state
    console.log('\n📸 Taking screenshot...');
    await page.screenshot({ path: '/tmp/los-diagnostic-v2-screenshot.png', fullPage: true });
    console.log('✓ Screenshot saved');

    // Try navigating to dashboard directly
    console.log('\n🔗 Trying direct navigation to dashboard...');
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForTimeout(2000);

    const dashboardUrl = page.url();
    console.log(`📍 Dashboard URL: ${dashboardUrl}`);

    // Look for applications on dashboard
    const tableRows = page.locator('table tbody tr, [role="row"]');
    const rowCount = await tableRows.count();
    console.log(`\n📊 Table rows on dashboard: ${rowCount}`);

    if (rowCount > 0) {
      console.log('\n📋 APPLICATIONS FOUND:');
      for (let i = 0; i < Math.min(rowCount, 20); i++) {
        const row = tableRows.nth(i);
        const rowText = await row.textContent();
        console.log(`   ${i + 1}. ${rowText?.trim().substring(0, 120)}`);
      }
    } else {
      // Try looking for applications in different format
      const appElements = page.locator('text=/APP-[0-9]+/');
      const appCount = await appElements.count();
      console.log(`📋 Elements with "APP-" pattern: ${appCount}`);

      if (appCount > 0) {
        console.log('\n📋 APPLICATIONS FOUND:');
        for (let i = 0; i < Math.min(appCount, 20); i++) {
          const elem = appElements.nth(i);
          const text = await elem.textContent();
          console.log(`   ${i + 1}. ${text?.trim()}`);
        }
      }
    }

    // Final screenshot
    await page.screenshot({ path: '/tmp/los-diagnostic-v2-dashboard.png', fullPage: true });
    console.log('\n✓ Dashboard screenshot saved');
  });
});
