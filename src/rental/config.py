"""Project paths and YAML config loaders."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
CONFIG_DIR = REPO_ROOT / "config"
RAW_DIR = DATA_DIR / "raw"
WAREHOUSE_PATH = DATA_DIR / "warehouse.duckdb"


def load_yaml(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / name).read_text())
