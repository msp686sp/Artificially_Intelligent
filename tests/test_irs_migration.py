from pathlib import Path

import duckdb

from rental.db import init_schema
from rental.sources import IRSMigrationSource

FIXTURE = Path(__file__).parent / "fixtures" / "irs_migration_sample.csv"


def _con():
    con = duckdb.connect(":memory:")
    init_schema(con)
    return con


def test_irs_migration_load_shape():
    con = _con()
    rows = IRSMigrationSource().load(con, FIXTURE)
    assert rows == 30  # all fixture rows loaded
    n = con.execute("SELECT count(*) FROM raw_irs_migration").fetchone()[0]
    assert n == 30


def test_irs_migration_fips_padded_to_5_chars():
    con = _con()
    IRSMigrationSource().load(con, FIXTURE)
    fips = con.execute(
        "SELECT DISTINCT origin_fips FROM raw_irs_migration "
        "UNION SELECT DISTINCT dest_fips FROM raw_irs_migration"
    ).fetchall()
    assert all(len(f[0]) == 5 for f in fips)


def test_irs_inflow_origin_dest_orientation():
    """Inflow rows: origin is where filers came FROM, dest is the county itself."""
    con = _con()
    IRSMigrationSource().load(con, FIXTURE)
    # Cook County inflow from Marion County: origin should be 18097, dest 17031.
    rows = con.execute(
        """
        SELECT origin_fips, dest_fips, returns
        FROM raw_irs_migration
        WHERE flow_direction = 'inflow'
          AND origin_fips = '18097' AND dest_fips = '17031'
        """
    ).fetchall()
    assert rows == [("18097", "17031", 1850)]


def test_irs_outflow_origin_dest_orientation():
    """Outflow rows: origin is the home county, dest is where filers went."""
    con = _con()
    IRSMigrationSource().load(con, FIXTURE)
    rows = con.execute(
        """
        SELECT origin_fips, dest_fips, returns
        FROM raw_irs_migration
        WHERE flow_direction = 'outflow'
          AND origin_fips = '17031' AND dest_fips = '18097'
        """
    ).fetchall()
    assert rows == [("17031", "18097", 2200)]


def test_irs_refresh_from_fixture_logs_success():
    con = _con()
    result = IRSMigrationSource().refresh(
        con, raw_dir=Path("/tmp/_unused"), from_fixture=FIXTURE
    )
    assert result.status == "ok"
    assert result.rows_loaded == 30
    log = con.execute(
        "SELECT source, rows_loaded, status FROM refresh_log"
    ).fetchall()
    assert log == [("irs_migration", 30, "ok")]
