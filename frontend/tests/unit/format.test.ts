import { describe, expect, it } from "vitest";
import {
  EMPTY_VALUE,
  formatCurrency,
  formatDate,
  formatDuration,
  formatNumber,
  formatPercent,
  formatRelativeTime,
  isNullish,
} from "@/lib/format";

describe("isNullish", () => {
  it("recognises null and undefined", () => {
    expect(isNullish(null)).toBe(true);
    expect(isNullish(undefined)).toBe(true);
    expect(isNullish(0)).toBe(false);
    expect(isNullish("")).toBe(false);
  });
});

describe("formatNumber", () => {
  it("formats integers with thousands separators", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
  });
  it("respects decimals option", () => {
    expect(formatNumber(3.14159, { decimals: 2 })).toBe("3.14");
  });
  it("compact mode renders 1.2K-style", () => {
    expect(formatNumber(12500, { compact: true })).toMatch(/12\.5K/i);
  });
  it("returns em-dash for nullish/NaN", () => {
    expect(formatNumber(null)).toBe(EMPTY_VALUE);
    expect(formatNumber(undefined)).toBe(EMPTY_VALUE);
    expect(formatNumber(Number.NaN)).toBe(EMPTY_VALUE);
  });
});

describe("formatCurrency", () => {
  it("formats USD", () => {
    expect(formatCurrency(1500)).toBe("$1,500");
  });
  it("supports decimals", () => {
    expect(formatCurrency(1500.5, { decimals: 2 })).toBe("$1,500.50");
  });
  it("returns em-dash for nullish", () => {
    expect(formatCurrency(null)).toBe(EMPTY_VALUE);
  });
});

describe("formatPercent", () => {
  it("treats input as percent by default", () => {
    expect(formatPercent(5.2)).toBe("5.2%");
  });
  it("supports ratio mode", () => {
    expect(formatPercent(0.052, { asRatio: true })).toBe("5.2%");
  });
  it("respects decimals", () => {
    expect(formatPercent(3.14159, { decimals: 3 })).toBe("3.142%");
  });
  it("returns em-dash for nullish", () => {
    expect(formatPercent(undefined)).toBe(EMPTY_VALUE);
  });
});

describe("formatDate", () => {
  it("formats ISO date", () => {
    const out = formatDate("2024-01-15T00:00:00Z");
    expect(out).toMatch(/Jan|January/);
  });
  it("supports iso style", () => {
    expect(formatDate("2024-01-15T00:00:00Z", { style: "iso" })).toBe("2024-01-15");
  });
  it("returns em-dash for nullish/invalid", () => {
    expect(formatDate(null)).toBe(EMPTY_VALUE);
    expect(formatDate("not a date")).toBe(EMPTY_VALUE);
  });
});

describe("formatRelativeTime", () => {
  it("formats past times", () => {
    const past = new Date("2024-01-01T00:00:00Z");
    const now = new Date("2024-01-01T01:00:00Z");
    expect(formatRelativeTime(past, now)).toMatch(/hour/);
  });
  it("returns em-dash for nullish", () => {
    expect(formatRelativeTime(null)).toBe(EMPTY_VALUE);
  });
});

describe("formatDuration", () => {
  it("seconds", () => {
    expect(formatDuration(45)).toBe("45s");
  });
  it("minutes + seconds", () => {
    expect(formatDuration(192)).toBe("3m 12s");
  });
  it("hours + minutes", () => {
    expect(formatDuration(3 * 3600 + 4 * 60)).toBe("3h 4m");
  });
  it("returns em-dash for nullish/negative", () => {
    expect(formatDuration(null)).toBe(EMPTY_VALUE);
    expect(formatDuration(-1)).toBe(EMPTY_VALUE);
  });
});
