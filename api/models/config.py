"""Pydantic models for the ``/api/config/*`` endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConfigFileList(BaseModel):
    """Allowed config files under ``config/`` ending in .yaml/.yml."""

    files: list[str]


class ConfigFile(BaseModel):
    """A YAML config file, both the raw text and the parsed dict.

    ``parsed`` is ``None`` when the file is unreadable or fails to
    parse, but the route raises before that under normal flow; this
    type signature mirrors the contract in ``docs/gooey-plan.md``.
    """

    name: str
    content: str
    parsed: dict[str, Any] | None = None
    mtime: float = Field(description="Last modification time (epoch seconds)")


class ConfigFilePut(BaseModel):
    """Body for ``PUT /api/config/{file}``."""

    content: str
