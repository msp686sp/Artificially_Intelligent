"""In-process async pub/sub for long-running job progress events.

Agent 1 (``api-core``) owns the canonical implementation; this module
provides a minimal fallback so the routes this agent owns
(``/api/backtest/*`` + ``/api/events``) can stand up before the
integration commit. The public surface is:

- :func:`publish(event)` — fan an event out to every subscriber.
- :func:`subscribe()` — async context manager returning a queue-backed
  subscription that yields events as they arrive.
- :class:`ProgressEvent` — typed payload (``type``, ``job_id``,
  ``payload``, ``timestamp``).

The implementation is purposely tiny: a module-level set of
``asyncio.Queue`` objects, guarded by an asyncio lock. The intent is
"single-process FastAPI dev server"; this is not a real broker.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


@dataclass
class ProgressEvent:
    """A single progress event published by a long-running job.

    ``type`` is a free-form string like ``backtest.progress`` or
    ``backtest.finished`` so the frontend can pattern-match without a
    closed enum. ``job_id`` is the opaque id returned by the route that
    kicked off the work. ``payload`` is whatever JSON-serialisable
    detail the producer wants to attach.
    """

    type: str
    job_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_subscribers: set[asyncio.Queue[ProgressEvent]] = set()
_lock = asyncio.Lock()


async def publish(event: ProgressEvent) -> None:
    """Fan ``event`` out to every active subscriber.

    Subscribers that have fallen behind are not dropped; their queue
    simply grows. The producer never blocks waiting for the consumer.
    """
    async with _lock:
        targets = list(_subscribers)
    for q in targets:
        q.put_nowait(event)


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
