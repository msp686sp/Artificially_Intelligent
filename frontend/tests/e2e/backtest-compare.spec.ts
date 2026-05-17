/**
 * Backtest compare (plan §7 #11).
 *
 * /backtest/compare?ids=run-1,run-2 renders the weight-diff and
 * spearman-by-snapshot panels.
 */
import { test, expect } from "./fixtures";

test.describe("Backtest compare", () => {
  test("renders weight diff + spearman delta for two runs", async ({
    page,
    stable,
  }) => {
    await page.goto("/backtest/compare?ids=run-1,run-2");
    await stable();

    await expect(page.getByTestId("backtest-compare-root")).toBeVisible();
    await expect(page.getByTestId("backtest-compare-weight-diff"))
      .toBeVisible();
    await expect(page.getByTestId("backtest-compare-spearman")).toBeVisible();
    await expect(page).toHaveScreenshot("backtest-compare.png");
  });
});
