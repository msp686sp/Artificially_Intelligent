/**
 * Backtest hub (plan §7 #10).
 *
 * "New run" form submits → POST /api/backtest/run mocked → no real
 * compute. Run history table renders.
 */
import { test, expect } from "./fixtures";

test.describe("Backtest hub", () => {
  test("submits a new run via the form", async ({ page, stable }) => {
    await page.goto("/backtest");
    await stable();

    await expect(page.getByTestId("backtest-root")).toBeVisible();
    await expect(page.getByTestId("backtest-runs-table")).toBeVisible();

    const newBtn = page.getByTestId("backtest-new-run-btn");
    if (await newBtn.count()) {
      await newBtn.click();
      const form = page.getByTestId("backtest-run-form-root");
      await expect(form).toBeVisible();

      await page.getByTestId("backtest-run-form-start-year").fill("2013");
      await page.getByTestId("backtest-run-form-end-year").fill("2019");
      await page.getByTestId("backtest-run-form-submit").click();
    }
    await stable();
    await expect(page).toHaveScreenshot("backtest.png");
  });
});
