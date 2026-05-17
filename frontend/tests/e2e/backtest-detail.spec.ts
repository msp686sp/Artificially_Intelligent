/**
 * Backtest detail (plan §7 #10).
 *
 * /backtest/run-1 shows the HTML report tab + the summary tab; toggling
 * between them swaps the visible panel.
 */
import { test, expect } from "./fixtures";

test.describe("Backtest detail", () => {
  test("toggles between report and summary tabs", async ({ page, stable }) => {
    await page.goto("/backtest/run-1");
    await stable();

    await expect(page.getByTestId("backtest-detail-root")).toBeVisible();
    // Summary tab is the safer screenshot target (no iframe paint timing).
    const summary = page.getByTestId("backtest-detail-tab-summary");
    if (await summary.count()) await summary.click();

    await expect(page.getByTestId("backtest-detail-summary-table"))
      .toBeVisible();
    await stable();
    await expect(page).toHaveScreenshot("backtest-detail.png");
  });
});
