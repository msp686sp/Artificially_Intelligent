"""Pytest bootstrap.

Two jobs:

1. Make the local ``src/`` (rental package) and worktree root (api
   package) importable before pytest collects anything.
2. Force ``api`` and ``rental`` imports to resolve inside this
   worktree, even when a sibling worktree's editable install
   (via ``__editable__.rental-0.0.1.pth``) has registered a meta-path
   finder pointing elsewhere.
"""

from __future__ import annotations

import sys
from importlib.machinery import PathFinder
from importlib.util import spec_from_file_location
from pathlib import Path

_ROOT = Path(__file__).parent.resolve()
_SRC = _ROOT / "src"

for entry in (_SRC, _ROOT):
    if entry.exists() and str(entry) not in sys.path:
        sys.path.insert(0, str(entry))


class _WorktreeFirstFinder:
    """Resolve ``api``/``rental`` from this worktree, ahead of any
    editable-install finder that a sibling worktree may have installed.
    """

    _packages = {"api": _ROOT / "api", "rental": _SRC / "rental"}

    @classmethod
    def find_spec(cls, fullname, path=None, target=None):  # noqa: D401
        root = fullname.partition(".")[0]
        base = cls._packages.get(root)
        if base is None or not base.exists():
            return None
        if fullname == root:
            search = [str(base)]
        else:
            rel_parts = fullname.split(".")[1:-1]
            search_dir = base.joinpath(*rel_parts) if rel_parts else base
            search = [str(search_dir)]
        spec = PathFinder.find_spec(fullname.rsplit(".", 1)[-1], search)
        if spec is None:
            return None
        origin = spec.origin
        if origin is None:
            return None
        # Rebuild the spec under the full dotted name so Python registers
        # ``api.routes.config`` (not ``config``) when the module loads.
        return spec_from_file_location(
            fullname,
            origin,
            submodule_search_locations=(
                list(spec.submodule_search_locations)
                if spec.submodule_search_locations is not None
                else None
            ),
        )


if not any(getattr(f, "_is_worktree_first", False) for f in sys.meta_path):
    _WorktreeFirstFinder._is_worktree_first = True  # type: ignore[attr-defined]
    sys.meta_path.insert(0, _WorktreeFirstFinder)
