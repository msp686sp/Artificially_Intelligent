import duckdb
import pandas as pd


def latest_zhvi_per_zip(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Latest observed ZHVI per zip from the most recent snapshot, ranked descending."""
    return con.execute("""
        WITH latest_snapshot AS (
            SELECT MAX(snapshot_date) AS snap FROM raw_zillow_zhvi
        ),
        latest_obs AS (
            SELECT zcta5, MAX(observation_date) AS max_obs
            FROM raw_zillow_zhvi, latest_snapshot
            WHERE snapshot_date = snap
            GROUP BY zcta5
        )
        SELECT z.zcta5, z.state, z.metro, z.county_name,
               z.observation_date, z.zhvi
        FROM raw_zillow_zhvi z
        INNER JOIN latest_obs lo
          ON z.zcta5 = lo.zcta5 AND z.observation_date = lo.max_obs
        INNER JOIN latest_snapshot ls
          ON z.snapshot_date = ls.snap
        ORDER BY z.zhvi DESC
    """).df()
