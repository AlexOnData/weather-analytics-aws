"""Helpers to load and run the SQL files in ``athena_queries/`` against DuckDB."""

from __future__ import annotations

import pandas as pd

from src.catalog.catalog import query
from src.config import PROJECT_ROOT

QUERIES_DIR = PROJECT_ROOT / "athena_queries"


def load_query(name: str) -> str:
    path = QUERIES_DIR / f"{name}.sql"
    if not path.exists():
        raise FileNotFoundError(f"unknown query: {name} (expected {path})")
    return path.read_text(encoding="utf-8")


def list_queries() -> list[str]:
    return sorted(p.stem for p in QUERIES_DIR.glob("*.sql"))


def run_named(name: str, **format_kwargs) -> pd.DataFrame:
    """Run a query by file stem; ``format_kwargs`` substitute ``{placeholder}`` tokens."""
    sql = load_query(name)
    if format_kwargs:
        sql = sql.format(**format_kwargs)
    return query(sql)
