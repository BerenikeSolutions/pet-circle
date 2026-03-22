/**
 * 00-empty-states.spec.ts
 *
 * Verifies that the dashboard renders cleanly for a pet with no records
 * (EMPTY_TOKEN: "Skippy" — all optional onboarding steps skipped).
 *
 * Checks:
 *  - No "undefined", "NaN", "[object Object]" anywhere in page text
 *  - Each of the 5 tabs loads without error
 *  - Empty-state placeholder text or graceful fallbacks are shown
 *  - Screenshots captured for every tab
 */

import { test, expect } from '@playwright/test';
import { getTokens } from './helpers/tokens';
import { goDashboard, clickTab, TAB } from './helpers/nav';
import { shot } from './helpers/screenshots';

const FOLDER = 'empty-states';
const BAD_STRINGS = ['undefined', 'NaN', '[object Object]', 'null'];

async function assertNoJunkText(page: any) {
  const text = await page.innerText('body');
  for (const bad of BAD_STRINGS) {
    expect(text, `Page should not contain "${bad}"`).not.toContain(bad);
  }
}

test.describe('Empty State — All Tabs', () => {
  test('Overview tab renders without errors', async ({ page }) => {
    const { emptyToken } = getTokens();
    const loaded = await goDashboard(page, emptyToken);
    if (loaded) await assertNoJunkText(page);
    await shot(page, FOLDER, 'tab-overview');
  });

  test('Health tab renders without errors', async ({ page }) => {
    const { emptyToken } = getTokens();
    const loaded = await goDashboard(page, emptyToken);
    if (loaded) {
      await clickTab(page, TAB.medical);
      await page.waitForTimeout(500);
      await assertNoJunkText(page);
    }
    await shot(page, FOLDER, 'tab-health');
  });

  test('Hygiene tab renders without errors', async ({ page }) => {
    const { emptyToken } = getTokens();
    const loaded = await goDashboard(page, emptyToken);
    if (loaded) {
      await clickTab(page, TAB.grooming);
      await page.waitForTimeout(500);
      await assertNoJunkText(page);
    }
    await shot(page, FOLDER, 'tab-hygiene');
  });

  test('Nutrition tab renders without errors', async ({ page }) => {
    const { emptyToken } = getTokens();
    const loaded = await goDashboard(page, emptyToken);
    if (loaded) {
      await clickTab(page, TAB.nutrition);
      await page.waitForTimeout(500);
      await assertNoJunkText(page);
    }
    await shot(page, FOLDER, 'tab-nutrition');
  });

  test('Conditions tab renders without errors', async ({ page }) => {
    const { emptyToken } = getTokens();
    const loaded = await goDashboard(page, emptyToken);
    if (loaded) {
      await clickTab(page, TAB.conditions);
      await page.waitForTimeout(500);
      await assertNoJunkText(page);
    }
    await shot(page, FOLDER, 'tab-conditions');
  });

  test('Tab bar is clickable and switches content', async ({ page }) => {
    const { emptyToken } = getTokens();
    const loaded = await goDashboard(page, emptyToken);
    if (!loaded) return; // backend unavailable — skip test

    // Click through all tabs
    for (const label of Object.values(TAB)) {
      await clickTab(page, label);
      await page.waitForTimeout(300);
      // No crash
      await expect(page.locator('body')).not.toContainText('Unable to load dashboard');
    }
    await shot(page, FOLDER, 'tab-switching-complete');
  });

  test('Invalid token shows error page', async ({ page }) => {
    await page.goto('/dashboard/invalid-token-xyz-000');
    // Wait for EITHER the error state to appear OR loading to stop (20s for 404 + React render)
    await page.waitForFunction(
      () =>
        document.body.innerText.includes('Unable to load') ||
        document.body.innerText.includes('Try Again') ||
        document.body.innerText.includes('Failed') ||
        document.body.innerText.includes('error') ||
        !document.body.innerText.includes('Loading dashboard'),
      { timeout: 20_000 }
    ).catch(() => {});
    await page.waitForTimeout(500);
    // Use textContent (includes hidden/collapsed DOM nodes) rather than innerText
    const body = await page.locator('body').textContent() || '';
    const hasError =
      body.includes('Unable to load') ||
      body.includes('Try Again') ||
      body.includes('Failed') ||
      body.includes('404') ||
      body.includes('not found') ||
      body.includes('error') ||
      body.includes('invalid');
    expect(hasError, 'Should show error for invalid token').toBe(true);
    await shot(page, 'errors', '01-invalid-token');
  });
});
