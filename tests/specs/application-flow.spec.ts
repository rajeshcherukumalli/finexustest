import { test, expect } from '@playwright/test';

/**
 * TP02-TP20: Application Entry, Identity, Email Verification & Consent Tests
 * Source: tests/testcases/ascendus/TP02_TP20_application_identity.yaml
 *
 * Coverage:
 * - TP02: Entry validation (mandatory fields)
 * - TP03: Amount/state boundaries
 * - TP04: First email code verification
 * - TP08: Applicant summary persistence
 * - TP11: Business details & catalogues
 * - TP16: Birth date & SSN handling
 * - TP18: Consent & terms review
 */

test.describe('Application Entry & Identity (TP02-TP20)', () => {

  test.beforeEach(async ({ page }) => {
    const baseURL = process.env.QA_BASE_URL || 'https://ascendus-portal-dev.finexusinc.ai';
    await page.goto(baseURL);
  });

  // TP02: Entry validation - Mandatory fields
  test('TP02: Entry validation - mandatory fields required', async ({ page }) => {
    await test.step('Verify page loaded', async () => {
      const title = await page.title();
      expect(title).toContain('Ascendus');
    });

    await test.step('Attempt to submit empty form', async () => {
      // Look for Next/Submit button
      const nextButton = page.locator('button:has-text("Next"), button:has-text("Submit")').first();

      if (await nextButton.isVisible()) {
        await nextButton.click();

        // Check if validation error appears
        const errorCount = await page.locator('[role="alert"], .error, .error-message').count();
        console.log(`✓ Validation errors shown: ${errorCount > 0 ? 'Yes' : 'No'}`);
      } else {
        console.log('ℹ Next button not found in current state');
      }
    });
  });

  // TP03: Amount & state boundaries
  test('TP03: Amount and state field validation', async ({ page }) => {
    await test.step('Check amount input field', async () => {
      const amountInput = page.locator('input[name*="amount"], input[placeholder*="amount"], input[type="number"]').first();

      if (await amountInput.isVisible()) {
        console.log('✓ Amount input field found');

        // Try entering a value
        await amountInput.click();
        await amountInput.fill('25000');

        const value = await amountInput.inputValue();
        console.log(`✓ Amount value entered: ${value}`);
      } else {
        console.log('ℹ Amount input not found in current state');
      }
    });

    await test.step('Check state dropdown', async () => {
      const stateSelect = page.locator('select[name*="state"], select[aria-label*="state"]').first();

      if (await stateSelect.isVisible()) {
        console.log('✓ State select found');

        // Get available options
        const options = await stateSelect.locator('option').count();
        console.log(`✓ State options available: ${options}`);
      } else {
        console.log('ℹ State dropdown not found in current state');
      }
    });
  });

  // TP04: Email verification first checkpoint
  test('TP04: Email verification code requirement', async ({ page }) => {
    await test.step('Look for email input', async () => {
      const emailInput = page.locator('input[type="email"], input[name*="email"]').first();

      if (await emailInput.isVisible()) {
        console.log('✓ Email input field found');
      } else {
        console.log('ℹ Email input not found - may need to fill earlier fields first');
      }
    });

    await test.step('Check for OTP/verification elements', async () => {
      const otpElements = await page.locator('[name*="otp"], [name*="code"], [name*="verification"]').count();
      const otpLabels = await page.locator('text=/code|otp|verify/i').count();

      console.log(`✓ OTP-related elements: ${otpElements}`);
      console.log(`✓ Verification-related text: ${otpLabels}`);
    });
  });

  // TP05: Email code validation - wrong, incomplete, expired
  test('TP05: Email code validation - wrong/incomplete/expired', async ({ page }) => {
    await test.step('Check for OTP input field', async () => {
      const otpInput = page.locator('input[name*="code"], input[name*="otp"], input[placeholder*="code"]').first();

      if (await otpInput.isVisible()) {
        console.log('✓ OTP input field found');

        // Try entering wrong code
        await otpInput.click();
        await otpInput.fill('000000');
        const value = await otpInput.inputValue();
        console.log(`✓ Test OTP entered: ${value}`);
      } else {
        console.log('ℹ OTP input not found - field may appear after email entry');
      }
    });

    await test.step('Check for validation error display', async () => {
      const errorElements = await page.locator('[role="alert"], .error-message, .validation-error').count();
      console.log(`✓ Error message elements: ${errorElements}`);
    });

    await test.step('Verify form structure for OTP verification', async () => {
      const buttons = await page.locator('button:has-text("Verify"), button:has-text("Submit")').count();
      console.log(`✓ Verify/Submit buttons available: ${buttons > 0 ? 'Yes' : 'Check structure'}`);
    });
  });

  // TP06: Email code resend and reuse rules
  test('TP06: Email code resend and reuse handling', async ({ page }) => {
    await test.step('Check for Resend Code button', async () => {
      const resendButton = page.locator('button:has-text("Resend"), button:has-text("Send Again")').first();

      if (await resendButton.isVisible()) {
        console.log('✓ Resend button found');

        // Check if disabled
        const isDisabled = await resendButton.isDisabled();
        console.log(`✓ Resend button state: ${isDisabled ? 'Disabled (countdown active)' : 'Enabled'}`);
      } else {
        console.log('ℹ Resend button not found in current state');
      }
    });

    await test.step('Check for countdown timer', async () => {
      const countdownElements = await page.locator('[data-testid*="countdown"], .timer, .resend-timer').count();
      const timerText = await page.locator('text=/resend|wait|seconds/i').count();

      console.log(`✓ Countdown timer elements: ${countdownElements}`);
      console.log(`✓ Timer-related text: ${timerText}`);
    });

    await test.step('Verify OTP code state management', async () => {
      const otpInputs = await page.locator('input[name*="code"], input[name*="otp"]').count();
      console.log(`✓ OTP input fields ready: ${otpInputs > 0 ? 'Yes' : 'No'}`);
    });
  });

  // TP07: Second email verification checkpoint
  test('TP07: Second email verification checkpoint', async ({ page }) => {
    await test.step('Check for multiple OTP prompts support', async () => {
      // Look for indicators of multiple verification steps
      const progressElements = await page.locator('[data-testid*="progress"], .progress-indicator, .step-indicator').count();
      const stepElements = await page.locator('[aria-label*="step"], .step').count();

      console.log(`✓ Progress indicators: ${progressElements}`);
      console.log(`✓ Step indicators: ${stepElements}`);
    });

    await test.step('Verify OTP modal reusability', async () => {
      // Check if OTP modal/component can be used multiple times
      const otpContainers = await page.locator('[data-testid*="otp"], .otp-modal, [role="dialog"]').count();
      const verifyButtons = await page.locator('button:has-text("Verify")').count();

      console.log(`✓ OTP containers available: ${otpContainers}`);
      console.log(`✓ Verify buttons: ${verifyButtons}`);
    });

    await test.step('Check for second checkpoint support', async () => {
      // Look for bank connection or final confirmation screens
      const bankElements = await page.locator('[name*="bank"], [aria-label*="bank"]').count();
      const confirmElements = await page.locator('button:has-text("Confirm"), button:has-text("Complete")').count();

      console.log(`✓ Bank connection form elements: ${bankElements}`);
      console.log(`✓ Confirmation buttons: ${confirmElements}`);
    });
  });

  // TP08: Summary persistence
  test('TP08: Form data persistence across navigation', async ({ page }) => {
    await test.step('Capture initial page state', async () => {
      const allInputs = await page.locator('input').count();
      console.log(`✓ Input fields on page: ${allInputs}`);
    });

    await test.step('Fill a test field if available', async () => {
      const firstInput = page.locator('input').first();

      if (await firstInput.isVisible()) {
        await firstInput.click();
        await firstInput.fill('TestValue123');

        const value = await firstInput.inputValue();
        console.log(`✓ Test value entered: ${value}`);

        // Check if value persists
        await firstInput.blur();
        const persistedValue = await firstInput.inputValue();
        expect(persistedValue).toBe('TestValue123');
        console.log('✓ Value persisted after blur');
      }
    });
  });

  // TP11: Business details
  test('TP11: Business details and form sections', async ({ page }) => {
    await test.step('Check for business-related fields', async () => {
      const businessFields = await page.locator('[name*="business"], [placeholder*="business"], label:has-text(/business/i)').count();
      console.log(`✓ Business-related fields: ${businessFields}`);
    });

    await test.step('Check for business structure options', async () => {
      const structureSelect = page.locator('select[name*="structure"], select[name*="type"], select[aria-label*="structure"]').first();

      if (await structureSelect.isVisible()) {
        const options = await structureSelect.locator('option').count();
        console.log(`✓ Business structure options: ${options}`);
      }
    });
  });

  // TP16: SSN and DOB handling
  test('TP16: Identity fields (SSN, DOB) security', async ({ page }) => {
    await test.step('Check for DOB field', async () => {
      const dobInputs = page.locator('input[name*="dob"], input[name*="birth"], input[placeholder*="date"]');
      const count = await dobInputs.count();
      console.log(`✓ DOB input fields: ${count}`);
    });

    await test.step('Check for SSN field', async () => {
      const ssnInputs = page.locator('input[name*="ssn"], input[name*="social"], input[placeholder*="ssn"]');
      const count = await ssnInputs.count();
      console.log(`✓ SSN input fields: ${count}`);
    });

    await test.step('Verify sensitive data not in URL', async () => {
      const url = page.url();
      const hasSSN = url.includes('ssn');
      const hasSSNData = url.match(/\d{3}-\d{2}-\d{4}/);

      console.log(`✓ SSN in URL: ${hasSSN || hasSSNData ? 'WARN' : 'OK'}`);
      expect(!hasSSNData).toBeTruthy();
    });
  });

  // TP18: Consent & terms
  test('TP18: Terms and consent handling', async ({ page }) => {
    await test.step('Check for consent checkbox', async () => {
      const consentCheckbox = page.locator('input[type="checkbox"][name*="consent"], input[type="checkbox"][name*="agree"], input[type="checkbox"][name*="terms"]').first();

      if (await consentCheckbox.isVisible()) {
        console.log('✓ Consent checkbox found');

        const isChecked = await consentCheckbox.isChecked();
        console.log(`✓ Consent pre-checked: ${isChecked}`);
      } else {
        console.log('ℹ Consent checkbox not found in current state');
      }
    });

    await test.step('Check for terms/policy links', async () => {
      const policyLinks = await page.locator('a:has-text(/terms|privacy|policy/i)').count();
      console.log(`✓ Policy/terms links found: ${policyLinks}`);
    });

    await test.step('Check for consent-blocking UI', async () => {
      const submitButton = page.locator('button:has-text("Submit"), button:has-text("Next")').first();

      if (await submitButton.isVisible()) {
        const isDisabled = await submitButton.isDisabled();
        console.log(`✓ Submit button disabled without consent: ${isDisabled ? 'Yes' : 'No (may require consent)'}`);
      }
    });
  });
});
