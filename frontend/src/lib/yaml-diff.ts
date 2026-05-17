/**
 * Semantic YAML diff for the /filters page.
 *
 * The naive line-diff approach is misleading when keys are reordered or values
 * are reformatted. Instead, we parse both sides to plain JS, then walk the
 * resulting tree and emit add/remove/change records keyed by dotted path.
 *
 * For the rankings dry-run diff (zip-level), see `rankingsDryRunDiff`.
 */

import { parse as parseYaml } from "yaml";

export type ChangeKind = "added" | "removed" | "changed";

export interface YamlChange {
  /** Dotted path, e.g. "weights.yield" or "filters[2].min". */
  path: string;
  kind: ChangeKind;
  before?: unknown;
  after?: unknown;
}

export interface YamlDiffResult {
  changes: YamlChange[];
  /** True if parsing fails on either side. */
  invalid: boolean;
  /** Error message from whichever side failed to parse. */
  error?: string;
}

/** Safely parse YAML, returning [parsed, error]. */
export function tryParseYaml(text: string): { ok: true; value: unknown } | { ok: false; error: string } {
  try {
    return { ok: true, value: parseYaml(text ?? "") };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return !!v && typeof v === "object" && !Array.isArray(v) && v.constructor === Object;
}

function diffNodes(before: unknown, after: unknown, path: string, out: YamlChange[]): void {
  // Both missing -> nothing.
  if (before === undefined && after === undefined) return;
  // Added.
  if (before === undefined) {
    out.push({ path, kind: "added", after });
    return;
  }
  // Removed.
  if (after === undefined) {
    out.push({ path, kind: "removed", before });
    return;
  }
  // Both null or primitive.
  if (!isPlainObject(before) && !isPlainObject(after) && !Array.isArray(before) && !Array.isArray(after)) {
    if (before !== after) {
      out.push({ path, kind: "changed", before, after });
    }
    return;
  }
  // Arrays — compare positionally. (Filters/weights configs in this app are
  // small, flat structures where positional diffing is acceptable.)
  if (Array.isArray(before) && Array.isArray(after)) {
    const len = Math.max(before.length, after.length);
    for (let i = 0; i < len; i++) {
      const subPath = `${path}[${i}]`;
      diffNodes(before[i], after[i], subPath, out);
    }
    return;
  }
  // Type mismatch (array vs object, etc.) -> treat as changed.
  if (Array.isArray(before) !== Array.isArray(after) || isPlainObject(before) !== isPlainObject(after)) {
    out.push({ path, kind: "changed", before, after });
    return;
  }
  // Both objects.
  if (isPlainObject(before) && isPlainObject(after)) {
    const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
    for (const k of Array.from(keys).sort()) {
      const subPath = path ? `${path}.${k}` : k;
      diffNodes(before[k], after[k], subPath, out);
    }
  }
}

export function diffYaml(beforeText: string, afterText: string): YamlDiffResult {
  const b = tryParseYaml(beforeText);
  const a = tryParseYaml(afterText);
  if (!b.ok) return { changes: [], invalid: true, error: `Before: ${b.error}` };
  if (!a.ok) return { changes: [], invalid: true, error: `After: ${a.error}` };
  const changes: YamlChange[] = [];
  diffNodes(b.value, a.value, "", changes);
  return { changes, invalid: false };
}

export interface RankingsDryRunDiff {
  added: string[];
  removed: string[];
  score_deltas: Array<{ zcta5: string; old: number | null; new: number | null; delta: number }>;
}

/**
 * Compute the rankings-level diff between two sets of (zcta5 -> score) maps,
 * with an optional top-N restriction.
 */
export function rankingsDryRunDiff(
  before: Array<{ zcta5: string; market_score: number | null }>,
  after: Array<{ zcta5: string; market_score: number | null }>,
  topN: number = 100,
): RankingsDryRunDiff {
  const beforeMap = new Map<string, number | null>();
  for (const r of before) beforeMap.set(r.zcta5, r.market_score);
  const afterMap = new Map<string, number | null>();
  for (const r of after) afterMap.set(r.zcta5, r.market_score);

  const beforeTop = new Set(
    [...before]
      .sort((x, y) => (y.market_score ?? -Infinity) - (x.market_score ?? -Infinity))
      .slice(0, topN)
      .map((r) => r.zcta5),
  );
  const afterTop = new Set(
    [...after]
      .sort((x, y) => (y.market_score ?? -Infinity) - (x.market_score ?? -Infinity))
      .slice(0, topN)
      .map((r) => r.zcta5),
  );

  const added: string[] = [];
  const removed: string[] = [];
  for (const z of afterTop) if (!beforeTop.has(z)) added.push(z);
  for (const z of beforeTop) if (!afterTop.has(z)) removed.push(z);
  added.sort();
  removed.sort();

  const score_deltas: RankingsDryRunDiff["score_deltas"] = [];
  // Anyone whose score moved by more than 0.1.
  const seen = new Set<string>([...beforeMap.keys(), ...afterMap.keys()]);
  for (const z of seen) {
    const o = beforeMap.get(z) ?? null;
    const n = afterMap.get(z) ?? null;
    if (o === null && n === null) continue;
    const delta = (n ?? 0) - (o ?? 0);
    if (Math.abs(delta) >= 0.1) {
      score_deltas.push({ zcta5: z, old: o, new: n, delta });
    }
  }
  score_deltas.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
  return { added, removed, score_deltas };
}
