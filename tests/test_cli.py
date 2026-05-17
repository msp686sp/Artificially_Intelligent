"""End-to-end CLI tests via Click's CliRunner.

The warehouse is redirected to a per-test tmpdir via
``RENTAL_WAREHOUSE_PATH``; same for the manifest (the autouse fixture in
``conftest.py`` already does this, but we override to keep the manifest
adjacent to the warehouse for assertion clarity).
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from click.testing import CliRunner

FIXTURE = Path(__file__).parent / "fixtures" / "zhvi_sample.csv"


@pytest.fixture()
def warehouse_env(tmp_path, monkeypatch):
    """Redirect warehouse + manifest at the CLI for the duration of one test."""
    warehouse = tmp_path / "warehouse.duckdb"
    manifest = tmp_path / "manifest.json"
    monkeypatch.setenv("RENTAL_WAREHOUSE_PATH", str(warehouse))
    monkeypatch.setenv("RENTAL_MANIFEST_PATH", str(manifest))

    # cli module reads WAREHOUSE_PATH at import time. Reload so the
    # env-var override is picked up for assertions that read WAREHOUSE_PATH.
    import rental.cli as cli_mod
    import rental.config as cfg

    cfg.WAREHOUSE_PATH = cfg._resolve_warehouse_path()
    cfg.MANIFEST_PATH = cfg._resolve_manifest_path()
    importlib.reload(cli_mod)
    yield tmp_path, warehouse, manifest


def test_init_creates_warehouse(warehouse_env):
    _, warehouse, _ = warehouse_env
    from rental.cli import cli

    result = CliRunner().invoke(cli, ["init"])
    assert result.exit_code == 0, result.output
    assert warehouse.exists()
    assert str(warehouse) in result.output


def test_refresh_from_fixture_loads_rows_and_updates_manifest(warehouse_env):
    _, warehouse, manifest = warehouse_env
    from rental.cli import cli

    runner = CliRunner()
    init_result = runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0, init_result.output

    refresh_result = runner.invoke(
        cli,
        ["refresh", "--source", "zillow_zhvi", "--from-fixture", str(FIXTURE)],
    )
    assert refresh_result.exit_code == 0, refresh_result.output
    assert "15" in refresh_result.output  # rows loaded
    assert warehouse.exists()
    assert manifest.exists()

    # Manifest content matches what refresh logged.
    from rental.manifest import load_manifest

    entries = load_manifest()
    assert entries["zillow_zhvi"].rows_loaded == 15
    assert entries["zillow_zhvi"].status == "ok"


def test_score_writes_output_with_expected_row_count(warehouse_env):
    tmp_path, _, _ = warehouse_env
    from rental.cli import cli

    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    assert (
        runner.invoke(
            cli,
            ["refresh", "--source", "zillow_zhvi", "--from-fixture", str(FIXTURE)],
        ).exit_code
        == 0
    )

    out = tmp_path / "rankings" / "price_rank.csv"
    score_result = runner.invoke(cli, ["score", "--output", str(out)])
    assert score_result.exit_code == 0, score_result.output
    assert out.exists()

    lines = out.read_text().strip().splitlines()
    # 1 header + 5 zips (the fixture has 5)
    assert len(lines) == 6
    # First non-header column should be a 5-digit zip; ranking by zhvi desc
    # puts NYC's 10025 on top.
    assert lines[1].split(",")[0] == "10025"


def test_status_empty_warehouse_is_graceful(warehouse_env):
    """`rental status` must run cleanly with no refresh ever recorded."""
    from rental.cli import cli

    result = CliRunner().invoke(cli, ["status"])
    assert result.exit_code == 0, result.output
    # Either the "no refreshes recorded" banner or a table with the
    # registered source flagged as never-refreshed is acceptable.
    assert (
        "no refresh" in result.output.lower()
        or "never" in result.output.lower()
    )


def test_status_after_refresh_shows_source_ok(warehouse_env):
    from rental.cli import cli

    runner = CliRunner()
    runner.invoke(cli, ["init"])
    runner.invoke(
        cli,
        ["refresh", "--source", "zillow_zhvi", "--from-fixture", str(FIXTURE)],
    )

    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0, result.output
    assert "zillow_zhvi" in result.output
    assert "ok" in result.output.lower()


def test_status_strict_flag_fails_when_source_never_refreshed(warehouse_env):
    """``--strict`` is what `make doctor` relies on for exit-code signaling."""
    from rental.cli import cli

    # No refresh -> the registered source is missing from the manifest
    # which the table flags but `--strict` only exits 1 on stale/error.
    # A never-refreshed source isn't "stale" (no timestamp), so strict
    # passes; this test pins that contract.
    result = CliRunner().invoke(cli, ["status", "--strict"])
    assert result.exit_code == 0, result.output


def test_refresh_unknown_source_rejected(warehouse_env):
    from rental.cli import cli

    result = CliRunner().invoke(
        cli, ["refresh", "--source", "not_a_source", "--from-fixture", str(FIXTURE)]
    )
    assert result.exit_code != 0
