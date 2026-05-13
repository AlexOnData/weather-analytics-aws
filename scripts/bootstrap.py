"""Bootstrap script: fetch the last N days of weather, run ETL, refresh catalog.

Use this on a fresh checkout so the dashboard has charts to draw immediately.
``python scripts/bootstrap.py --days 30``
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.catalog.catalog import refresh_catalog  # noqa: E402
from src.etl.etl import run_etl  # noqa: E402
from src.ingest.ingest import backfill  # noqa: E402
from src.monitoring.logger import configure_logging, get_logger  # noqa: E402

configure_logging("bootstrap")
log = get_logger("bootstrap")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="how many days back to fetch")
    parser.add_argument("--end", help="end date YYYY-MM-DD (default: yesterday UTC)")
    args = parser.parse_args()

    end = (
        datetime.strptime(args.end, "%Y-%m-%d").date()
        if args.end else (datetime.now(timezone.utc).date() - timedelta(days=1))
    )
    start = end - timedelta(days=args.days - 1)

    log.info(f"backfill window: {start} -> {end} ({args.days} days)")
    ingest_results = backfill(start, end)
    ok = sum(len(r.success) for r in ingest_results)
    failed = sum(len(r.failed) for r in ingest_results)
    log.info(f"ingest finished: ok={ok} failed={failed}")

    log.info("running ETL on every JSON in data/raw")
    etl_report = run_etl(None)
    log.info(f"etl: {etl_report.to_dict()}")

    log.info("refreshing DuckDB catalog")
    catalog_report = refresh_catalog()
    log.info(f"catalog: {catalog_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
