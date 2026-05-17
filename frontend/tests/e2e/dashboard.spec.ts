/**
 * Dashboard workflow (plan §7 #1).
 *
 * Two paths:
 *   1. Cold-start: /api/health says warehouse not initialized →
 *      empty-state copy + "Run make init" CTA.
 *   2. Happy path: stats render, top-5 table populated, screenshot.
 */
import { test, expect } from "./fixtures";

test.describe("Dashboard", () => {
  test("shows empty state when warehouse is not initialized", async ({
    page,
    apiOverrides,
    stable,
  }) => {
    apiOverrides.set("/api/health", {
      status: "ok",
      version: "0.1.0",
      uptime_s: 12,
      warehouse: { initialized: false, path: null, tables: 0, zips: 0 },
      sources_ok: 0,
      sources_stale: 0,
      sources_error: 0,
    });

    await page.goto("/");
    await stable();

    await expect(page.getByTestId("dashboard-empty-state")).toBeVisible();
    await expect(page.getByTestId("dashboard-empty-cta-init")).toBeVisible();
    await expect(page).toHaveScreenshot("dashboard-empty.png");
  });

  test("renders top-line stats and top-5 zips", async ({ page, stable }) => {
    await page.goto("/");
    await stable();

    await expect(page.getByTestId("dashboard-stat-sources-ok")).toBeVisible();
    await expect(page.getByTestId("dashboard-stat-sources-stale")).toBeVisible();
    await expect(page.getByTestId("dashboard-stat-sources-error")).toBeVisible();
    await expect(page.getByTestId("dashboard-top5-table")).toBeVisible();
    await expect(page).toHaveScreenshot("dashboard.png");
  });
});
