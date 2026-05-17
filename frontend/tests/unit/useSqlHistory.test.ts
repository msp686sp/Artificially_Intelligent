import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { useSavedQueries, useSqlHistory } from "@/hooks/useSqlHistory";

beforeEach(() => {
  window.localStorage.clear();
});
afterEach(() => {
  window.localStorage.clear();
});

describe("useSqlHistory", () => {
  it("pushes most-recent queries to the head and caps at 20", () => {
    const { result } = renderHook(() => useSqlHistory());
    expect(result.current.history).toEqual([]);
    act(() => {
      for (let i = 0; i < 25; i++) {
        result.current.push({
          query: `SELECT ${i};`,
          ranAt: new Date().toISOString(),
          ok: true,
        });
      }
    });
    expect(result.current.history).toHaveLength(20);
    expect(result.current.history[0].query).toBe("SELECT 24;");
    expect(result.current.history[19].query).toBe("SELECT 5;");
  });

  it("respects a custom max", () => {
    const { result } = renderHook(() => useSqlHistory(3));
    act(() => {
      ["a", "b", "c", "d"].forEach((q, i) =>
        result.current.push({
          query: `SELECT '${q}';`,
          ranAt: new Date(2024, 0, i + 1).toISOString(),
          ok: true,
        }),
      );
    });
    expect(result.current.history.map((h) => h.query)).toEqual([
      "SELECT 'd';",
      "SELECT 'c';",
      "SELECT 'b';",
    ]);
  });

  it("dedupes consecutive identical queries (whitespace normalized)", () => {
    const { result } = renderHook(() => useSqlHistory());
    act(() => {
      result.current.push({
        query: "SELECT 1;",
        ranAt: "2024-01-01T00:00:00Z",
        ok: true,
      });
      result.current.push({
        query: "  SELECT 1;  ",
        ranAt: "2024-01-01T00:00:01Z",
        ok: true,
      });
    });
    expect(result.current.history).toHaveLength(1);
    expect(result.current.history[0].ranAt).toBe("2024-01-01T00:00:01Z");
  });

  it("ignores empty queries", () => {
    const { result } = renderHook(() => useSqlHistory());
    act(() => {
      result.current.push({
        query: "   ",
        ranAt: new Date().toISOString(),
        ok: true,
      });
    });
    expect(result.current.history).toEqual([]);
  });

  it("clear() empties the buffer", () => {
    const { result } = renderHook(() => useSqlHistory());
    act(() => {
      result.current.push({
        query: "SELECT 1;",
        ranAt: new Date().toISOString(),
        ok: true,
      });
      result.current.clear();
    });
    expect(result.current.history).toEqual([]);
  });

  it("persists across hook remounts via localStorage", () => {
    const first = renderHook(() => useSqlHistory());
    act(() => {
      first.result.current.push({
        query: "SELECT 42;",
        ranAt: "2024-01-01T00:00:00Z",
        ok: true,
        rowCount: 1,
        elapsedMs: 12.3,
      });
    });
    first.unmount();
    const second = renderHook(() => useSqlHistory());
    expect(second.result.current.history).toHaveLength(1);
    expect(second.result.current.history[0]).toMatchObject({
      query: "SELECT 42;",
      rowCount: 1,
      elapsedMs: 12.3,
    });
  });

  it("remove(i) drops one entry", () => {
    const { result } = renderHook(() => useSqlHistory());
    act(() => {
      ["a", "b", "c"].forEach((q, i) =>
        result.current.push({
          query: `SELECT ${q};`,
          ranAt: new Date(2024, 0, i + 1).toISOString(),
          ok: true,
        }),
      );
      result.current.remove(1);
    });
    expect(result.current.history.map((h) => h.query)).toEqual([
      "SELECT c;",
      "SELECT a;",
    ]);
  });
});

describe("useSavedQueries", () => {
  it("save() adds a query and re-saving replaces the prior entry", () => {
    const { result } = renderHook(() => useSavedQueries());
    act(() => {
      result.current.save("top", "SELECT 1;");
      result.current.save("top", "SELECT 2;");
    });
    expect(result.current.saved).toHaveLength(1);
    expect(result.current.saved[0].query).toBe("SELECT 2;");
  });

  it("ignores empty name or query", () => {
    const { result } = renderHook(() => useSavedQueries());
    act(() => {
      result.current.save("", "SELECT 1;");
      result.current.save("name", "   ");
    });
    expect(result.current.saved).toEqual([]);
  });

  it("remove() drops by name", () => {
    const { result } = renderHook(() => useSavedQueries());
    act(() => {
      result.current.save("a", "SELECT 1;");
      result.current.save("b", "SELECT 2;");
      result.current.remove("a");
    });
    expect(result.current.saved.map((s) => s.name)).toEqual(["b"]);
  });
});
