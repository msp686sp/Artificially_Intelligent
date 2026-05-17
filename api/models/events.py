"""Pydantic model for messages emitted over the WebSocket ``/api/events``."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EventMessage(BaseModel):
    """One message on the events channel.

    Mirrors :class:`api.progress.ProgressEvent`; we keep the pydantic
    model here so the OpenAPI surface can document the schema even
    though WebSocket frames are not part of OpenAPI per se.
    """

    type: str
    job_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str
