import { useEffect, useRef, useState } from "react";
import type { WsEvent } from "@/api/types";

export type WebSocketStatus = "idle" | "connecting" | "open" | "closed" | "error";

interface UseWebSocketOptions {
  /** Defaults to `/api/events`. Pass a different path to override (rare). */
  path?: string;
  /** Auto-reconnect on close. Default: true (exponential backoff up to 30s). */
  reconnect?: boolean;
  /** Set false to skip connecting (e.g. feature flag off). */
  enabled?: boolean;
  /** Fired for every parsed message. */
  onEvent?: (event: WsEvent) => void;
}

/**
 * useWebSocket — subscribes to /api/events and dispatches typed
 * WsEvent objects. Returns the live status + the last event seen so
 * components can render banners without each one wiring its own
 * listener.
 *
 * In dev, the vite proxy forwards /api → http://localhost:8000 for
 * HTTP. WebSocket frames go through the /ws prefix configured in
 * vite.config.ts.
 */
export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { path = "/ws/events", reconnect = true, enabled = true, onEvent } = options;
  const [status, setStatus] = useState<WebSocketStatus>("idle");
  const [lastEvent, setLastEvent] = useState<WsEvent | null>(null);
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;

    let ws: WebSocket | null = null;
    let backoffMs = 500;
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (cancelled) return;
      setStatus("connecting");
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${proto}//${window.location.host}${path}`;
      try {
        ws = new WebSocket(url);
      } catch (err) {
        setStatus("error");
        return;
      }
      ws.onopen = () => {
        setStatus("open");
        backoffMs = 500;
      };
      ws.onmessage = (msg) => {
        try {
          const parsed = JSON.parse(msg.data) as WsEvent;
          setLastEvent(parsed);
          handlerRef.current?.(parsed);
        } catch {
          // Ignore non-JSON frames; backend should always send JSON.
        }
      };
      ws.onerror = () => {
        setStatus("error");
      };
      ws.onclose = () => {
        if (cancelled) return;
        setStatus("closed");
        if (reconnect) {
          reconnectTimer = setTimeout(connect, backoffMs);
          backoffMs = Math.min(backoffMs * 2, 30_000);
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [enabled, path, reconnect]);

  return { status, lastEvent };
}
