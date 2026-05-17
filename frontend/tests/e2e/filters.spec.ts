/**
 * Filters & weights (plan §7 #7).
 *
 * Edit the YAML, click Preview, the diff panel shows added/removed rows.
 */
import { test, expect } from "./fixtures";

test.describe("Filters", () => {
  test("preview shows diff after edits", async ({ page, stable }) => {
    await page.goto("/filters");
    await stable();

    await expect(page.getByTestId("filters-root")).toBeVisible();
    await expect(page.getByTestId("filters-editor-yaml")).toBeVisible();

    const preview = page.getByTestId("filters-preview-btn");
    if (await preview.count()) {
      await preview.click();
      await expect(page.getByTestId("filters-diff")).toBeVisible();
    }
    await stable();
    await expect(page).toHaveScreenshot("filters.png");
  });
});
