import { describe, expect, it } from "vitest";
import {
  diffYaml,
  rankingsDryRunDiff,
  tryParseYaml,
} from "../../src/lib/yaml-diff";

describe("tryParseYaml", () => {
  it("parses valid YAML", () => {
    const r = tryParseYaml("a: 1\nb: 2\n");
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.value).toEqual({ a: 1, b: 2 });
  });

  it("returns an error for invalid YAML", () => {
    const r = tryParseYaml("a:\n  b: 1\n c: 2\n");
    expect(r.ok).toBe(false);
  });

  it("treats empty string as empty content", () => {
    const r = tryParseYaml("");
    expect(r.ok).toBe(true);
  });
});

describe("diffYaml", () => {
  it("returns no changes for identical text (even with whitespace)", () => {
    const a = "a: 1\nb: 2\n";
    const b = "a: 1\nb: 2\n";
    const r = diffYaml(a, b);
    expect(r.invalid).toBe(false);
    expect(r.changes).toEqual([]);
  });

  it("ignores key reordering", () => {
    const a = "a: 1\nb: 2\n";
    const b = "b: 2\na: 1\n";
    expect(diffYaml(a, b).changes).toEqual([]);
  });

  it("emits 'added' for new keys", () => {
    const a = "a: 1\n";
    const b = "a: 1\nb: 2\n";
    const r = diffYaml(a, b);
    expect(r.changes).toEqual([{ path: "b", kind: "added", after: 2 }]);
  });

  it("emits 'removed' for missing keys", () => {
    const a = "a: 1\nb: 2\n";
    const b = "a: 1\n";
    const r = diffYaml(a, b);
    expect(r.changes).toEqual([{ path: "b", kind: "removed", before: 2 }]);
  });

  it("emits 'changed' for value updates", () => {
    const a = "a: 1\n";
    const b = "a: 2\n";
    const r = diffYaml(a, b);
    expect(r.changes).toEqual([{ path: "a", kind: "changed", before: 1, after: 2 }]);
  });

  it("walks nested objects", () => {
    const a = "weights:\n  yield: 0.3\n  growth: 0.4\n";
    const b = "weights:\n  yield: 0.5\n  growth: 0.4\n  risk: 0.1\n";
    const r = diffYaml(a, b);
    expect(r.changes).toEqual([
      { path: "weights.growth", kind: "changed", before: 0.4, after: 0.4 }, // no
      { path: "weights.risk", kind: "added", after: 0.1 },
      { path: "weights.yield", kind: "changed", before: 0.3, after: 0.5 },
    ].filter((c) => !(c.kind === "changed" && c.before === c.after)));
  });

  it("walks arrays positionally", () => {
    const a = "filters:\n  - name: x\n    min: 1\n";
    const b = "filters:\n  - name: x\n    min: 2\n";
    const r = diffYaml(a, b);
    expect(r.changes).toEqual([
      { path: "filters[0].min", kind: "changed", before: 1, after: 2 },
    ]);
  });

  it("flags invalid YAML on either side", () => {
    // Unclosed flow-mapping is a hard syntax error in the `yaml` parser.
    const r = diffYaml("a: 1\n", "a: { unclosed");
    expect(r.invalid).toBe(true);
    expect(r.error).toBeTruthy();
  });
});

describe("rankingsDryRunDiff", () => {
  it("detects zips added to the top-N", () => {
    const before = [
      { zcta5: "10025", market_score: 80 },
      { zcta5: "10026", market_score: 70 },
    ];
    const after = [
      { zcta5: "10025", market_score: 80 },
      { zcta5: "10027", market_score: 75 },
    ];
    const d = rankingsDryRunDiff(before, after, 2);
    expect(d.added).toEqual(["10027"]);
    expect(d.removed).toEqual(["10026"]);
  });

  it("reports score deltas above the threshold", () => {
    const before = [
      { zcta5: "10025", market_score: 80 },
      { zcta5: "10026", market_score: 70 },
    ];
    const after = [
      { zcta5: "10025", market_score: 85 },
      { zcta5: "10026", market_score: 70.05 },
    ];
    const d = rankingsDryRunDiff(before, after, 100);
    // 10025 delta=5, included. 10026 delta=0.05, excluded.
    expect(d.score_deltas.map((s) => s.zcta5)).toEqual(["10025"]);
    expect(d.score_deltas[0]).toMatchObject({ zcta5: "10025", old: 80, new: 85, delta: 5 });
  });

  it("handles empty inputs gracefully", () => {
    const d = rankingsDryRunDiff([], [], 10);
    expect(d.added).toEqual([]);
    expect(d.removed).toEqual([]);
    expect(d.score_deltas).toEqual([]);
  });

  it("orders deltas by absolute magnitude", () => {
    const before = [
      { zcta5: "A", market_score: 10 },
      { zcta5: "B", market_score: 10 },
      { zcta5: "C", market_score: 10 },
    ];
    const after = [
      { zcta5: "A", market_score: 20 },
      { zcta5: "B", market_score: 5 },
      { zcta5: "C", market_score: 30 },
    ];
    const d = rankingsDryRunDiff(before, after, 10);
    expect(d.score_deltas.map((s) => s.zcta5)).toEqual(["C", "A", "B"]);
  });
});
