import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRefreshJob } from "@/hooks/useRefreshJob";

// A minimal fake WebSocket we can drive synchronously from tests.
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onclose: ((ev: Event) => void) | null = null;
  closed = false;
  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }
  emit(payload: unknown) {
    this.onmessage?.({
      data: JSON.stringify(payload),
    } as unknown as MessageEvent);
  }
  close() {
    this.closed = true;
    this.onclose?.({} as Event);
  }
}

const wsFactory = (url: string) =>
  new FakeWebSocket(url) as unknown as WebSocket;

describe("useRefreshJob", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    // Stub fetch for the POST /refresh kickoff.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        return new Response(JSON.stringify({ job_id: "job-123" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }),
    );
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts in idle state with zero progress", () => {
    const { result } = renderHook(() => useRefreshJob(wsFactory));
    expect(result.current.state).toBe("idle");
    expect(result.current.progress).toBe(0);
    expect(result.current.error).toBeNull();
    expect(result.current.jobId).toBeNull();
  });

  it("transitions starting → running and exposes the job id", async () => {
    const { result } = renderHook(() => useRefreshJob(wsFactory));
    await act(async () => {
      await result.current.start("zillow_zhvi");
    });
    expect(result.current.state).toBe("running");
    expect(result.current.jobId).toBe("job-123");
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).toContain("/api/events");
    expect(FakeWebSocket.instances[0].url).toContain("job-123");
  });

  it("forwards progress events to state", async () => {
    const { result } = renderHook(() => useRefreshJob(wsFactory));
    await act(async () => {
      await result.current.start("zillow_zhvi");
    });
    const sock = FakeWebSocket.instances[0];
    act(() => {
      sock.emit({
        type: "refresh.progress",
        job_id: "job-123",
        payload: { step: "fetching", percent: 42, eta_seconds: 12 },
      });
    });
    await waitFor(() => expect(result.current.progress).toBeCloseTo(0.42));
    expect(result.current.step).toBe("fetching");
    expect(result.current.etaSeconds).toBe(12);
    expect(result.current.state).toBe("running");
  });

  it("calls onComplete and closes socket on refresh.complete", async () => {
    const onComplete = vi.fn();
    const { result } = renderHook(() => useRefreshJob(wsFactory));
    await act(async () => {
      await result.current.start("zillow_zhvi", { onComplete });
    });
    const sock = FakeWebSocket.instances[0];
    act(() => {
      sock.emit({
        type: "refresh.complete",
        job_id: "job-123",
        payload: { rows_loaded: 9_999 },
      });
    });
    await waitFor(() => expect(result.current.state).toBe("completed"));
    expect(result.current.progress).toBe(1);
    expect(onComplete).toHaveBeenCalledWith(9_999);
    expect(sock.closed).toBe(true);
  });

  it("calls onError and surfaces the message on refresh.error", async () => {
    const onError = vi.fn();
    const { result } = renderHook(() => useRefreshJob(wsFactory));
    await act(async () => {
      await result.current.start("zillow_zhvi", { onError });
    });
    const sock = FakeWebSocket.instances[0];
    act(() => {
      sock.emit({
        type: "refresh.error",
        job_id: "job-123",
        payload: { error: "boom" },
      });
    });
    await waitFor(() => expect(result.current.state).toBe("errored"));
    expect(result.current.error).toBe("boom");
    expect(onError).toHaveBeenCalledWith("boom");
    expect(sock.closed).toBe(true);
  });

  it("ignores events from a different job id", async () => {
    const { result } = renderHook(() => useRefreshJob(wsFactory));
    await act(async () => {
      await result.current.start("zillow_zhvi");
    });
    const sock = FakeWebSocket.instances[0];
    act(() => {
      sock.emit({
        type: "refresh.complete",
        job_id: "wrong-job",
        payload: {},
      });
    });
    // No state change.
    expect(result.current.state).toBe("running");
    expect(result.current.progress).toBe(0);
  });

  it("appends from_fixture=true when requested", async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    const { result } = renderHook(() => useRefreshJob(wsFactory));
    await act(async () => {
      await result.current.start("zillow_zhvi", { fromFixture: true });
    });
    expect(fetchMock).toHaveBeenCalled();
    const [url] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("from_fixture=true");
  });

  it("transitions to errored if the kickoff POST fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("nope", { status: 500 })),
    );
    const onError = vi.fn();
    const { result } = renderHook(() => useRefreshJob(wsFactory));
    await act(async () => {
      await result.current.start("zillow_zhvi", { onError });
    });
    expect(result.current.state).toBe("errored");
    expect(result.current.error).toBeTruthy();
    expect(onError).toHaveBeenCalled();
  });

  it("reset returns to idle", async () => {
    const { result } = renderHook(() => useRefreshJob(wsFactory));
    await act(async () => {
      await result.current.start("zillow_zhvi");
    });
    act(() => {
      result.current.reset();
    });
    expect(result.current.state).toBe("idle");
    expect(result.current.jobId).toBeNull();
    expect(result.current.progress).toBe(0);
  });
});
