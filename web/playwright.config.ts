import { defineConfig, devices } from "@playwright/test";

const CI = !!process.env.CI;

/**
 * End-to-end tests against the production build (vite preview), so CI exercises
 * exactly what GitHub Pages serves. See e2e/dashboard.spec.ts.
 */
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: true,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  workers: CI ? 2 : undefined,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: "http://localhost:4173/",
    viewport: { width: 1600, height: 1000 },
    screenshot: "only-on-failure",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1600, height: 1000 } } },
  ],
  webServer: {
    command: "npm run build && npx vite preview --port 4173 --strictPort",
    url: "http://localhost:4173/",
    reuseExistingServer: !CI,
    timeout: 180_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
