import { defineConfig, devices } from "@playwright/test";

// End-to-end journeys against the real demo stack (docker-compose.demo.yml), served by Caddy on
// http://localhost:8080. The stack must be built (`make demo-build`); globalSetup recreates and
// seeds it once per run with `make demo-reset` (skip with E2E_SKIP_RESET=1 on a fresh seed).
//
// One worker, in file order: the specs share one database and one officer's alert bell, so they
// run one at a time. Each spec uses its own seeded or newly created transactions, so the specs
// do not depend on each other's side effects or order.
const CI = Boolean(process.env.CI);

export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  globalSetup: "./global-setup.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  outputDir: "../test-results",
  reporter: [["list"], ["html", { outputFolder: "../playwright-report", open: "never" }]],
  use: {
    baseURL: "http://localhost:8080",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    locale: "en-IN",
    timezoneId: "Asia/Kolkata",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
