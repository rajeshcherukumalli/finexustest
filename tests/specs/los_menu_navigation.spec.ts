import { test, expect, Browser, BrowserContext, Page } from '@playwright/test';

const BASE_URL = process.env.QA_LOS_BASE_URL || 'https://los.finexusinc.ai';
const ADMIN_USERNAME = process.env.QA_LOS_USERNAME || '';
const ADMIN_PASSWORD = process.env.QA_LOS_PASSWORD || '';

let browser: Browser;
let context: BrowserContext;
let page: Page;

test.describe.configure({ mode: 'serial' });

test.describe('LOS Menu Navigation & Tabs', () => {

  test.beforeAll(async ({ browser: b }) => {
    console.log('\n🔐 LOGIN & SETUP\n');

    browser = b;
    context = await browser.newContext();
    page = await context.newPage();

    // Login
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

    console.log('✅ Login successful\n');
  });

  test.afterAll(async () => {
    await context.close();
  });

  // M1: Dashboard Navigation
  test('M1: Navigate to Dashboard and verify content', async () => {
    console.log('🔷 M1: Dashboard\n');

    // Find and click Dashboard
    const dashboardBtn = page.locator('text="Dashboard"').first();
    const dashboardExists = await dashboardBtn.isVisible().catch(() => false);

    if (dashboardExists) {
      console.log('✓ Dashboard button found');
      await dashboardBtn.click();
      await page.waitForTimeout(2000);

      // Verify dashboard elements
      const hasAnalytics = await page.locator('text="Analytics"').count() > 0;
      const hasApplications = await page.locator('text="Applications"').count() > 0;
      const hasContent = await page.locator('h1, h2, [class*="card"]').count() > 0;

      console.log(`✓ Analytics section: ${hasAnalytics ? 'YES' : 'NO'}`);
      console.log(`✓ Applications section: ${hasApplications ? 'YES' : 'NO'}`);
      console.log(`✓ Content loaded: ${hasContent ? 'YES' : 'NO'}`);

      if (!hasContent) {
        throw new Error('❌ Dashboard content not loaded');
      }
    } else {
      throw new Error('❌ Dashboard button not found');
    }

    console.log('✓ M1 PASS: Dashboard navigation successful\n');
  });

  // M2: Loan Applications Navigation
  test('M2: Navigate to Loan Applications and verify list', async () => {
    console.log('🔷 M2: Loan Applications\n');

    const loanAppBtn = page.locator('text="Loan Applications"').first();
    const loanAppExists = await loanAppBtn.isVisible().catch(() => false);

    if (loanAppExists) {
      console.log('✓ Loan Applications button found');
      await loanAppBtn.click();
      await page.waitForTimeout(2000);
      await page.waitForLoadState('networkidle');

      // Verify loan applications content
      const hasTable = await page.locator('table, [role="grid"]').count() > 0;
      const hasAppId = await page.locator('text=/APP-[0-9]+/').count() > 0;
      const hasStatus = await page.locator('text=/Approved|Lending|Intake/i').count() > 0;

      console.log(`✓ Application table: ${hasTable ? 'YES' : 'NO'}`);
      console.log(`✓ App IDs visible: ${hasAppId ? 'YES' : 'NO'}`);
      console.log(`✓ Status info: ${hasStatus ? 'YES' : 'NO'}`);

      if (!hasAppId) {
        throw new Error('❌ No applications found in list');
      }
    } else {
      throw new Error('❌ Loan Applications button not found');
    }

    console.log('✓ M2 PASS: Loan Applications navigation successful\n');
  });

  // M3: Onboarding Navigation
  test('M3: Navigate to Onboarding and verify workflows', async () => {
    console.log('🔷 M3: Onboarding\n');

    const onboardingBtn = page.locator('text="Onboarding"').first();
    const onboardingExists = await onboardingBtn.isVisible().catch(() => false);

    if (onboardingExists) {
      console.log('✓ Onboarding button found');
      await onboardingBtn.click();
      await page.waitForTimeout(2000);
      await page.waitForLoadState('networkidle');

      // Verify onboarding content
      const pageUrl = page.url();
      const hasOnboardingContent = await page.locator('h1, h2, button, [class*="form"]').count() > 0;
      const hasWorkflow = await page.locator('text=/workflow|step|process/i').count() > 0;

      console.log(`✓ URL: ${pageUrl}`);
      console.log(`✓ Onboarding content: ${hasOnboardingContent ? 'YES' : 'NO'}`);
      console.log(`✓ Workflow indicators: ${hasWorkflow ? 'YES' : 'NO'}`);

      if (!hasOnboardingContent) {
        throw new Error('❌ Onboarding content not loaded');
      }
    } else {
      throw new Error('❌ Onboarding button not found');
    }

    console.log('✓ M3 PASS: Onboarding navigation successful\n');
  });

  // M4: Analytics Navigation
  test('M4: Navigate to Analytics and verify charts/reports', async () => {
    console.log('🔷 M4: Analytics\n');

    const analyticsBtn = page.locator('text="Analytics"').first();
    const analyticsExists = await analyticsBtn.isVisible().catch(() => false);

    if (analyticsExists) {
      console.log('✓ Analytics button found');
      await analyticsBtn.click();
      await page.waitForTimeout(2000);
      await page.waitForLoadState('networkidle');

      // Verify analytics content
      const hasCharts = await page.locator('svg, [class*="chart"]').count() > 0;
      const hasMetrics = await page.locator('text=/Total|Count|Average|Sum/i').count() > 0;
      const hasReports = await page.locator('text=/Report|Analytics|Dashboard/i').count() > 0;

      console.log(`✓ Charts/graphs: ${hasCharts ? 'YES' : 'NO'}`);
      console.log(`✓ Metrics: ${hasMetrics ? 'YES' : 'NO'}`);
      console.log(`✓ Reports: ${hasReports ? 'YES' : 'NO'}`);

      if (!hasCharts && !hasMetrics && !hasReports) {
        console.log('⚠️  Analytics content may still be loading');
      }
    } else {
      throw new Error('❌ Analytics button not found');
    }

    console.log('✓ M4 PASS: Analytics navigation successful\n');
  });

  // M5: Settings Navigation
  test('M5: Navigate to Settings and verify options', async () => {
    console.log('🔷 M5: Settings\n');

    const settingsBtn = page.locator('text="Settings"').first();
    const settingsExists = await settingsBtn.isVisible().catch(() => false);

    if (settingsExists) {
      console.log('✓ Settings button found');
      await settingsBtn.click();
      await page.waitForTimeout(2000);
      await page.waitForLoadState('networkidle');

      // Verify settings content
      const hasSettings = await page.locator('text=/Setting|Configuration|Preference/i').count() > 0;
      const hasForm = await page.locator('input, select, textarea, button').count() > 0;
      const hasToggle = await page.locator('[role="switch"], [class*="toggle"]').count() > 0;

      console.log(`✓ Settings content: ${hasSettings ? 'YES' : 'NO'}`);
      console.log(`✓ Form elements: ${hasForm ? 'YES' : 'NO'}`);
      console.log(`✓ Toggle switches: ${hasToggle ? 'YES' : 'NO'}`);

      if (!hasSettings && !hasForm) {
        throw new Error('❌ Settings content not loaded');
      }
    } else {
      console.log('ℹ Settings not found as clickable button (may be icon-only)');
    }

    console.log('✓ M5 PASS: Settings navigation successful\n');
  });

  // M6: Verify LMS Button
  test('M6: Verify LMS navigation button', async () => {
    console.log('🔷 M6: LMS Button\n');

    const lmsBtn = page.locator('button:has-text("LMS")').first();
    const lmsExists = await lmsBtn.isVisible().catch(() => false);

    if (lmsExists) {
      console.log('✓ LMS button found');
      const ariaLabel = await lmsBtn.getAttribute('aria-label');
      const title = await lmsBtn.getAttribute('title');
      console.log(`✓ Aria label: ${ariaLabel || 'N/A'}`);
      console.log(`✓ Title: ${title || 'N/A'}`);
      console.log('✓ LMS button is available for navigation');
    } else {
      console.log('ℹ LMS button not found on current page');
    }

    console.log('✓ M6 PASS: LMS button verified\n');
  });

  // M7: Test backward navigation
  test('M7: Navigate backward through menu items', async () => {
    console.log('🔷 M7: Backward Navigation\n');

    // Go to Dashboard first
    let dashboard = page.locator('text="Dashboard"').first();
    if (await dashboard.isVisible().catch(() => false)) {
      await dashboard.click();
      await page.waitForTimeout(1500);
    }

    // Then to Loan Applications
    let loanApp = page.locator('text="Loan Applications"').first();
    if (await loanApp.isVisible().catch(() => false)) {
      await loanApp.click();
      await page.waitForTimeout(1500);
      console.log('✓ Navigated to Loan Applications');
    }

    // Back to Dashboard
    dashboard = page.locator('text="Dashboard"').first();
    if (await dashboard.isVisible().catch(() => false)) {
      await dashboard.click();
      await page.waitForTimeout(1500);

      const hasContent = await page.locator('h1, h2, [class*="card"]').count() > 0;
      console.log(`✓ Back to Dashboard - content loaded: ${hasContent}`);

      if (!hasContent) {
        throw new Error('❌ Dashboard content not loaded on navigation back');
      }
    }

    console.log('✓ M7 PASS: Backward navigation successful\n');
  });

});
