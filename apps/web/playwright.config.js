import { existsSync } from 'node:fs';
import { defineConfig, devices } from '@playwright/test';

// Some sandboxes pre-install a pinned Chromium revision outside Playwright's
// own managed cache (see repo-level environment notes). When present, use it
// directly instead of the revision `@playwright/test` expects — avoids a
// version-skew "Executable doesn't exist" failure without needing a browser
// download (often unavailable in those sandboxes). CI and normal local dev
// don't have this path, so they fall through to Playwright's own resolution.
const SANDBOX_CHROMIUM = '/opt/pw-browsers/chromium';
const launchOptions = existsSync(SANDBOX_CHROMIUM) ? { executablePath: SANDBOX_CHROMIUM } : {};

export default defineConfig({
  testDir: './tests',
  fullyParallel: false, // Run sequentially for simplicity
  workers: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    launchOptions,
  },
  webServer: {
    command: 'pnpm dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
