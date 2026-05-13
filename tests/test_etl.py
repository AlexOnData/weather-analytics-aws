"""Tests for src.etl — JSON to Parquet transformation + aggregation."""

from __future__ import annotations

import json
from datetime import date


def _write_stub_raw(raw_root, city: str, target: date, *, hours: int = 24, temp_offset: float = 0.0):
    folder = raw_root / f"year={target.year}" / f"month={target.month:02d}" / f"day={target.day:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    times = [f"{target.isoformat()}T{h:02d}:00" for h in range(hours)]
    payload = {
        "latitude": 44.43,
        "longitude": 26.10,
        "hourly_units": {},
        "hourly": {
            "time": times,
            "temperature_2m": [10.0 + h + temp_offset for h in range(hours)],
            "apparent_temperature": [9.0 + h for h in range(hours)],
            "precipitation": [0.0 if h % 6 else 1.5 for h in range(hours)],
            "wind_speed_10m": [5.0 + h * 0.5 for h in range(hours)],
            "relative_humidity_2m": [60 + h % 30 for h in range(hours)],
            "pressure_msl": [1013.0] * hours,
            "weather_code": [0] * hours,
            "cloud_cover": [20] * hours,
        },
        "_metadata": {"city": city, "date": target.isoformat()},
    }
    path = folder / f"{city}_{target.strftime('%Y%m%d')}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_etl_round_trip(tmp_workspace):
    from src.config import RAW_DIR, PROCESSED_DIR
    from src.etl import etl

    target = date(2026, 4, 1)
    for city in ("bucharest", "cluj"):
        _write_stub_raw(RAW_DIR, city, target)

    report = etl.run_etl([target])
    assert report.rows_in == 48
    assert report.rows_out == 48
    assert sorted(report.cities_processed) == ["bucharest", "cluj"]
    assert report.daily_rows == 2

    import pandas as pd
    leaf = PROCESSED_DIR / "weather_data" / "city=bucharest" / "year=2026" / "month=4"
    files = sorted(leaf.glob("data_*.parquet"))
    assert files, f"no parquet written under {leaf}"
    df = pd.read_parquet(files[0])
    assert len(df) == 24
    for col in ["temp_rolling_avg_24h", "temp_anomaly", "wind_category", "is_extreme_event"]:
        assert col in df.columns


def test_etl_validates_out_of_range(tmp_workspace):
    """Out-of-range values get nulled, not dropped."""
    from src.config import RAW_DIR
    from src.etl import etl

    target = date(2026, 4, 5)
    folder = RAW_DIR / f"year={target.year}" / f"month={target.month:02d}" / f"day={target.day:02d}"
    folder.mkdir(parents=True, exist_ok=True)

    times = [f"{target.isoformat()}T{h:02d}:00" for h in range(24)]
    payload = {
        "latitude": 44.43, "longitude": 26.10, "hourly_units": {},
        "hourly": {
            "time": times,
            "temperature_2m": [9999.0] + [10.0] * 23,  # first value is bogus
            "apparent_temperature": [9.0] * 24,
            "precipitation": [0.0] * 24,
            "wind_speed_10m": [5.0] * 24,
            "relative_humidity_2m": [60] * 24,
            "pressure_msl": [1013.0] * 24,
            "weather_code": [0] * 24,
            "cloud_cover": [10] * 24,
        },
        "_metadata": {"city": "bucharest", "date": target.isoformat()},
    }
    (folder / "bucharest_20260405.json").write_text(json.dumps(payload), encoding="utf-8")

    report = etl.run_etl([target])
    assert report.rows_out == 24  # row preserved, bad value nulled

    import pandas as pd
    leaf = tmp_workspace / "data" / "processed" / "weather_data" / "city=bucharest" / "year=2026" / "month=4"
    files = sorted(leaf.glob("data_*.parquet"))
    assert files
    df = pd.read_parquet(files[0])
    sentinel = df.iloc[0]
    assert pd.isna(sentinel["temperature_c"])
