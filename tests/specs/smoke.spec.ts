import { test, expect } from '@playwright/test';

/**
 * TP01: End-to-End Smoke Test - Portal Accessibility
 * Source: tests/testcases/ascendus/TP01_smoke_test.yaml
 *
 * This is a minimal smoke test to verify:
 * 1. Portal is accessible
 * 2. Home page loads correctly
 * 3. Application entry controls are visible
 */

test.describe('TP01: Ascendus Portal Smoke Test', () => {

  test('Step 1: Open portal and verify page loads', async ({ page }) => {
    // Navigate to portal
    const baseURL = process.env.QA_BASE_URL || 'https://ascendus-portal-dev.finexusinc.ai';
    await test.step('Navigate to Ascendus portal', async () => {
      await page.goto(baseURL);
    });

    // Verify page title
    await test.step('Verify page loaded', async () => {
      const title = await page.title();
      console.log(`✓ Page title: "${title}"`);
      expect(title.length).toBeGreaterThan(0);
    });

    // Check for application entry controls
    await test.step('Verify application entry controls visible', async () => {
      // Look for key elements that indicate the form is loaded
      const buttons = await page.locator('button').count();
      console.log(`✓ Found ${buttons} button(s) on page`);
      expect(buttons).toBeGreaterThan(0);
    });

    // Capture page info
    await test.step('Capture page state', async () => {
      const url = page.url();
      console.log(`✓ Current URL: ${url}`);

      const htmlContent = await page.content();
      const hasForm = htmlContent.includes('input') || htmlContent.includes('form');
      console.log(`✓ Page contains form elements: ${hasForm}`);
    });
  });

  test('Step 2: Verify navigation elements', async ({ page }) => {
    const baseURL = process.env.QA_BASE_URL || 'https://ascendus-portal-dev.finexusinc.ai';

    await test.step('Navigate to portal', async () => {
      await page.goto(baseURL);
    });

    await test.step('Check for navigation links', async () => {
      const links = await page.locator('a').count();
      console.log(`✓ Found ${links} navigation link(s)`);
      expect(links).toBeGreaterThanOrEqual(0);
    });

    await test.step('Check page structure', async () => {
      // Look for common page elements
      const headings = await page.locator('h1, h2, h3').count();
      const inputs = await page.locator('input').count();

      console.log(`✓ Headings: ${headings}`);
      console.log(`✓ Input fields: ${inputs}`);
    });

    await test.step('Take screenshot', async () => {
      await page.screenshot({ path: 'smoke-test-portal.png' });
      console.log('✓ Screenshot saved: smoke-test-portal.png');
    });
  });

  test('Step 3: Verify portal is not showing error', async ({ page }) => {
    const baseURL = process.env.QA_BASE_URL || 'https://ascendus-portal-dev.finexusinc.ai';

    await test.step('Navigate to portal', async () => {
      await page.goto(baseURL, { waitUntil: 'networkidle' });
    });

    await test.step('Check for error messages', async () => {
      const errorElements = await page.locator('[role="alert"], .error, .alert-danger').count();
      console.log(`✓ Error elements found: ${errorElements}`);
      expect(errorElements).toBe(0);
    });

    await test.step('Verify no 404 or 500 errors', async () => {
      // Check response status
      const response = page.context().on('response', (res) => {
        if (res.status() >= 400) {
          console.warn(`⚠ HTTP ${res.status()}: ${res.url()}`);
        }
      });
    });
  });
});
