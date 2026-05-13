"""Tests for src.catalog — DuckDB views + named queries."""

from __future__ import annotations

import json
from datetime import date


def _seed(tmp_workspace) -> None:
    """Fast-track: write one stub raw file and run ETL so the catalog has data."""
    from src.config import RAW_DIR
    from src.etl import etl

    target = date(2026, 4, 1)
    folder = RAW_DIR / f"year={target.year}" / f"month={target.month:02d}" / f"day={target.day:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    times = [f"{target.isoformat()}T{h:02d}:00" for h in range(24)]
    payload = {
        "latitude": 44.43, "longitude": 26.10, "hourly_units": {},
        "hourly": {
            "time": times,
            "temperature_2m": [12.0] * 24,
            "apparent_temperature": [11.0] * 24,
            "precipitation": [0.0] * 24,
            "wind_speed_10m": [5.0] * 24,
            "relative_humidity_2m": [60] * 24,
            "pressure_msl": [1013.0] * 24,
            "weather_code": [0] * 24,
            "cloud_cover": [10] * 24,
        },
        "_metadata": {"city": "bucharest", "date": target.isoformat()},
    }
    (folder / "bucharest_20260401.json").write_text(json.dumps(payload), encoding="utf-8")
    etl.run_etl([target])


def test_refresh_catalog_creates_views(tmp_workspace):
    _seed(tmp_workspace)
    from src.catalog import catalog

    report = catalog.refresh_catalog()
    assert report["weather_hourly"] == 24
    assert report["daily_summary"] == 1


def test_query_returns_dataframe(tmp_workspace):
    _seed(tmp_workspace)
    from src.catalog import catalog

    catalog.refresh_catalog()
    df = catalog.query("SELECT city, COUNT(*) AS n FROM weather_hourly GROUP BY city")
    assert df.iloc[0]["n"] == 24
    assert df.iloc[0]["city"] == "bucharest"


def test_named_queries_load_and_run(tmp_workspace):
    _seed(tmp_workspace)
    from src.catalog import catalog
    from src.catalog.queries import list_queries, run_named

    catalog.refresh_catalog()
    names = list_queries()
    assert "01_temperature_trend" in names

    df = run_named("05_weather_frequency")
    # Fresh data is sparse; just ensure it ran without exception and returned columns.
    assert {"city", "weather_type", "days_count", "percentage"}.issubset(df.columns)
