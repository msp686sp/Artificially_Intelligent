/**
 * Compare two zips (plan §7 #6).
 *
 * /compare?z=10025,46220 renders numeric grid + overlay charts.
 */
import { test, expect } from "./fixtures";

test.describe("Compare", () => {
  test("renders numeric grid + overlay charts for two zips", async ({
    page,
    stable,
  }) => {
    await page.goto("/compare?z=10025,46220");
    await stable();

    await expect(page.getByTestId("compare-root")).toBeVisible();
    await expect(page.getByTestId("compare-grid")).toBeVisible();
    await expect(page.getByTestId("compare-chart-zhvi")).toBeVisible();
    await expect(page.getByTestId("compare-chart-zori")).toBeVisible();
    await expect(page).toHaveScreenshot("compare.png");
  });
});
