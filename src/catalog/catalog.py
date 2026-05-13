"""WeatherLens — DuckDB catalog (Athena + Glue Data Catalog equivalent).

DuckDB can read partitioned Parquet directly with Hive-style partition
detection, so we don't need a separate ``MSCK REPAIR TABLE`` step. We
create persistent views in ``data/catalog/weatherlens.duckdb`` that
point at the Parquet trees produced by the ETL.

Usage::

    >>> from src.catalog.catalog import refresh_catalog, query
    >>> refresh_catalog()
    >>> df = query("SELECT city, COUNT(*) FROM weather_hourly GROUP BY city")
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from src.config import DUCKDB_PATH, PROCESSED_DIR, ensure_dirs
from src.monitoring.logger import configure_logging, get_logger

configure_logging("catalog")
log = get_logger("catalog")

HOURLY_GLOB = (PROCESSED_DIR / "weather_data" / "**" / "*.parquet").as_posix()
DAILY_GLOB = (PROCESSED_DIR / "aggregated" / "daily_summary" / "**" / "*.parquet").as_posix()


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    ensure_dirs()
    return duckdb.connect(str(DUCKDB_PATH), read_only=read_only)


def _has_files(glob_path: str) -> bool:
    """DuckDB throws if the glob matches nothing. Probe first."""
    parent = Path(glob_path.split("**")[0])
    if not parent.exists():
        return False
    return any(parent.rglob("*.parquet"))


def refresh_catalog() -> dict:
    """Recreate the views and return a small status report."""
    con = connect()
    try:
        report: dict = {"weather_hourly": 0, "daily_summary": 0}

        if _has_files(HOURLY_GLOB):
            # DuckDB doesn't support prepared params in DDL — inline the path,
            # quoting it via str.replace to neutralise any single quotes.
            safe_glob = HOURLY_GLOB.replace("'", "''")
            con.execute(
                f"CREATE OR REPLACE VIEW weather_hourly AS "
                f"SELECT * FROM read_parquet('{safe_glob}', hive_partitioning=true)"
            )
            report["weather_hourly"] = con.execute(
                "SELECT COUNT(*) FROM weather_hourly"
            ).fetchone()[0]
            log.info(f"weather_hourly view ready: {report['weather_hourly']} rows")
        else:
            log.warning("no hourly parquet found yet — view not created")

        if _has_files(DAILY_GLOB):
            safe_glob = DAILY_GLOB.replace("'", "''")
            con.execute(
                f"CREATE OR REPLACE VIEW daily_summary AS "
                f"SELECT * FROM read_parquet('{safe_glob}', hive_partitioning=true)"
            )
            report["daily_summary"] = con.execute(
                "SELECT COUNT(*) FROM daily_summary"
            ).fetchone()[0]
            log.info(f"daily_summary view ready: {report['daily_summary']} rows")
        else:
            log.warning("no daily summary parquet found yet — view not created")

        return report
    finally:
        con.close()


def query(sql: str, params: list | tuple | None = None) -> pd.DataFrame:
    """Run an arbitrary SELECT and return a DataFrame."""
    con = connect(read_only=True)
    try:
        if params:
            return con.execute(sql, params).df()
        return con.execute(sql).df()
    finally:
        con.close()


def list_tables() -> list[str]:
    con = connect(read_only=True)
    try:
        rows = con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


if __name__ == "__main__":
    import json

    print(json.dumps(refresh_catalog(), indent=2))
    print("Tables:", list_tables())
