import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import type { TimeSeriesResponse, ZipDetail } from "../api/types";

/**
 * Parse the ?z=NNNNN,NNNNN,... query param. Strips invalid entries.
 */
export function parseCompareZips(raw: string | null | undefined): string[] {
  if (!raw) return [];
  return Array.from(
    new Set(
      raw
        .split(",")
        .map((s) => s.trim())
        .filter((s) => /^\d{5}$/.test(s)),
    ),
  );
}

export function serializeCompareZips(zips: readonly string[]): string {
  return Array.from(new Set(zips)).filter((z) => /^\d{5}$/.test(z)).join(",");
}

export interface CompareData {
  zcta5s: string[];
  details: Array<{ zcta5: string; data: ZipDetail | undefined; isLoading: boolean; error: unknown }>;
  zhvi: Array<{ zcta5: string; data: TimeSeriesResponse | undefined; isLoading: boolean }>;
  zori: Array<{ zcta5: string; data: TimeSeriesResponse | undefined; isLoading: boolean }>;
  isLoading: boolean;
}

export function useCompare(zcta5s: readonly string[]): CompareData {
  const detailQueries = useQueries({
    queries: zcta5s.map((z) => ({
      queryKey: ["zip", z],
      queryFn: ({ signal }: { signal?: AbortSignal }) =>
        apiFetch<ZipDetail>(`/api/zips/${z}`, { signal }),
      enabled: !!z,
    })),
  });
  const zhviQueries = useQueries({
    queries: zcta5s.map((z) => ({
      queryKey: ["chart", "zhvi", z],
      queryFn: ({ signal }: { signal?: AbortSignal }) =>
        apiFetch<TimeSeriesResponse>(`/api/charts/zhvi/${z}`, { signal }),
      enabled: !!z,
    })),
  });
  const zoriQueries = useQueries({
    queries: zcta5s.map((z) => ({
      queryKey: ["chart", "zori", z],
      queryFn: ({ signal }: { signal?: AbortSignal }) =>
        apiFetch<TimeSeriesResponse>(`/api/charts/zori/${z}`, { signal }),
      enabled: !!z,
    })),
  });

  return useMemo(
    () => ({
      zcta5s: [...zcta5s],
      details: zcta5s.map((z, i) => ({
        zcta5: z,
        data: detailQueries[i]?.data,
        isLoading: detailQueries[i]?.isLoading ?? false,
        error: detailQueries[i]?.error,
      })),
      zhvi: zcta5s.map((z, i) => ({
        zcta5: z,
        data: zhviQueries[i]?.data,
        isLoading: zhviQueries[i]?.isLoading ?? false,
      })),
      zori: zcta5s.map((z, i) => ({
        zcta5: z,
        data: zoriQueries[i]?.data,
        isLoading: zoriQueries[i]?.isLoading ?? false,
      })),
      isLoading:
        detailQueries.some((q) => q.isLoading) ||
        zhviQueries.some((q) => q.isLoading) ||
        zoriQueries.some((q) => q.isLoading),
    }),
    [zcta5s, detailQueries, zhviQueries, zoriQueries],
  );
}
