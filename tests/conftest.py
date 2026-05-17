"""Test-wide fixtures.

Now that all parallel agent branches have been integrated into a single
tree, the sys.path bootstrap that was needed for worktree isolation
(see also: conftest.py at repo root) is no longer strictly required —
``pip install -e .`` against this checkout is the canonical install.

Kept here: the manifest-isolation autouse fixture so test runs never
touch the real ``data/manifest.json`` in the repo. Individual tests
that need to assert manifest contents can override
``RENTAL_MANIFEST_PATH`` via ``monkeypatch``.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolate_manifest(tmp_path, monkeypatch):
    """Point manifest writes at a tmpdir for every test."""
    monkeypatch.setenv("RENTAL_MANIFEST_PATH", str(tmp_path / "manifest.json"))
    yield
    os.environ.pop("RENTAL_MANIFEST_PATH", None)
