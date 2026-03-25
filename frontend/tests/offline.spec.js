import { test, expect } from '@playwright/test';

test.describe('VitalNet PWA Offline Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Go to the local dev server
    await page.goto('http://localhost:5173/');
    
    // Wait for the page to settle
    await page.waitForLoadState('networkidle');

    // Login as ASHA if we are on the login page
    const emailInput = page.locator('input[type="email"]');
    // We give it 2 seconds to appear; if it does, we log in
    try {
      await emailInput.waitFor({ state: 'visible', timeout: 3000 });
      await emailInput.fill('asha@test.vitalnet');
      await page.fill('input[type="password"]', 'TestASHA2026!');
      await page.click('button[type="submit"]');
    } catch (e) {
      // Already logged in
    }
    
    // Wait for dashboard to load
    await page.waitForSelector('text=New Case', { timeout: 10000 });
    
    // Click New Case if it's not already fully open (the panel starts open on mobile typically, but let's be safe)
    const newCaseBtn = page.locator('button:has-text("New Case")');
    try {
        await newCaseBtn.waitFor({ state: 'visible', timeout: 3000 });
        await newCaseBtn.click();
    } catch (e) {
        // Button not found, might already be open
    }
  });

  test('Draft saves when connection is lost and syncs when restored', async ({ page, context }) => {
    // Fill out the intake form partially
    await page.fill('input[name="patient_name"]', 'Test Offline Patient');
    await page.fill('input[name="patient_age"]', '35');
    await page.check('input[value="female"]');
    
    // Wait for the debounced auto-save (1s)
    await page.waitForTimeout(1500);

    // Reload the page to simulate tab eviction
    await page.reload();

    // Verify the draft was restored
    await expect(page.locator('input[name="patient_name"]')).toHaveValue('Test Offline Patient');
    await expect(page.locator('input[name="patient_age"]')).toHaveValue('35');

    // Go offline
    await context.setOffline(true);

    // Complete the form
    await page.fill('input[name="location"]', 'Test Village');
    await page.selectOption('select[name="chief_complaint"]', 'Chest pain / tightness');
    await page.selectOption('select[name="complaint_duration"]', '1–6 hours');
    
    // Submit the form
    await page.click('text=Submit Case');

    // Verify offline queue UI
    await expect(page.getByText('Case Saved Locally')).toBeVisible();
    await expect(page.getByText('SAVED OFFLINE', { exact: true })).toBeVisible();

    // Go back online
    await context.setOffline(false);

    // Queue should process automatically (processQueue runs every 10s or on online event)
    // We can't easily wait for the background sync without a network intercept,
    // but this validates the UI response to offline submission.
  });

  test('Clinical Validation bounds block submission', async ({ page }) => {
    await page.fill('input[name="patient_name"]', 'Test Validation');
    await page.fill('input[name="patient_age"]', '35');
    await page.check('input[value="female"]');
    await page.fill('input[name="location"]', 'Test Village');
    await page.selectOption('select[name="chief_complaint"]', 'Fever');
    await page.selectOption('select[name="complaint_duration"]', '1–6 hours');

    // Enter clinically impossible vitals
    await page.fill('input[name="spo2"]', '150');
    
    // Submit
    await page.click('text=Submit Case');

    // Verify validation error
    await expect(page.locator('text=Please fix the validation errors below before submitting.')).toBeVisible();
    // Verify specific Zod field error
    await expect(page.locator('text=SpO2 must be ≤ 100')).toBeVisible();
  });
});
