"""WebSocket ``/api/events`` — progress fan-out for long-running jobs.

Clients connect and optionally pass ``?job_id=<id>`` as a filter. Each
message is the dict form of :class:`api.progress.ProgressEvent`. With
no filter every event is forwarded; with a filter only events whose
``job_id`` matches reach the client.
"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from api import progress

router = APIRouter(tags=["events"])


@router.websocket("/events")
async def events_ws(
    websocket: WebSocket,
    job_id: str | None = Query(default=None),
) -> None:
    """Stream progress events to the connected client.

    The loop terminates when the client disconnects. A background task
    watches for the client's close frame so the producer side stops
    waiting on ``queue.get()``.
    """
    await websocket.accept()

    async with progress.subscribe() as queue:
        stop = asyncio.Event()

        async def _watch_for_close() -> None:
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                stop.set()
            except Exception:  # noqa: BLE001 - any error means "give up"
                stop.set()

        watcher = asyncio.create_task(_watch_for_close())
        try:
            while not stop.is_set():
                get_task = asyncio.create_task(queue.get())
                stop_task = asyncio.create_task(stop.wait())
                done, pending = await asyncio.wait(
                    {get_task, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()
                if stop_task in done:
                    break
                event = get_task.result()
                if job_id is not None and event.job_id != job_id:
                    continue
                try:
                    await websocket.send_json(event.to_dict())
                except WebSocketDisconnect:
                    break
                except RuntimeError:
                    # Socket already closed.
                    break
        finally:
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await watcher
            with contextlib.suppress(Exception):
                await websocket.close()
