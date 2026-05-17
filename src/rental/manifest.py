"""Refresh manifest — durable record of when each source last loaded.

The manifest is a small JSON file at ``data/manifest.json`` mapping each
source name to its last successful refresh:

    {
      "zillow_zhvi": {
        "last_refresh": "2026-05-17T12:34:56.000000+00:00",
        "rows_loaded": 15,
        "status": "ok"
      }
    }

It's deliberately separate from ``refresh_log`` in the warehouse: the
manifest answers "what's the freshness of source X right now" in one O(1)
read without opening DuckDB, which is what ``rental status`` and
``make doctor`` need.

Status values:
- ``"ok"`` — last refresh succeeded; ``rows_loaded`` is populated.
- ``"error"`` — last refresh failed; ``error`` carries the message.

Updates are atomic via tmpfile + rename.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from rental import config


@dataclass(frozen=True)
class ManifestEntry:
    source: str
    last_refresh: datetime
    rows_loaded: int
    status: str
    error: str | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "last_refresh": self.last_refresh.isoformat(),
            "rows_loaded": self.rows_loaded,
            "status": self.status,
        }
        if self.error is not None:
            d["error"] = self.error
        return d

    @classmethod
    def from_dict(cls, source: str, payload: dict) -> ManifestEntry:
        return cls(
            source=source,
            last_refresh=datetime.fromisoformat(payload["last_refresh"]),
            rows_loaded=int(payload.get("rows_loaded", 0)),
            status=str(payload.get("status", "ok")),
            error=payload.get("error"),
        )


def _manifest_path() -> Path:
    # Re-resolve each call so RENTAL_MANIFEST_PATH overrides set at test
    # time are honored.
    return config._resolve_manifest_path()


def load_manifest(path: Path | None = None) -> dict[str, ManifestEntry]:
    """Read the manifest. Returns an empty dict if it doesn't exist."""
    target = path or _manifest_path()
    if not target.exists():
        return {}
    try:
        raw = json.loads(target.read_text())
    except json.JSONDecodeError:
        return {}
    return {
        src: ManifestEntry.from_dict(src, payload)
        for src, payload in raw.items()
        if isinstance(payload, dict) and "last_refresh" in payload
    }


def _atomic_write(target: Path, data: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(dir=str(target.parent), prefix=".manifest.", suffix=".tmp")
    tmp = Path(tmp_str)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(data)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def update_manifest(
    source: str,
    rows_loaded: int,
    status: str,
    error: str | None = None,
    *,
    when: datetime | None = None,
    path: Path | None = None,
) -> ManifestEntry:
    """Upsert a single source's entry; persist atomically."""
    target = path or _manifest_path()
    entry = ManifestEntry(
        source=source,
        last_refresh=when or datetime.now(UTC),
        rows_loaded=rows_loaded,
        status=status,
        error=error,
    )
    current = load_manifest(target)
    current[source] = entry
    serializable = {src: e.to_dict() for src, e in sorted(current.items())}
    _atomic_write(target, json.dumps(serializable, indent=2, sort_keys=True) + "\n")
    return entry


def staleness_days(entry: ManifestEntry, *, now: datetime | None = None) -> float:
    """Days since the entry's last refresh (UTC)."""
    ref = now or datetime.now(UTC)
    last = entry.last_refresh
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return (ref - last).total_seconds() / 86400.0
