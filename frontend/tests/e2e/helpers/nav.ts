/**
 * nav.ts — Navigation helpers for the dashboard.
 *
 * Tab IDs (from DashboardClient.tsx):
 *   overview | medical | grooming | nutrition | conditions
 *
 * Tab labels (from DASHBOARD_TABS in dashboard-utils.ts):
 *   Overview | Health | Hygiene | Nutrition | Conditions
 */

import { Page, expect } from '@playwright/test';

export const TAB = {
  overview:    'Overview',
  medical:     'Health',
  grooming:    'Hygiene',
  nutrition:   'Nutrition',
  conditions:  'Conditions',
} as const;

/**
 * Navigate to dashboard and wait for it to finish loading.
 * Returns true if the tab bar is visible (success), false if error/offline state.
 */
export async function goDashboard(page: Page, token: string): Promise<boolean> {
  await page.goto(`/dashboard/${token}`);
  // Wait for EITHER the tab bar (success) OR an error/offline state (not stuck at spinner)
  // 90s because backend may queue AI background tasks, slowing DB responses
  try {
    await expect(page.getByRole('button', { name: 'Overview', exact: true }))
      .toBeVisible({ timeout: 90_000 });
    return true;
  } catch {
    // Tab bar not found — check if there's an error or offline state
    const body = await page.locator('body').textContent() || '';
    if (body.includes('Unable to load') || body.includes('No network') || body.includes('Loading dashboard')) {
      return false;
    }
    throw new Error('Dashboard did not load within 90s');
  }
}

/** Click a top-level tab. */
export async function clickTab(page: Page, label: string) {
  await page.getByRole('button', { name: label, exact: true }).click();
  await page.waitForTimeout(400);
}

/** Dismiss loading spinner if it appears. */
export async function waitForLoad(page: Page) {
  // Wait until "Loading dashboard..." disappears
  await page.waitForFunction(
    () => !document.body.innerText.includes('Loading dashboard'),
    { timeout: 20_000 }
  );
}
