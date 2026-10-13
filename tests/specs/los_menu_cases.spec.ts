import { test, expect, Browser, BrowserContext, Page } from '@playwright/test';

const BASE_URL = process.env.QA_LOS_BASE_URL || 'https://los.finexusinc.ai';
const ADMIN_USERNAME = process.env.QA_LOS_USERNAME || '';
const ADMIN_PASSWORD = process.env.QA_LOS_PASSWORD || '';

let context: BrowserContext;
let page: Page;

test.describe.configure({ mode: 'serial' });

test.describe('LOS Menu Navigation', () => {

  test.beforeAll(async ({ browser }: { browser: Browser }) => {
    context = await browser.newContext();
    page = await context.newPage();
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    const usernameInput = page.locator('input[type="text"], input[placeholder*="mail"]').first();
    const passwordInput = page.locator('input[type="password"]').first();
    await usernameInput.fill(ADMIN_USERNAME);
    await passwordInput.fill(ADMIN_PASSWORD);
    await page.locator('button:has-text("SIGN IN"), button:has-text("Sign In")').first().click();
    await page.waitForLoadState('networkidle');
  });

  test.afterAll(async () => {
    await context.close();
  });

  const menuItem = (name: string) => page.locator(`text="${name}"`).first();

  test('MN01: Login lands on Home with sidebar visible', async () => {
    expect(page.url()).not.toContain('/login');
    await expect(menuItem('Dashboard')).toBeVisible({ timeout: 5000 });
  });

  test('MN02: Dashboard menu opens the Dashboard', async () => {
    await menuItem('Dashboard').click();
    await expect(page).toHaveURL(/tab=Dashboard/, { timeout: 5000 });
    await expect(page.locator('h1, h2, [class*="card"]').first()).toBeVisible({ timeout: 5000 });
  });

  test('MN03: Loan Applications lists applications', async () => {
    await menuItem('Loan Applications').click();
    await page.waitForTimeout(1500);
    const appIds = page.locator('text=/APP-[0-9]+/');
    await expect(appIds.first()).toBeVisible({ timeout: 5000 });
    expect(await appIds.count()).toBeGreaterThan(0);
  });

  test('MN04: Onboarding opens the Onboarding section', async () => {
    await menuItem('Onboarding').click();
    await expect(page).toHaveURL(/tab=Onboarding/, { timeout: 5000 });
    await expect(page.locator('input, button, h1, h2').first()).toBeVisible({ timeout: 5000 });
  });

  test('MN05: Settings opens the Settings section', async () => {
    // Known defect O1: Settings navigation has been observed ending on tab=Onboarding.
    await menuItem('Settings').click();
    await expect(page).toHaveURL(/tab=Settings/, { timeout: 5000 });
  });

  test('MN06: Analytics section is available on the Dashboard', async () => {
    await menuItem('Dashboard').click();
    await page.waitForTimeout(1000);
    await expect(menuItem('Analytics')).toBeVisible({ timeout: 5000 });
  });

  test('MN07: LMS button is visible and enabled', async () => {
    const lms = page.locator('button:has-text("LMS")').first();
    await expect(lms).toBeVisible({ timeout: 5000 });
    await expect(lms).toBeEnabled();
  });

  test('MN08: Selected section survives a page refresh', async () => {
    await menuItem('Onboarding').click();
    await expect(page).toHaveURL(/tab=Onboarding/, { timeout: 5000 });
    await page.reload();
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/tab=Onboarding/, { timeout: 5000 });
  });

  test('MN09: Full navigation cycle', async () => {
    const cycle = ['Dashboard', 'Loan Applications', 'Onboarding', 'Analytics', 'Settings', 'Dashboard'];
    for (const name of cycle) {
      await menuItem(name).click();
      await page.waitForTimeout(1000);
    }
    await expect(page).toHaveURL(/tab=Dashboard/, { timeout: 5000 });
  });
});
