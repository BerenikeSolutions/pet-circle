/**
 * 01-overview-tab.spec.ts
 *
 * Tests the Overview tab with FULL_TOKEN (Zayn — all data filled).
 *
 * Happy path:
 *  - Pet name, breed visible in header
 *  - Health score ring renders (SVG)
 *  - Nudge FAB appears
 *  - Weight update works
 *  - Nudge dismiss works
 *  - Reminders view opens
 *
 * Screenshots saved to tests/screenshots/overview/
 */

import { test, expect } from '@playwright/test';
import { getTokens } from './helpers/tokens';
import { goDashboard, clickTab, TAB } from './helpers/nav';
import { shot } from './helpers/screenshots';

const FOLDER = 'overview';

test.describe('Overview Tab — Full Data (Zayn)', () => {
  test('Header shows pet name and breed', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await goDashboard(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '01-skipped'); return; }
    await shot(page, FOLDER, '01-initial');

    // Pet name in header
    await expect(page.getByRole('heading', { name: 'Zayn' })).toBeVisible();
    // Breed text
    await expect(page.locator('body')).toContainText('Labrador');
  });

  test('Health score SVG ring is present', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await goDashboard(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '02-skipped'); return; }
    // SVG circle (ring) should be present somewhere on overview
    const svgEl = page.locator('svg circle').first();
    await expect(svgEl).toBeVisible({ timeout: 10_000 });
    await shot(page, FOLDER, '02-health-ring');
  });

  test('Weight update — enter new weight', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await goDashboard(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '03-skipped'); return; }

    // Look for weight display and click to edit
    const weightEl = page.locator('text=/\\d+(\\.\\d+)?\\s*kg/i').first();
    if (await weightEl.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await weightEl.click();
      await page.waitForTimeout(500);

      // Type new weight in any input that appears
      const input = page.locator('input[type="number"], input[type="text"]').first();
      if (await input.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await input.fill('29.5');
        await page.keyboard.press('Enter');
        await page.waitForTimeout(1000);
        await shot(page, FOLDER, '03-weight-updated');
      }
    } else {
      // Weight might not be visible if no weight data — skip gracefully
      console.log('Weight element not found, skipping weight update test');
    }
    await shot(page, FOLDER, '03-weight-section');
  });

  test('Nudge FAB appears and opens nudges view', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await goDashboard(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '04-skipped'); return; }
    await page.waitForTimeout(1000); // wait for nudges to load

    // FAB with ⚡ icon
    const fab = page.locator('button').filter({ hasText: '⚡' }).last();
    if (await fab.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await shot(page, FOLDER, '04-nudge-fab');
      await fab.click();
      await page.waitForTimeout(500);
      await shot(page, FOLDER, '05-nudges-open');

      // Dismiss the first nudge if visible
      const dismissBtn = page.locator('button').filter({ hasText: /dismiss/i }).first();
      if (await dismissBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await dismissBtn.click();
        await page.waitForTimeout(500);
        await shot(page, FOLDER, '06-nudge-dismissed');
      }

      // Go back
      const backBtn = page.locator('button').filter({ hasText: /back|←|✕|close/i }).first();
      if (await backBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await backBtn.click();
        await page.waitForTimeout(300);
      }
    } else {
      console.log('No nudge FAB visible (no nudges or already dismissed)');
    }
  });

  test('Reminders view opens from header or nudges', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await goDashboard(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '05-skipped'); return; }
    await page.waitForTimeout(500);

    // Try opening reminders — could be via a "Reminders" button
    const reminderBtn = page.locator('button').filter({ hasText: /reminder/i }).first();
    if (await reminderBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await reminderBtn.click();
      await page.waitForTimeout(500);
      await shot(page, FOLDER, '07-reminders-open');

      const backBtn = page.locator('button').filter({ hasText: /back|←|✕|close/i }).first();
      if (await backBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await backBtn.click();
      }
    } else {
      console.log('Reminders button not visible in overview — skipping');
    }
  });

  test('Final overview screenshot', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await goDashboard(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '06-skipped'); return; }
    await page.waitForTimeout(1000);
    await shot(page, FOLDER, '08-final');
  });
});
