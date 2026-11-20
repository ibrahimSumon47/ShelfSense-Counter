import { defineConfig, devices } from '@playwright/test';

// The checked URL is the deployed site by default so these are production checks, not a
// local harness: point SHELFSENSE_URL at a preview or a dev server to run them elsewhere.
const baseURL = process.env.SHELFSENSE_URL ?? 'https://shelfsense-counter.vercel.app';

export default defineConfig({
  testDir: './e2e',
  // The first upload downloads the 32.8 MB model and then runs inference on WASM.
  timeout: 180_000,
  expect: { timeout: 120_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
