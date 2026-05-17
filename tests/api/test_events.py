"""WebSocket smoke tests for ``/api/events``.

Uses FastAPI's :class:`TestClient.websocket_connect` so we don't need a
real network socket. ``publish`` is async; we drive it via
``asyncio.run`` from the test thread, which interacts with the
producer-side queues directly.
"""

from __future__ import annotations

import asyncio
import time

from fastapi.testclient import TestClient

from api import progress


def _publish_sync(event: progress.ProgressEvent) -> None:
    """Run ``publish`` on a fresh event loop in the calling thread."""
    asyncio.run(progress.publish(event))


def test_events_unfiltered_receives_everything(client: TestClient) -> None:
    with client.websocket_connect("/api/events") as ws:
        # Give the server a moment to register the subscription before
        # publishing — the connect handshake returns before the route
        # body has called ``subscribe()`` in some race orderings.
        time.sleep(0.1)
        _publish_sync(
            progress.ProgressEvent(
                type="backtest.progress",
                job_id="abc",
                payload={"snapshot": 1, "of": 3},
            )
        )
        msg = ws.receive_json()
        assert msg["type"] == "backtest.progress"
        assert msg["job_id"] == "abc"
        assert msg["payload"] == {"snapshot": 1, "of": 3}
        assert "timestamp" in msg


def test_events_filtered_by_job_id(client: TestClient) -> None:
    with client.websocket_connect("/api/events?job_id=keep") as ws:
        time.sleep(0.1)
        _publish_sync(
            progress.ProgressEvent(type="x", job_id="drop", payload={"v": 1})
        )
        _publish_sync(
            progress.ProgressEvent(type="x", job_id="keep", payload={"v": 2})
        )
        # The 'drop' event must not arrive; the next message must be the
        # 'keep' one. ``receive_json`` will block on an empty queue, so
        # by being able to receive the 'keep' event we've implicitly
        # established the 'drop' event was filtered.
        msg = ws.receive_json()
        assert msg["job_id"] == "keep"
        assert msg["payload"] == {"v": 2}


def test_events_multiple_messages_preserve_order(client: TestClient) -> None:
    with client.websocket_connect("/api/events") as ws:
        time.sleep(0.1)
        for i in range(3):
            _publish_sync(
                progress.ProgressEvent(
                    type="backtest.progress", job_id="j", payload={"i": i}
                )
            )
        seen = [ws.receive_json()["payload"]["i"] for _ in range(3)]
        assert seen == [0, 1, 2]
