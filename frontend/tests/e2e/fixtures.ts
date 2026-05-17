/**
 * Playwright fixtures shared by every spec.
 *
 * Responsibilities:
 *   1. Mock `/api/**` so the suite is hermetic (no real backend).
 *   2. Inject CSS to disable animations / transitions / caret blink,
 *      so visual snapshots are stable.
 *   3. Freeze `Date.now` / `new Date()` so any time-relative UI
 *      ("3 hours ago") renders identically across runs.
 *   4. Wait on `document.fonts.ready` before any screenshot.
 *
 * Each fixture JSON lives under `__fixtures__/` and corresponds to one
 * API endpoint defined in `docs/gooey-plan.md` §5. New endpoints get a
 * new JSON file + a `route()` entry below.
 */

import { test as base, expect, Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// 2026-05-17T12:00:00Z — frozen "now" for deterministic relative dates.
const FROZEN_NOW = Date.UTC(2026, 4, 17, 12, 0, 0);

const FIXTURE_DIR = path.join(__dirname, "__fixtures__");

function _loadFixture(name: string): unknown {
  const file = path.join(FIXTURE_DIR, name);
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

/**
 * Routing table: URL pattern -> fixture file. The first match wins.
 * Patterns are matched against the request URL pathname + query.
 */
type RouteRule = {
  match: (url: URL) => boolean;
  fixture: string;
  status?: number;
};

const ROUTES: RouteRule[] = [
  // Health + meta
  { match: (u) => u.pathname === "/api/health", fixture: "health.json" },
  { match: (u) => u.pathname === "/api/version", fixture: "version.json" },

  // Sources
  { match: (u) => u.pathname === "/api/sources", fixture: "sources.json" },
  {
    match: (u) => /^\/api\/sources\/[^/]+\/preview$/.test(u.pathname),
    fixture: "source-preview.json",
  },
  {
    match: (u) => /^\/api\/sources\/[^/]+\/schema$/.test(u.pathname),
    fixture: "source-schema.json",
  },
  {
    match: (u) => /^\/api\/sources\/[^/]+\/refresh$/.test(u.pathname),
    fixture: "source-refresh.json",
  },
  {
    match: (u) => /^\/api\/sources\/[^/]+$/.test(u.pathname),
    fixture: "source-detail.json",
  },

  // SQL + schema
  { match: (u) => u.pathname === "/api/sql", fixture: "sql-result.json" },
  { match: (u) => u.pathname === "/api/schema", fixture: "schema.json" },

  // Rankings + zips
  { match: (u) => u.pathname === "/api/rankings", fixture: "rankings.json" },
  {
    match: (u) => u.pathname === "/api/zips/compare",
    fixture: "zips-compare.json",
  },
  {
    match: (u) => /^\/api\/zips\/\d{5}$/.test(u.pathname),
    fixture: "zip-10025.json",
  },

  // Charts
  {
    match: (u) => /^\/api\/charts\/zhvi\/\d{5}$/.test(u.pathname),
    fixture: "charts-zhvi-10025.json",
  },
  {
    match: (u) => /^\/api\/charts\/zori\/\d{5}$/.test(u.pathname),
    fixture: "charts-zori-10025.json",
  },
  {
    match: (u) => /^\/api\/charts\/redfin\/\d{5}$/.test(u.pathname),
    fixture: "charts-redfin-10025.json",
  },
  {
    match: (u) => u.pathname === "/api/charts/score-distribution",
    fixture: "charts-score-distribution.json",
  },

  // Manifest + config
  { match: (u) => u.pathname === "/api/manifest", fixture: "manifest.json" },
  {
    match: (u) => /^\/api\/manifest\/[^/]+$/.test(u.pathname),
    fixture: "manifest-entry.json",
  },
  {
    match: (u) => u.pathname === "/api/config/files",
    fixture: "config-files.json",
  },
  {
    match: (u) => /^\/api\/config\/[^/]+$/.test(u.pathname),
    fixture: "config-filters.json",
  },

  // Backtest
  {
    match: (u) => u.pathname === "/api/backtest/runs",
    fixture: "backtest-runs.json",
  },
  {
    match: (u) =>
      u.pathname === "/api/backtest/run" || u.pathname === "/api/backtest/tune",
    fixture: "backtest-run-submit.json",
  },
  {
    match: (u) => /^\/api\/backtest\/runs\/[^/]+\/report\.html$/.test(u.pathname),
    fixture: "backtest-report.html",
  },
  {
    match: (u) => /^\/api\/backtest\/runs\/[^/]+$/.test(u.pathname),
    fixture: "backtest-run-1.json",
  },

  // Refresh log
  { match: (u) => u.pathname === "/api/logs/refresh", fixture: "refresh-log.json" },
];

/**
 * Inject a stylesheet that:
 *   - kills CSS animations, transitions, and the caret blink
 *   - hides the scrollbar (which differs across OSes)
 *   - forces the same font smoothing so AA differences shrink
 */
const STABILITY_CSS = `
  *, *::before, *::after {
    animation-duration: 0s !important;
    animation-delay: 0s !important;
    transition-duration: 0s !important;
    transition-delay: 0s !important;
    caret-color: transparent !important;
  }
  html { scrollbar-width: none; }
  html::-webkit-scrollbar { display: none; }
  body { -webkit-font-smoothing: antialiased; }
`;

/**
 * Inject a Date freeze so any relative timestamps render identically.
 * Runs before any page script via addInitScript.
 */
const FREEZE_DATE_SCRIPT = (frozen: number) => `
  (() => {
    const _Date = Date;
    const frozen = ${frozen};
    function FrozenDate(...args) {
      if (args.length === 0) return new _Date(frozen);
      return new _Date(...args);
    }
    FrozenDate.now = () => frozen;
    FrozenDate.UTC = _Date.UTC;
    FrozenDate.parse = _Date.parse;
    FrozenDate.prototype = _Date.prototype;
    // eslint-disable-next-line no-global-assign
    Date = FrozenDate;
  })();
`;

async function installApiMocks(page: Page, overrides: Map<string, unknown>) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());

    // Per-test overrides take precedence over the global routing table.
    for (const [pattern, body] of overrides.entries()) {
      if (url.pathname === pattern || url.pathname.startsWith(pattern)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: typeof body === "string" ? body : JSON.stringify(body),
        });
        return;
      }
    }

    const rule = ROUTES.find((r) => r.match(url));
    if (!rule) {
      // Unmocked endpoint — fail loud so the test author adds a fixture.
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ error: `unmocked api call: ${url.pathname}` }),
      });
      return;
    }

    const file = path.join(FIXTURE_DIR, rule.fixture);
    if (!fs.existsSync(file)) {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ error: `missing fixture: ${rule.fixture}` }),
      });
      return;
    }

    const body = fs.readFileSync(file, "utf8");
    const contentType = rule.fixture.endsWith(".html")
      ? "text/html"
      : "application/json";
    await route.fulfill({
      status: rule.status ?? 200,
      contentType,
      body,
    });
  });
}

type Fixtures = {
  /**
   * Map of pathname -> body. Set BEFORE navigating to override the
   * global mock for the current test (e.g. health = empty warehouse).
   */
  apiOverrides: Map<string, unknown>;
  /** Wait for fonts + a microtask flush so the page is paint-stable. */
  stable: () => Promise<void>;
};

export const test = base.extend<Fixtures>({
  // eslint-disable-next-line no-empty-pattern
  apiOverrides: async ({}, use) => {
    const overrides = new Map<string, unknown>();
    await use(overrides);
  },

  page: async ({ page, apiOverrides }, use) => {
    await page.addInitScript({ content: FREEZE_DATE_SCRIPT(FROZEN_NOW) });
    await page.addStyleTag({ content: STABILITY_CSS }).catch(() => {
      // addStyleTag fires before navigation — swallow until a doc exists.
    });
    // Re-add the stylesheet on each navigation so it survives SPA reloads.
    page.on("load", async () => {
      await page.addStyleTag({ content: STABILITY_CSS }).catch(() => {});
    });
    await installApiMocks(page, apiOverrides);
    await use(page);
  },

  stable: async ({ page }, use) => {
    const fn = async () => {
      await page.evaluate(() => document.fonts && document.fonts.ready);
      // Give React a tick to flush after the fonts settle.
      await page.evaluate(
        () => new Promise((r) => requestAnimationFrame(() => r(null))),
      );
    };
    await use(fn);
  },
});

export { expect };
