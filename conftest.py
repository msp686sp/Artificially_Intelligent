"""Pytest bootstrap.

Ensures the local ``src/`` (rental package) and worktree root (in-tree
``api/`` package) are importable before pytest collects anything —
even when an editable install elsewhere has registered a different
finder. Once the GUI integration is on a single branch this is mostly
belt-and-suspenders, but it keeps test runs deterministic.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.resolve()
_SRC = _ROOT / "src"

for entry in (_SRC, _ROOT):
    if entry.exists() and str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
