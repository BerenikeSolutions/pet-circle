import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  globalSetup: './tests/e2e/global-setup.ts',
  outputDir: './tests/test-results',
  fullyParallel: false,        // run sequentially — tests share state from onboarding
  retries: 0,
  timeout: 60_000,             // 60s per test (AI endpoints can be slow)
  workers: 1,

  use: {
    baseURL: 'http://localhost:3000',
    viewport: { width: 430, height: 932 },   // mobile-first (matches zayn_dashboard.jsx)
    screenshot: 'on',                         // always capture screenshots
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
    headless: true,
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
  },

  reporter: [
    ['html', { outputFolder: 'tests/playwright-report', open: 'never' }],
    ['list'],
  ],

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
