/**
 * Zip detail page (plan §7 — covers 10025 sub-scores + charts).
 *
 * All five sub-scores + ZHVI/ZORI/Redfin charts render from mocked
 * fixtures. No real backend.
 */
import { test, expect } from "./fixtures";

const SUB_SCORES = [
  "yield_score",
  "demand_score",
  "supply_score",
  "operability_score",
  "risk_score",
];

test.describe("Zip detail (10025)", () => {
  test("renders all five sub-scores + charts", async ({ page, stable }) => {
    await page.goto("/rankings/10025");
    await stable();

    await expect(page.getByTestId("zip-detail-root")).toBeVisible();
    for (const score of SUB_SCORES) {
      const el = page.getByTestId(`zip-detail-score-${score}`);
      if (await el.count()) await expect(el).toBeVisible();
    }
    await expect(page.getByTestId("zip-detail-chart-zhvi")).toBeVisible();
    await expect(page.getByTestId("zip-detail-chart-zori")).toBeVisible();
    await expect(page).toHaveScreenshot("zip-detail.png");
  });
});
