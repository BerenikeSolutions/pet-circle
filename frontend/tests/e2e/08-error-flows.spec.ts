/**
 * 08-error-flows.spec.ts
 *
 * Tests error and edge-case scenarios for the dashboard.
 *
 * Scenarios:
 *  1. Invalid token — shows error page
 *  2. Empty token path — 404/redirect
 *  3. Offline simulation — offline banner shown
 *  4. Online restore — auto-retry / reconnect shown
 *  5. Rapid tab switching — no crashes
 *  6. Stale data banner (simulated by intercepting API)
 *
 * Screenshots saved to tests/screenshots/errors/
 */

import { test, expect } from '@playwright/test';
import { getTokens } from './helpers/tokens';
import { goDashboard, clickTab, TAB } from './helpers/nav';
import { shot } from './helpers/screenshots';

const FOLDER = 'errors';

test.describe('Error Flows', () => {
  test('Invalid token shows error or 404', async ({ page }) => {
    await page.goto('/dashboard/invalid-token-xyz-000abc');
    await page.waitForTimeout(3000);

    const body = await page.innerText('body');
    const hasError =
      body.toLowerCase().includes('unable to load') ||
      body.toLowerCase().includes('404') ||
      body.toLowerCase().includes('not found') ||
      body.toLowerCase().includes('error') ||
      body.toLowerCase().includes('invalid') ||
      body.toLowerCase().includes('failed');

    expect(hasError, 'Invalid token should show an error state').toBe(true);
    await shot(page, FOLDER, '01-invalid-token');
  });

  test('Random garbage token shows error', async ({ page }) => {
    await page.goto('/dashboard/00000000000000000000000000000000');
    await page.waitForTimeout(3000);

    const body = await page.innerText('body');
    const hasError =
      body.toLowerCase().includes('unable to load') ||
      body.toLowerCase().includes('error') ||
      body.toLowerCase().includes('failed') ||
      body.toLowerCase().includes('not found');

    expect(hasError, 'Garbage token should show an error state').toBe(true);
    await shot(page, FOLDER, '02-garbage-token');
  });

  test('Offline simulation — shows offline banner', async ({ page }) => {
    const { fullToken } = getTokens();

    // Load dashboard first while online
    await goDashboard(page, fullToken);
    await page.waitForTimeout(1000);
    await shot(page, FOLDER, '03-online');

    // Go offline — DashboardClient listens to 'offline' browser event and hides tabs
    await page.context().setOffline(true);
    // Wait for the offline event to propagate to React state
    await page.waitForTimeout(2000);

    const body = await page.innerText('body');
    const hasOfflineBanner =
      body.includes('No network') ||
      body.includes('network connection') ||
      body.includes('offline') ||
      body.includes('Offline') ||
      body.includes('last saved data');

    await shot(page, FOLDER, '04-offline-banner');
    // Restore online before leaving
    await page.context().setOffline(false);
    expect(hasOfflineBanner, 'Offline state should show offline banner').toBe(true);
  });

  test('Back online — shows cached data or reconnects', async ({ page }) => {
    const { fullToken } = getTokens();

    // Load while online, then go offline, then come back online
    const loaded = await goDashboard(page, fullToken);
    if (!loaded) {
      // Backend unavailable — just check we see something reasonable
      await shot(page, FOLDER, '05-back-online');
      return;
    }
    await page.waitForTimeout(1000);

    // Go offline briefly
    await page.context().setOffline(true);
    await page.waitForTimeout(1000);

    // Come back online
    await page.context().setOffline(false);
    await page.waitForTimeout(3000);

    // Should show either normal dashboard or reconnect banner
    const body = await page.innerText('body');
    const online =
      body.includes('Overview') ||
      body.includes('Health') ||
      body.includes('Retry') ||
      body.includes('last saved data');
    await shot(page, FOLDER, '05-back-online');
    expect(online).toBe(true);
  });

  test('Rapid tab switching — no crashes', async ({ page }) => {
    const { fullToken } = getTokens();
    await goDashboard(page, fullToken);

    const tabs = Object.values(TAB);

    // Click through all tabs 3 times rapidly
    for (let round = 0; round < 3; round++) {
      for (const tab of tabs) {
        await clickTab(page, tab);
        await page.waitForTimeout(150);
      }
    }

    // No error boundary should have triggered
    const body = await page.innerText('body');
    expect(body).not.toContain('Something went wrong');
    expect(body).not.toContain('Application Error');
    await shot(page, FOLDER, '06-rapid-tab-switching-survived');
  });

  test('Stale data banner appears on API failure', async ({ page }) => {
    const { fullToken } = getTokens();

    // First load the dashboard normally (populate localStorage cache)
    await goDashboard(page, fullToken);
    await page.waitForTimeout(1000);

    // Intercept ONLY the backend API call (port 8000) to return 500
    // Using exact URL to avoid intercepting the Next.js page itself
    await page.route(`http://localhost:8000/dashboard/${fullToken}`, route => {
      route.fulfill({ status: 500, body: JSON.stringify({ detail: 'Server error' }) });
    });

    // Reload — should show stale data with amber banner from localStorage
    await page.reload();
    await page.waitForTimeout(4000);

    const body = await page.innerText('body');
    const hasStale =
      body.includes('last saved data') ||
      body.includes('Showing last') ||
      body.includes('stale') ||
      body.includes('Server appears offline') ||
      // OR shows error state
      body.includes('Unable to load') ||
      body.includes('Retry Now');

    await shot(page, FOLDER, '07-stale-data-banner');
    expect(hasStale, 'Should show stale banner or error on API failure').toBe(true);
  });

  test('Network timeout shows error gracefully', async ({ page }) => {
    const { fullToken } = getTokens();

    // Block ONLY the backend API (port 8000) — intercept with a 5s delay then 408
    await page.route(`http://localhost:8000/dashboard/${fullToken}`, route => {
      setTimeout(() => {
        route.fulfill({ status: 408, body: 'Timeout' }).catch(() => {});
      }, 5000);
    });

    await page.goto(`/dashboard/${fullToken}`);
    await page.waitForTimeout(8000); // wait for timeout to fire + app to react

    const body = await page.innerText('body');
    // After timeout, the app shows stale data (from localStorage) OR an error
    const hasGracefulError =
      body.includes('Unable to load') ||
      body.includes('last saved data') ||
      body.includes('Server appears offline') ||
      body.includes('Retry Now') ||
      body.includes('failed') ||
      body.includes('Failed') ||
      body.includes('error') ||
      body.includes('Error') ||
      body.includes('Try Again');

    await shot(page, FOLDER, '08-timeout-error');
    expect(hasGracefulError, 'Timeout should show a graceful error').toBe(true);
  });

  test('Empty dashboard route redirects or 404s', async ({ page }) => {
    // Try to navigate to the base /dashboard path without a token
    await page.goto('/dashboard');
    await page.waitForTimeout(2000);

    // Should either 404, redirect, or show an error
    const url = page.url();
    const body = await page.innerText('body').catch(() => '');
    const handledGracefully =
      url !== 'http://localhost:3000/dashboard' || // redirected
      body.includes('404') ||
      body.includes('not found') ||
      body.includes('error') ||
      body.length < 200; // minimal content = 404 page

    await shot(page, FOLDER, '09-empty-dashboard-route');
    expect(handledGracefully).toBe(true);
  });
});
