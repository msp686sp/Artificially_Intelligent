/**
 * Settings page.
 */
import { test, expect } from "./fixtures";

test.describe("Settings", () => {
  test("renders env + theme + version", async ({ page, stable }) => {
    await page.goto("/settings");
    await stable();

    await expect(page.getByTestId("settings-root")).toBeVisible();
    await expect(page.getByTestId("settings-theme")).toBeVisible();
    await expect(page.getByTestId("settings-version")).toBeVisible();
    await expect(page).toHaveScreenshot("settings.png");
  });
});
