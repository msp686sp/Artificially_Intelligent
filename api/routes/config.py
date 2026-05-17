"""``/api/config/*`` — editor backing for ``config/*.yaml``.

The GUI's filter + weights pages read and PUT YAML through these
endpoints. The route is intentionally narrow:

- only files inside the project's ``config/`` directory,
- only ``*.yaml`` / ``*.yml`` extensions,
- no path traversal (no ``..``, no absolute paths, no nested dirs),
- PUT validates that the body parses as a YAML mapping (top-level
  dict), since every downstream loader expects a dict.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Response, status

from api.models.config import ConfigFile, ConfigFileList, ConfigFilePut


def _project_root() -> Path:
    """Project root (the directory containing ``config/``).

    The repo layout has ``config/`` at the top level next to ``api/``.
    Tests override the location via the ``RENTAL_CONFIG_DIR`` env var.
    """
    override = os.environ.get("RENTAL_CONFIG_DIR")
    if override:
        return Path(override).resolve()
    return (Path(__file__).resolve().parents[2] / "config").resolve()


def _safe_resolve(name: str) -> Path:
    """Resolve ``name`` relative to the config dir, rejecting traversal."""
    if not name:
        raise HTTPException(status_code=400, detail="empty filename")
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="invalid filename")
    if os.path.isabs(name):
        raise HTTPException(status_code=400, detail="absolute path not allowed")
    suffix = Path(name).suffix.lower()
    if suffix not in {".yaml", ".yml"}:
        raise HTTPException(status_code=400, detail="only .yaml/.yml allowed")

    root = _project_root()
    candidate = (root / name).resolve()
    # Belt-and-braces: ensure the resolved path is still inside the root.
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="path escapes config dir") from exc
    return candidate


router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/files", response_model=ConfigFileList)
def list_config_files() -> ConfigFileList:
    """List every YAML config file under the project's ``config/`` dir."""
    root = _project_root()
    if not root.exists():
        return ConfigFileList(files=[])
    files = sorted(
        p.name
        for p in root.iterdir()
        if p.is_file() and p.suffix.lower() in {".yaml", ".yml"}
    )
    return ConfigFileList(files=files)


@router.get("/{file}", response_model=ConfigFile)
def read_config_file(file: str) -> ConfigFile:
    """Return the YAML file's raw content, parsed dict, and mtime."""
    path = _safe_resolve(file)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{file} not found")
    content = path.read_text()
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError:
        parsed = None
    if not isinstance(parsed, dict):
        # The contract says ``parsed: dict | None``; anything that isn't
        # a top-level mapping is normalised to ``None`` here so the
        # frontend can show the raw text without crashing.
        parsed_dict: dict | None = None
    else:
        parsed_dict = parsed
    return ConfigFile(
        name=file,
        content=content,
        parsed=parsed_dict,
        mtime=path.stat().st_mtime,
    )


@router.put("/{file}", status_code=status.HTTP_204_NO_CONTENT)
def write_config_file(file: str, body: ConfigFilePut) -> Response:
    """Persist new YAML content. Validates that it parses as a dict."""
    path = _safe_resolve(file)
    try:
        parsed = yaml.safe_load(body.content)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"invalid YAML: {exc}") from exc
    if parsed is None or not isinstance(parsed, dict):
        raise HTTPException(
            status_code=400,
            detail="YAML must be a top-level mapping (dict)",
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body.content)
    os.replace(tmp, path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
