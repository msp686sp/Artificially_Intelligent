"""Pin tests to this worktree's `src/` so they run reliably even when
other parallel agents reinstall the `rental` package elsewhere on the
shared environment.

`pip install -e` writes a path-config file pointing to a single source
checkout; with multiple worktrees racing on `pip install -e .`, the
last writer wins. Pre-pending our `src/` here keeps each worktree's
tests bound to its own code.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
src_str = str(SRC)
if src_str not in sys.path:
    sys.path.insert(0, src_str)

# Drop any pre-imported `rental` modules so the upcoming imports re-resolve
# against the path above. Important when another worktree's modules are
# already in sys.modules.
for mod in [m for m in list(sys.modules) if m == "rental" or m.startswith("rental.")]:
    other = getattr(sys.modules[mod], "__file__", "") or ""
    if not other.startswith(src_str):
        del sys.modules[mod]
