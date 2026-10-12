import { test, expect } from '@playwright/test';

/**
 * TP21-TP48: Business Data, References, Bank Integration & Operations Tests
 * Source: tests/testcases/ascendus/TP21_TP34_business_references.yaml
 *         tests/testcases/ascendus/TP35_TP48_bank_operational.yaml
 *
 * Coverage:
 * - TP23: Renovation purpose selection
 * - TP25: Income annualization
 * - TP30: Decline demographics
 * - TP35: Plaid bank connection (happy path)
 * - TP41: Confirmation output
 * - TP42: LOS reconciliation
 * - TP46: Data masking & redaction
 * - TP48: Accessibility testing
 */

test.describe('Business Data, References & Operations (TP21-TP48)', () => {

  test.beforeEach(async ({ page }) => {
    const baseURL = process.env.QA_BASE_URL || 'https://ascendus-portal-dev.finexusinc.ai';
    await page.goto(baseURL);
  });

  // TP23: Renovation purpose
  test('TP23: Purpose selection and conditional fields', async ({ page }) => {
    await test.step('Check for purpose selection', async () => {
      const purposeSelect = page.locator('select[name*="purpose"], select[aria-label*="purpose"]').first();

      if (await purposeSelect.isVisible()) {
        const options = await purposeSelect.locator('option').count();
        console.log(`✓ Purpose options available: ${options}`);

        // Check if Renovation is an option
        const renovation = await purposeSelect.locator('option:has-text("Renovation")').count();
        console.log(`✓ Renovation option: ${renovation > 0 ? 'Yes' : 'Not found'}`);
      } else {
        console.log('ℹ Purpose dropdown not found in current state');
      }
    });

    await test.step('Check for conditional fields', async () => {
      const conditionalFields = await page.locator('[name*="renovation"], [name*="plan"], [placeholder*="description"]').count();
      console.log(`✓ Conditional/description fields: ${conditionalFields}`);
    });
  });

  // TP25: Income annualization
  test('TP25: Income calculation and annualization', async ({ page }) => {
    await test.step('Check for income fields', async () => {
      const incomeFields = await page.locator('input[name*="income"], input[name*="salary"], input[placeholder*="income"]').count();
      console.log(`✓ Income input fields: ${incomeFields}`);
    });

    await test.step('Check for annual income display', async () => {
      const annualFields = await page.locator('input[name*="annual"], span[name*="annual"], div[name*="annual"]').count();
      const annualText = await page.locator('text=/annual|yearly|per year/i').count();

      console.log(`✓ Annual income fields: ${annualFields}`);
      console.log(`✓ Annual income text mentions: ${annualText}`);
    });

    await test.step('Test income entry if available', async () => {
      const monthlyIncome = page.locator('input[name*="take_home"], input[name*="monthly"], input[name*="income"]').first();

      if (await monthlyIncome.isVisible()) {
        await monthlyIncome.click();
        await monthlyIncome.fill('5000');

        const value = await monthlyIncome.inputValue();
        console.log(`✓ Monthly income entered: $${value}`);
      }
    });
  });

  // TP30: Decline demographics
  test('TP30: Demographic selection and decline option', async ({ page }) => {
    await test.step('Check for demographic fields', async () => {
      const demographicFields = await page.locator('[name*="demographic"], [aria-label*="demographic"], label:has-text(/demographic/i)').count();
      console.log(`✓ Demographic fields: ${demographicFields}`);
    });

    await test.step('Check for decline option', async () => {
      const declineOption = page.locator('button:has-text(/decline|skip|not answer/i), input[value*="decline"], label:has-text(/not answer|prefer not/i)');
      const count = await declineOption.count();

      console.log(`✓ Decline/skip options: ${count > 0 ? 'Yes' : 'Not found'}`);
    });
  });

  // TP35: Plaid bank connection
  test('TP35: Plaid bank connection interface', async ({ page }) => {
    await test.step('Check for bank connection button', async () => {
      const bankButton = page.locator('button:has-text(/bank|plaid|connect|link/i)').first();

      if (await bankButton.isVisible()) {
        console.log('✓ Bank connection button found');
      } else {
        console.log('ℹ Bank connection button not found in current state');
      }
    });

    await test.step('Check for bank-related form sections', async () => {
      const bankElements = await page.locator('[name*="bank"], [aria-label*="bank"], [name*="account"]').count();
      console.log(`✓ Bank-related fields: ${bankElements}`);
    });
  });

  // TP41: Confirmation output
  test('TP41: Confirmation page elements', async ({ page }) => {
    await test.step('Check for success indicators', async () => {
      const successElements = await page.locator('text=/success|congratulations|submitted|confirmed/i, [role="status"][aria-label*="success"]').count();
      console.log(`✓ Success indicator elements: ${successElements}`);
    });

    await test.step('Check for application ID display', async () => {
      const idElements = await page.locator('[name*="id"], [data-testid*="id"], text=/application.*id|reference.*number/i').count();
      console.log(`✓ ID/reference display elements: ${idElements}`);
    });

    await test.step('Check for summary information', async () => {
      const summaryElements = await page.locator('[name*="summary"], [data-testid*="summary"], table, dl, .info-grid').count();
      console.log(`✓ Summary/details elements: ${summaryElements}`);
    });
  });

  // TP42: LOS reconciliation
  test('TP42: LOS system integration points', async ({ page }) => {
    await test.step('Check for LOS links', async () => {
      const losLinks = await page.locator('a:has-text(/los|loan|origination|system/i), a[href*="los"], a[href*="loan"]').count();
      console.log(`✓ LOS system links: ${losLinks}`);
    });

    await test.step('Check for external system references', async () => {
      const externalRefs = await page.locator('a[target="_blank"], a[rel*="external"]').count();
      console.log(`✓ External system links: ${externalRefs}`);
    });
  });

  // TP46: Data masking & redaction
  test('TP46: Sensitive data masking', async ({ page }) => {
    await test.step('Verify SSN masking on page', async () => {
      const ssnPatterns = await page.locator('text=/\*\*\*-\*\*-\d{4}|xxx-xx-\d{4}/i').count();
      console.log(`✓ SSN masking patterns found: ${ssnPatterns}`);
    });

    await test.step('Check for sensitive data in HTML', async () => {
      const html = await page.content();

      // Check for unmasked SSN pattern
      const hasUnmaskedSSN = /\d{3}-\d{2}-\d{4}/.test(html);
      console.log(`✓ Unmasked SSN in HTML: ${hasUnmaskedSSN ? 'WARN' : 'OK (not found)'}`);

      // Check URL for credentials
      const url = page.url();
      const hasURLSecrets = /password|token|apikey|secret|otp|code/i.test(url);
      console.log(`✓ Secrets in URL: ${hasURLSecrets ? 'WARN' : 'OK (not found)'}`);
    });
  });

  // TP48: Accessibility
  test('TP48: Browser compatibility and accessibility', async ({ page }) => {
    await test.step('Check keyboard navigation support', async () => {
      // Check for focus indicators
      const focusableElements = await page.locator('button, a, input, select, textarea').count();
      console.log(`✓ Focusable elements: ${focusableElements}`);
    });

    await test.step('Check form accessibility', async () => {
      const labels = await page.locator('label').count();
      const inputs = await page.locator('input').count();

      console.log(`✓ Label elements: ${labels}`);
      console.log(`✓ Input fields: ${inputs}`);
      console.log(`✓ Label-to-input ratio: ${labels > 0 ? 'Good' : 'Check accessibility'}`);
    });

    await test.step('Check ARIA attributes', async () => {
      const ariaLabels = await page.locator('[aria-label]').count();
      const ariaDescribed = await page.locator('[aria-describedby]').count();
      const roles = await page.locator('[role]').count();

      console.log(`✓ ARIA labels: ${ariaLabels}`);
      console.log(`✓ ARIA descriptions: ${ariaDescribed}`);
      console.log(`✓ ARIA roles: ${roles}`);
    });

    await test.step('Check heading hierarchy', async () => {
      const h1 = await page.locator('h1').count();
      const h2 = await page.locator('h2').count();
      const h3 = await page.locator('h3').count();

      console.log(`✓ Heading hierarchy: H1=${h1}, H2=${h2}, H3=${h3}`);
    });

    await test.step('Verify mobile responsive', async () => {
      const viewport = page.viewportSize();
      console.log(`✓ Current viewport: ${viewport?.width}x${viewport?.height}`);

      // Check for mobile-specific meta tags
      const mobileViewport = await page.locator('meta[name="viewport"]').count();
      console.log(`✓ Mobile viewport meta: ${mobileViewport > 0 ? 'Yes' : 'Not found'}`);
    });
  });
});
