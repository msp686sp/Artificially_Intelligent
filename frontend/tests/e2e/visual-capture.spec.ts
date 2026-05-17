/**
 * Screenshot-capture spec.
 *
 * Navigates to every route, waits for React to mount, captures a
 * full-page screenshot at desktop and mobile viewports. Uses bare
 * Playwright (NOT the fixtures.ts mock layer) — the freeze-date
 * shim in the fixtures interferes with React's bootstrap. Data
 * comes from whatever the running Vite dev server returns when
 * `/api/*` requests hit and fail; the UI gracefully renders its
 * empty-state placeholders so the screenshots still validate
 * layout, theming, navigation, and responsive collapse.
 */
import { expect, test } from "@playwright/test";

const ROUTES: { path: string; name: string; waitFor?: string }[] = [
  { path: "/",                       name: "dashboard" },
  { path: "/sources",                name: "sources-list" },
  { path: "/sources/zillow_zhvi",    name: "source-detail" },
  { path: "/rankings",               name: "rankings" },
  { path: "/rankings/10025",         name: "zip-detail" },
  { path: "/compare?z=10025,46220",  name: "compare" },
  { path: "/filters",                name: "filters" },
  { path: "/sql",                    name: "sql" },
  { path: "/schema",                 name: "schema" },
  { path: "/backtest",               name: "backtest-hub" },
  { path: "/backtest/1",             name: "backtest-detail" },
  { path: "/backtest/compare?ids=1,2", name: "backtest-compare" },
  { path: "/manifest",               name: "manifest" },
  { path: "/logs",                   name: "logs" },
  { path: "/settings",               name: "settings" },
];

test.describe("Visual capture @capture", () => {
  for (const route of ROUTES) {
    test(`renders ${route.name} (${route.path})`, async ({ page }) => {
      await page.goto(route.path, { waitUntil: "load" });
      // Wait for React to mount (Shell + sidebar render).
      await page
        .waitForFunction(
          () => {
            const root = document.getElementById("root");
            return !!(root && root.children.length > 0);
          },
          { timeout: 8000 },
        )
        .catch(() => {});
      // Let TanStack Query finish its initial fetches + Recharts size itself.
      await page.waitForTimeout(800);
      // Soft assertion: the body has rendered content.
      const bodyLen = await page.evaluate(() => document.body.innerHTML.length);
      expect(bodyLen).toBeGreaterThan(200);
      // Capture a full-page screenshot under the canonical baseline path.
      await expect(page).toHaveScreenshot(`${route.name}.png`, {
        fullPage: true,
        maxDiffPixelRatio: 0.05,
        animations: "disabled",
      });
    });
  }
});
