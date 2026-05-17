/**
 * SQL workbench (plan §7 #8).
 *
 * Type a query into the CodeMirror editor, click Run, see results.
 */
import { test, expect } from "./fixtures";

const QUERY =
  "SELECT zcta5, market_score FROM zip_scores ORDER BY market_score DESC LIMIT 20";

test.describe("SQL workbench", () => {
  test("runs a query and shows results", async ({ page, stable }) => {
    await page.goto("/sql");
    await stable();

    await expect(page.getByTestId("sql-root")).toBeVisible();
    const editor = page.getByTestId("sql-editor");
    await expect(editor).toBeVisible();

    // CodeMirror is contenteditable; click and type. If the editor exposes
    // a textarea fallback, fill() works too.
    await editor.click();
    await page.keyboard.type(QUERY);

    await page.getByTestId("sql-run-btn").click();
    await expect(page.getByTestId("sql-results-table")).toBeVisible();
    await stable();
    await expect(page).toHaveScreenshot("sql.png");
  });
});
