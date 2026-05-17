/**
 * Manifest page.
 *
 * Lists all sources from the manifest. Status filter + age sort exist.
 */
import { test, expect } from "./fixtures";

test.describe("Manifest", () => {
  test("renders the manifest table", async ({ page, stable }) => {
    await page.goto("/manifest");
    await stable();

    await expect(page.getByTestId("manifest-root")).toBeVisible();
    await expect(page.getByTestId("manifest-table")).toBeVisible();
    await expect(page).toHaveScreenshot("manifest.png");
  });
});
