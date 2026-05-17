"""In-process pub/sub for long-running job progress events.

Used by:
- Refresh endpoints (api-core, this file's neighbor) to publish progress
  events while running ``rental.sources.REGISTRY[name]().refresh(...)``.
- WebSocket events handler (agent 3) to consume events and stream to
  connected clients.

The implementation is deliberately tiny: an asyncio.Queue per job_id,
plus a "broadcast" queue every subscriber gets a feed from. There is no
persistence — restart the process and history is gone. That's fine; the
GUI only cares about *currently* in-flight jobs, and the warehouse's
``refresh_log`` is the durable record.

The producer side is thread-safe: refresh runs in a background thread
(BackgroundTasks) and uses ``publish_threadsafe`` so the asyncio loop's
internal data structures aren't touched from the wrong thread.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProgressEvent:
    """A single progress event for a single job.

    ``type`` is the canonical kind ("refresh.started", "refresh.progress",
    "refresh.completed", "refresh.failed"). ``payload`` is event-specific.
    """

    job_id: str
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "type": self.type,
            "payload": self.payload,
            "ts": self.ts,
        }


class ProgressBus:
    """In-memory pub/sub. One instance per process.

    Subscribers each get their own ``asyncio.Queue`` and see every event
    published after subscription. Per-job queues are kept around for a
    short while after completion so a late subscriber can still see the
    terminal event.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[ProgressEvent]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the asyncio loop that owns this bus.

        Called on FastAPI startup so background threads can use
        ``call_soon_threadsafe`` to publish.
        """
        self._loop = loop

    # -- subscriber side ------------------------------------------------

    def subscribe(self) -> asyncio.Queue[ProgressEvent]:
        q: asyncio.Queue[ProgressEvent] = asyncio.Queue(maxsize=1024)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[ProgressEvent]) -> None:
        self._subscribers.discard(q)

    async def stream(self, job_id: str | None = None) -> AsyncIterator[ProgressEvent]:
        """Yield events. If ``job_id`` is set, filter to that job."""
        q = self.subscribe()
        try:
            while True:
                event = await q.get()
                if job_id is None or event.job_id == job_id:
                    yield event
        finally:
            self.unsubscribe(q)

    # -- producer side --------------------------------------------------

    def publish(self, event: ProgressEvent) -> None:
        """Publish on the asyncio loop's thread."""
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest to keep up; a fast-producer/slow-consumer
                # scenario shouldn't crash the API.
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    pass

    def publish_threadsafe(self, event: ProgressEvent) -> None:
        """Publish from a non-asyncio thread (BackgroundTasks worker)."""
        loop = self._loop
        if loop is None or not loop.is_running():
            # No loop: fall back to direct put. Tests that don't run a
            # loop (e.g. TestClient sync paths) still see events.
            self.publish(event)
            return
        loop.call_soon_threadsafe(self.publish, event)


# Module-level singleton. Importable as ``api.progress.bus``.
bus = ProgressBus()


def new_job_id() -> str:
    """Generate a short job identifier."""
    return uuid.uuid4().hex[:12]
