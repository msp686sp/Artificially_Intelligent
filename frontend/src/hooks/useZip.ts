import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import type {
  RedfinSeriesResponse,
  TimeSeriesResponse,
  ZipDetail,
} from "../api/types";

export function useZip(zcta5: string | undefined) {
  return useQuery<ZipDetail>({
    queryKey: ["zip", zcta5],
    queryFn: ({ signal }) => apiFetch<ZipDetail>(`/api/zips/${zcta5}`, { signal }),
    enabled: !!zcta5,
  });
}

export function useZhvi(zcta5: string | undefined) {
  return useQuery<TimeSeriesResponse>({
    queryKey: ["chart", "zhvi", zcta5],
    queryFn: ({ signal }) => apiFetch<TimeSeriesResponse>(`/api/charts/zhvi/${zcta5}`, { signal }),
    enabled: !!zcta5,
  });
}

export function useZori(zcta5: string | undefined) {
  return useQuery<TimeSeriesResponse>({
    queryKey: ["chart", "zori", zcta5],
    queryFn: ({ signal }) => apiFetch<TimeSeriesResponse>(`/api/charts/zori/${zcta5}`, { signal }),
    enabled: !!zcta5,
  });
}

export function useRedfin(zcta5: string | undefined) {
  return useQuery<RedfinSeriesResponse>({
    queryKey: ["chart", "redfin", zcta5],
    queryFn: ({ signal }) => apiFetch<RedfinSeriesResponse>(`/api/charts/redfin/${zcta5}`, { signal }),
    enabled: !!zcta5,
  });
}
