"""Pytest bootstrap.

Ensures the local ``src/`` tree is preferred over any pre-installed
``rental`` package on PYTHONPATH. Useful when multiple worktrees share
a Python environment and any one of them might have run
``pip install -e .`` last.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).parent / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
