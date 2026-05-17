"""Manifest endpoints — reads ``data/manifest.json``."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.models import ManifestEntryModel, ManifestResponse
from rental.manifest import load_manifest

router = APIRouter(tags=["manifest"])


def _entry_to_model(entry) -> ManifestEntryModel:
    return ManifestEntryModel(
        source=entry.source,
        last_refresh=entry.last_refresh,
        rows_loaded=entry.rows_loaded,
        status=entry.status,
        error=entry.error,
    )


@router.get("/manifest", response_model=ManifestResponse)
def get_manifest() -> ManifestResponse:
    """Return every manifest entry sorted by source name."""
    manifest = load_manifest()
    entries = [_entry_to_model(manifest[src]) for src in sorted(manifest)]
    return ManifestResponse(entries=entries)


@router.get("/manifest/{source}", response_model=ManifestEntryModel)
def get_manifest_entry(source: str) -> ManifestEntryModel:
    """Return a single manifest entry, or 404 if the source has never refreshed."""
    manifest = load_manifest()
    if source not in manifest:
        raise HTTPException(status_code=404, detail=f"No manifest entry for source '{source}'")
    return _entry_to_model(manifest[source])
