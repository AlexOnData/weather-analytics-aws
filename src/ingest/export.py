"""WeatherLens — Export module (Lambda `weatherlens-export` equivalent).

Wraps DuckDB queries into CSV / Excel files dropped into ``data/exports/``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src.catalog.queries import run_named
from src.config import EXPORTS_DIR, ensure_dirs
from src.monitoring.logger import configure_logging, get_logger

configure_logging("export")
log = get_logger("export")


def export(query_name: str, fmt: str = "csv", **params) -> Path:
    """Run a named query and persist the result. Returns the file path."""
    ensure_dirs()
    df = run_named(query_name, **params)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = EXPORTS_DIR / datetime.now().strftime("%Y/%m/%d")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"weatherlens_{query_name}_{ts}.{fmt}"

    if fmt == "csv":
        df.to_csv(target, index=False, encoding="utf-8")
    elif fmt in ("xlsx", "excel"):
        target = target.with_suffix(".xlsx")
        with pd.ExcelWriter(target, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Data")
    elif fmt == "json":
        df.to_json(target, orient="records", date_format="iso", force_ascii=False, indent=2)
    else:
        raise ValueError(f"unsupported format: {fmt}")

    log.info(f"exported {len(df)} rows -> {target}")
    return target


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="WeatherLens export")
    parser.add_argument("--query", required=True, help="query name (file in athena_queries/, no .sql)")
    parser.add_argument("--format", default="csv", choices=["csv", "xlsx", "excel", "json"])
    parser.add_argument("--params", nargs="*", default=[], help='key=value pairs (e.g. city=bucharest year=2026)')
    args = parser.parse_args()

    params: dict[str, str] = {}
    for kv in args.params:
        if "=" in kv:
            k, v = kv.split("=", 1)
            params[k] = v
    path = export(args.query, args.format, **params)
    print(path)
