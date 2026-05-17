/**
 * Source detail page (plan §7 #2).
 *
 * Navigate to /sources/zillow_zhvi → schema table and sample rows render.
 */
import { test, expect } from "./fixtures";

test.describe("Source detail", () => {
  test("renders schema and sample rows for zillow_zhvi", async ({
    page,
    stable,
  }) => {
    await page.goto("/sources/zillow_zhvi");
    await stable();

    await expect(page.getByTestId("source-detail-root")).toBeVisible();
    await expect(page.getByTestId("source-detail-schema-table")).toBeVisible();
    await expect(page.getByTestId("source-detail-sample-table")).toBeVisible();
    await expect(page).toHaveScreenshot("source-detail.png");
  });
});
