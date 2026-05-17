import { describe, expect, it, beforeEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  parseCompareZips,
  serializeCompareZips,
  useCompare,
} from "../../src/hooks/useCompare";

describe("parseCompareZips", () => {
  it("parses comma-separated 5-digit zips", () => {
    expect(parseCompareZips("10025,46220,30309")).toEqual(["10025", "46220", "30309"]);
  });

  it("ignores invalid entries", () => {
    expect(parseCompareZips("10025,abc,123,99999")).toEqual(["10025", "99999"]);
  });

  it("dedupes", () => {
    expect(parseCompareZips("10025,10025,46220")).toEqual(["10025", "46220"]);
  });

  it("treats null/empty as empty array", () => {
    expect(parseCompareZips(null)).toEqual([]);
    expect(parseCompareZips("")).toEqual([]);
  });
});

describe("serializeCompareZips", () => {
  it("joins with commas", () => {
    expect(serializeCompareZips(["10025", "46220"])).toBe("10025,46220");
  });

  it("dedupes & filters invalid", () => {
    expect(serializeCompareZips(["10025", "10025", "bad", "46220"])).toBe("10025,46220");
  });
});

describe("useCompare", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  function wrapper(client: QueryClient) {
    return function Wrapper({ children }: { children: React.ReactNode }) {
      return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    };
  }

  it("fetches detail+zhvi+zori for each zcta5", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.startsWith("/api/zips/")) {
        const z = url.split("/").pop()!;
        return new Response(
          JSON.stringify({ zcta5: z, market_score: 80, sub_scores: { yield_score: 60 } }),
          { headers: { "content-type": "application/json" } },
        );
      }
      if (url.includes("/charts/zhvi/")) {
        const z = url.split("/").pop()!;
        return new Response(
          JSON.stringify({ zcta5: z, series: [{ date: "2020-01-01", value: 100 }] }),
          { headers: { "content-type": "application/json" } },
        );
      }
      if (url.includes("/charts/zori/")) {
        const z = url.split("/").pop()!;
        return new Response(
          JSON.stringify({ zcta5: z, series: [{ date: "2020-01-01", value: 1000 }] }),
          { headers: { "content-type": "application/json" } },
        );
      }
      return new Response("{}", { headers: { "content-type": "application/json" } });
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const zips = ["10025", "46220"];
    const { result } = renderHook(() => useCompare(zips), { wrapper: wrapper(client) });

    await waitFor(() => {
      expect(result.current.details[0]?.data).toBeTruthy();
      expect(result.current.details[1]?.data).toBeTruthy();
      expect(result.current.zhvi[0]?.data).toBeTruthy();
      expect(result.current.zori[1]?.data).toBeTruthy();
    });

    expect(result.current.zcta5s).toEqual(zips);
    expect(result.current.details).toHaveLength(2);
    expect(result.current.zhvi).toHaveLength(2);
    expect(result.current.zori).toHaveLength(2);
    // Each zip triggers three fetches.
    expect(fetchMock).toHaveBeenCalledTimes(6);
  });

  it("returns empty arrays when no zcta5s provided", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useCompare([]), { wrapper: wrapper(client) });
    expect(result.current.zcta5s).toEqual([]);
    expect(result.current.details).toEqual([]);
    expect(result.current.zhvi).toEqual([]);
    expect(result.current.zori).toEqual([]);
  });
});
