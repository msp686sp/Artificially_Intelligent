import { useCallback, useEffect, useRef, useState } from "react";
import { apiPost, wsUrl } from "@/api/client";
import type { RefreshJobEvent, RefreshJobResponse } from "@/api/types";

export type RefreshState =
  | "idle"
  | "starting"
  | "running"
  | "completed"
  | "errored";

export interface RefreshJobOptions {
  /** When true, use the bundled fixture instead of fetching upstream. */
  fromFixture?: boolean;
  /** Called when the job completes successfully. */
  onComplete?: (rowsLoaded: number | undefined) => void;
  /** Called on error. */
  onError?: (message: string) => void;
}

export interface RefreshJobApi {
  state: RefreshState;
  progress: number; // 0–1
  step: string | null;
  etaSeconds: number | null;
  error: string | null;
  jobId: string | null;
  start: (source: string, options?: RefreshJobOptions) => Promise<void>;
  reset: () => void;
}

interface WsFactory {
  (url: string): WebSocket;
}

/**
 * useRefreshJob — kicks off `POST /api/sources/{name}/refresh` and
 * streams progress over the `/api/events?job_id=...` WebSocket.
 *
 * The `wsFactory` parameter exists so tests can inject a fake WebSocket.
 * Production callers should leave it undefined.
 */
export function useRefreshJob(wsFactory?: WsFactory): RefreshJobApi {
  const [state, setState] = useState<RefreshState>("idle");
  const [progress, setProgress] = useState(0);
  const [step, setStep] = useState<string | null>(null);
  const [etaSeconds, setEtaSeconds] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const callbacksRef = useRef<{
    onComplete?: RefreshJobOptions["onComplete"];
    onError?: RefreshJobOptions["onError"];
  }>({});

  const closeSocket = useCallback(() => {
    const sock = socketRef.current;
    if (sock) {
      try {
        sock.close();
      } catch {
        /* ignore */
      }
      socketRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    closeSocket();
    setState("idle");
    setProgress(0);
    setStep(null);
    setEtaSeconds(null);
    setError(null);
    setJobId(null);
    callbacksRef.current = {};
  }, [closeSocket]);

  useEffect(() => () => closeSocket(), [closeSocket]);

  const start = useCallback(
    async (source: string, options: RefreshJobOptions = {}) => {
      reset();
      callbacksRef.current = {
        onComplete: options.onComplete,
        onError: options.onError,
      };
      setState("starting");
      try {
        const path = `/api/sources/${encodeURIComponent(source)}/refresh${
          options.fromFixture ? "?from_fixture=true" : ""
        }`;
        const resp = await apiPost<RefreshJobResponse>(path);
        const newJobId = resp.job_id;
        setJobId(newJobId);
        setState("running");

        const factory = wsFactory ?? ((u: string) => new WebSocket(u));
        const sock = factory(wsUrl(`/api/events?job_id=${newJobId}`));
        socketRef.current = sock;

        sock.onmessage = (msg: MessageEvent) => {
          let parsed: RefreshJobEvent | null = null;
          try {
            parsed =
              typeof msg.data === "string"
                ? (JSON.parse(msg.data) as RefreshJobEvent)
                : null;
          } catch {
            parsed = null;
          }
          if (!parsed) return;
          if (parsed.job_id !== newJobId) return;
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const payload = (parsed.payload ?? {}) as any;
          if (parsed.type === "refresh.progress") {
            if (typeof payload.percent === "number") {
              setProgress(Math.min(1, Math.max(0, payload.percent / 100)));
            }
            if (payload.step) setStep(String(payload.step));
            if (payload.eta_seconds !== undefined && payload.eta_seconds !== null) {
              setEtaSeconds(Number(payload.eta_seconds));
            }
          } else if (parsed.type === "refresh.complete") {
            setProgress(1);
            setState("completed");
            callbacksRef.current.onComplete?.(Number(payload.rows_loaded ?? 0));
            closeSocket();
          } else if (parsed.type === "refresh.error") {
            const errMsg = String(payload.error ?? "Refresh failed.");
            setError(errMsg);
            setState("errored");
            callbacksRef.current.onError?.(errMsg);
            closeSocket();
          }
        };
        sock.onerror = () => {
          // Don't immediately flip to errored — the API may also send a
          // refresh.error message; but ensure the user sees something.
          setError((prev) => prev ?? "WebSocket connection error.");
        };
        sock.onclose = () => {
          // If we never saw a terminal event, treat unexpected close as
          // a transient state, not an error.
          socketRef.current = null;
        };
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        setState("errored");
        callbacksRef.current.onError?.(msg);
      }
    },
    [reset, closeSocket, wsFactory],
  );

  return { state, progress, step, etaSeconds, error, jobId, start, reset };
}
