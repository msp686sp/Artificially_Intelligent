"""Pytest bootstrap.

Ensures the local ``src/`` tree is preferred over any pre-installed
``rental`` package on PYTHONPATH. Useful when multiple worktrees share
a Python environment and any one of them might have run
``pip install -e .`` last.

Also prefers the repo root so the in-tree ``api/`` package (added by
the GUI build) resolves locally rather than from a sibling worktree.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).parent
_SRC = _ROOT / "src"
for entry in (_SRC, _ROOT):
    if entry.exists() and str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
