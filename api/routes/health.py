"""Health + version endpoints."""

from __future__ import annotations

import platform
import time

from fastapi import APIRouter

from api import __version__ as api_version
from api.deps import START_TIME, get_settings
from api.models import HealthResponse, VersionResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe — also reports API version + process uptime."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.api_version,
        uptime_s=round(time.monotonic() - START_TIME, 3),
    )


@router.get("/version", response_model=VersionResponse)
def version() -> VersionResponse:
    """Version metadata: API, app (rental package), Python runtime."""
    try:
        from rental import __version__ as app_version  # type: ignore[attr-defined]
    except Exception:
        app_version = "unknown"
    return VersionResponse(
        api=api_version,
        app=str(app_version),
        python=platform.python_version(),
    )
