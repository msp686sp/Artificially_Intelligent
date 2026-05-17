/**
 * Schema browser (plan §7 #9).
 *
 * Click raw_zillow_zhvi in the tree → preview pane opens with sample
 * rows.
 */
import { test, expect } from "./fixtures";

test.describe("Schema browser", () => {
  test("opens preview for raw_zillow_zhvi", async ({ page, stable }) => {
    await page.goto("/schema");
    await stable();

    await expect(page.getByTestId("schema-root")).toBeVisible();
    await expect(page.getByTestId("schema-tree")).toBeVisible();

    const node = page.getByTestId("schema-tree-item-raw_zillow_zhvi");
    if (await node.count()) {
      await node.click();
      await expect(page.getByTestId("schema-preview")).toBeVisible();
    }
    await stable();
    await expect(page).toHaveScreenshot("schema.png");
  });
});
