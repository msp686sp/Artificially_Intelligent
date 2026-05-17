"""In-process pub/sub for long-running job progress events.

Used by:
- Refresh endpoints (agent 1) to publish progress events while running
  ``rental.sources.REGISTRY[name]().refresh(...)`` from a background
  thread (``publish_threadsafe``).
- Backtest endpoints (agent 3) to publish from background tasks
  (``publish``, the async coroutine).
- WebSocket events handler (agent 3) to consume events and stream to
  connected clients (``subscribe`` async context manager).

The implementation is purposely tiny: a module-level set of
``asyncio.Queue`` subscribers, plus a ``ProgressBus`` class for the
thread-safe publish path that the refresh endpoint needs. There is no
persistence — restart the process and history is gone. That's fine; the
GUI only cares about *currently* in-flight jobs, and the warehouse's
``refresh_log`` is the durable record of refreshes.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


@dataclass
class ProgressEvent:
    """A single progress event published by a long-running job.

    Two timestamp views are provided for back-compat:
    - ``ts``: float seconds since epoch (agent 1's refresh path uses this).
    - ``timestamp``: ISO-8601 string (agent 3's backtest path uses this).

    ``type`` is a free-form string like ``"refresh.progress"`` or
    ``"backtest.finished"`` so the frontend can pattern-match without a
    closed enum. ``job_id`` is the opaque id returned by the route that
    kicked off the work. ``payload`` is whatever JSON-serialisable
    detail the producer wants to attach.
    """

    type: str
    job_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    timestamp: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "job_id": self.job_id,
            "payload": self.payload,
            "ts": self.ts,
            "timestamp": self.timestamp,
        }


_subscribers: set[asyncio.Queue[ProgressEvent]] = set()
_lock = asyncio.Lock()


class ProgressBus:
    """In-memory pub/sub. One instance per process (the ``bus`` singleton).

    Subscribers each get their own ``asyncio.Queue`` and see every event
    published after subscription. The producer side is thread-safe via
    ``publish_threadsafe`` so a background thread (used by the
    long-running refresh task) can publish without touching loop
    internals from the wrong thread.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the asyncio loop that owns this bus.

        Called on FastAPI startup (via lifespan) so background threads
        can use ``call_soon_threadsafe`` to publish.
        """
        self._loop = loop

    # -- subscriber side ------------------------------------------------

    def subscribe(self) -> asyncio.Queue[ProgressEvent]:
        q: asyncio.Queue[ProgressEvent] = asyncio.Queue(maxsize=1024)
        _subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[ProgressEvent]) -> None:
        _subscribers.discard(q)

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

    def publish_sync(self, event: ProgressEvent) -> None:
        """Publish on the asyncio loop's thread (or non-async caller)."""
        for q in list(_subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest to keep up.
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    pass

    def publish_threadsafe(self, event: ProgressEvent) -> None:
        """Publish from a non-asyncio thread (background worker)."""
        loop = self._loop
        if loop is None or not loop.is_running():
            # No loop: fall back to direct put. Tests that don't run a
            # loop (e.g. TestClient sync paths) still see events.
            self.publish_sync(event)
            return
        loop.call_soon_threadsafe(self.publish_sync, event)


# Module-level singleton. Importable as ``api.progress.bus``.
bus = ProgressBus()


async def publish(event: ProgressEvent) -> None:
    """Fan ``event`` out to every active subscriber (async entry point).

    Used by code running inside the asyncio loop (e.g. FastAPI route
    handlers and asyncio.create_task background tasks). Synchronous
    callers should use ``bus.publish_sync`` or ``bus.publish_threadsafe``.
    """
    async with _lock:
        targets = list(_subscribers)
    for q in targets:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            try:
                q.get_nowait()
                q.put_nowait(event)
            except Exception:
                pass


@contextlib.asynccontextmanager
async def subscribe() -> AsyncIterator[asyncio.Queue[ProgressEvent]]:
    """Yield an asyncio queue that receives every event from ``publish``.

    Use as ``async with subscribe() as queue: ...``. On exit the queue
    is removed from the broadcast set.
    """
    queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()
    async with _lock:
        _subscribers.add(queue)
    try:
        yield queue
    finally:
        async with _lock:
            _subscribers.discard(queue)


async def _reset_for_tests() -> None:
    """Drop all subscribers. Tests call this between cases."""
    async with _lock:
        _subscribers.clear()


def new_job_id() -> str:
    """Generate a short job identifier."""
    return uuid.uuid4().hex[:12]
