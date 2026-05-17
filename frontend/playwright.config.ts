import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for the rental-market GUI.
 *
 * Two projects:
 *   - desktop-chrome: 1440x900 Chromium
 *   - mobile-iphone-14: 390x844 iPhone 14 device emulation
 *
 * Tests live in `frontend/tests/e2e/` and visual snapshots are written
 * under `frontend/tests/e2e/__screenshots__/`. The dev server is
 * `npm run dev -- --port 5173`, base URL http://localhost:5173.
 *
 * All API traffic is mocked in fixtures.ts so the suite is hermetic
 * (no real FastAPI backend required). See README.md for how to update
 * snapshots post-integration.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  snapshotDir: "./tests/e2e/__screenshots__",
  // Identical screenshot path regardless of OS so CI matches local.
  snapshotPathTemplate:
    "{snapshotDir}/{testFilePath}/{arg}-{projectName}{ext}",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI
    ? [["github"], ["html", { open: "never" }]]
    : [["list"]],
  expect: {
    // Small pixel-diff tolerance to keep CI stable across font hinting.
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,
      animations: "disabled",
      caret: "hide",
    },
  },
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  projects: [
    {
      name: "desktop-chrome",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
      },
    },
    {
      name: "mobile-iphone-14",
      use: {
        // iPhone 14 viewport emulation. We use Chromium (not WebKit)
        // because the sandbox only has Chromium browsers installed.
        // Mobile-specific behavior (touch, viewport, isMobile) still
        // exercises the responsive layout paths in the UI.
        browserName: "chromium",
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 3,
        isMobile: true,
        hasTouch: true,
        userAgent:
          "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) " +
          "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
      },
    },
  ],
  webServer: {
    command: "npm run dev -- --port 5173",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
