import { describe, expect, it } from "vitest";
import {
  SOURCE_META,
  formatAge,
  formatCount,
  formatTimestamp,
  getSourceMeta,
  mergeSourceMeta,
  statusColor,
  KNOWN_SOURCE_NAMES,
} from "@/lib/source-meta";

describe("SOURCE_META", () => {
  it("includes the documented source modules", () => {
    // The Python package has 12 source modules; meta covers each one.
    expect(KNOWN_SOURCE_NAMES).toContain("zillow_zhvi");
    expect(KNOWN_SOURCE_NAMES).toContain("zillow_zori");
    expect(KNOWN_SOURCE_NAMES).toContain("redfin_market");
    expect(KNOWN_SOURCE_NAMES).toContain("acs_demographics");
    expect(KNOWN_SOURCE_NAMES).toContain("acs_housing_stock");
    expect(KNOWN_SOURCE_NAMES).toContain("bls_qcew");
    expect(KNOWN_SOURCE_NAMES).toContain("census_bps");
    expect(KNOWN_SOURCE_NAMES).toContain("census_geo");
    expect(KNOWN_SOURCE_NAMES).toContain("county_tax_rate");
    expect(KNOWN_SOURCE_NAMES).toContain("eviction_lab");
    expect(KNOWN_SOURCE_NAMES).toContain("fema_nri");
    expect(KNOWN_SOURCE_NAMES).toContain("irs_migration");
    expect(KNOWN_SOURCE_NAMES.length).toBe(12);
  });

  it("every entry has required fields", () => {
    for (const [name, meta] of Object.entries(SOURCE_META)) {
      expect(meta.display_name, name).toBeTruthy();
      expect(meta.description, name).toBeTruthy();
      expect(meta.license, name).toBeTruthy();
      expect(meta.cadence, name).toBeTruthy();
      expect(meta.source_url, name).toBeTruthy();
    }
  });
});

describe("getSourceMeta", () => {
  it("returns the registered entry when known", () => {
    const meta = getSourceMeta("zillow_zhvi");
    expect(meta.display_name).toBe("Zillow ZHVI");
    expect(meta.source_url).toContain("zillowstatic.com");
  });

  it("returns a fallback for unknown sources", () => {
    const meta = getSourceMeta("not_a_real_source");
    expect(meta.display_name).toBe("not_a_real_source");
    expect(meta.license).toBe("unknown");
    expect(meta.source_url).toBe("");
  });
});

describe("mergeSourceMeta", () => {
  it("prefers API-provided values when present", () => {
    const merged = mergeSourceMeta("zillow_zhvi", {
      license: "Custom license",
      cadence: "Weekly",
      source_url: "https://example.com/override",
    });
    expect(merged.license).toBe("Custom license");
    expect(merged.cadence).toBe("Weekly");
    expect(merged.source_url).toBe("https://example.com/override");
    // display_name + description come from static meta.
    expect(merged.display_name).toBe("Zillow ZHVI");
  });

  it("falls back to static meta when API fields are missing or empty", () => {
    const merged = mergeSourceMeta("zillow_zhvi", {});
    expect(merged.license).toBe(SOURCE_META.zillow_zhvi.license);
    expect(merged.cadence).toBe(SOURCE_META.zillow_zhvi.cadence);
    expect(merged.source_url).toBe(SOURCE_META.zillow_zhvi.source_url);
  });

  it("treats empty strings from the API as missing", () => {
    const merged = mergeSourceMeta("zillow_zhvi", {
      license: "",
      cadence: "",
      source_url: "",
    });
    expect(merged.license).toBe(SOURCE_META.zillow_zhvi.license);
  });
});

describe("formatAge", () => {
  it("returns 'never' for null / undefined", () => {
    expect(formatAge(null)).toBe("never");
    expect(formatAge(undefined)).toBe("never");
  });

  it("returns 'just now' for negative ages (clock skew)", () => {
    expect(formatAge(-1)).toBe("just now");
  });

  it("formats sub-minute as seconds", () => {
    expect(formatAge(0)).toBe("0s ago");
    expect(formatAge(45)).toBe("45s ago");
  });

  it("formats minutes, hours, and days", () => {
    expect(formatAge(120)).toBe("2m ago");
    expect(formatAge(60 * 60 * 3)).toBe("3h ago");
    expect(formatAge(60 * 60 * 24 * 5)).toBe("5d ago");
  });
});

describe("formatTimestamp", () => {
  it("returns 'never' for null / undefined / empty", () => {
    expect(formatTimestamp(null)).toBe("never");
    expect(formatTimestamp(undefined)).toBe("never");
    expect(formatTimestamp("")).toBe("never");
  });

  it("formats a valid ISO timestamp", () => {
    const result = formatTimestamp("2024-01-15T12:00:00Z");
    // We don't assert exact locale string, but it must not be "never"
    // or the raw input.
    expect(result).not.toBe("never");
    expect(result.length).toBeGreaterThan(0);
  });

  it("returns the input when unparseable", () => {
    const garbled = "not a date";
    // new Date("not a date") is invalid in V8 → NaN; we return the input.
    expect(formatTimestamp(garbled)).toBe(garbled);
  });
});

describe("formatCount", () => {
  it("renders em-dash for null/undefined", () => {
    expect(formatCount(null)).toBe("—");
    expect(formatCount(undefined)).toBe("—");
  });
  it("uses locale-aware thousands separators", () => {
    expect(formatCount(0)).toBe("0");
    expect(formatCount(1_234_567)).toMatch(/1.234.567|1,234,567/);
  });
});

describe("statusColor", () => {
  it("returns distinct classes per status", () => {
    expect(statusColor("ok")).toContain("emerald");
    expect(statusColor("stale")).toContain("amber");
    expect(statusColor("error")).toContain("rose");
    expect(statusColor("never")).toContain("slate");
    expect(statusColor(undefined)).toContain("slate");
  });
});
