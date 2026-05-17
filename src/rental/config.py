"""Project paths and YAML config loaders."""

import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
CONFIG_DIR = REPO_ROOT / "config"
RAW_DIR = DATA_DIR / "raw"


def _resolve_warehouse_path() -> Path:
    """Warehouse path with env-var override.

    Honors ``RENTAL_WAREHOUSE_PATH`` so tests (and ad-hoc workflows) can
    redirect the DuckDB file without monkey-patching. Falls back to the
    repo-rooted default for normal use.
    """
    override = os.environ.get("RENTAL_WAREHOUSE_PATH")
    if override:
        return Path(override)
    return DATA_DIR / "warehouse.duckdb"


WAREHOUSE_PATH = _resolve_warehouse_path()


def _resolve_manifest_path() -> Path:
    """Manifest path with env-var override (mirrors warehouse override)."""
    override = os.environ.get("RENTAL_MANIFEST_PATH")
    if override:
        return Path(override)
    return DATA_DIR / "manifest.json"


MANIFEST_PATH = _resolve_manifest_path()


def load_yaml(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / name).read_text())
