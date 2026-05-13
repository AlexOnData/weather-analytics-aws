"""WeatherLens — ETL module (Glue PySpark job equivalent).

Reads raw JSON, flattens, validates, derives the analytics columns
listed in ``03_DATA_PIPELINE.md`` / ``04_GLUE_ETL_JOBS.md``, then writes
two Parquet datasets:

  * ``data/processed/weather_data/city=X/year=Y/month=M/data.parquet`` (hourly)
  * ``data/processed/aggregated/daily_summary/city=X/year=Y/month=M/data.parquet``

The hourly dataset is partitioned to mirror the AWS plan; Athena and
DuckDB both pick up partitions from the directory layout.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.config import (
    CITIES,
    PIPELINE_VERSION,
    PROCESSED_DIR,
    RAW_DIR,
    VALIDATION_RULES,
    WMO_CODES,
    ensure_dirs,
    get_season,
    wind_category,
)
from src.monitoring.logger import configure_logging, get_logger

configure_logging("etl")
log = get_logger("etl")

HOURLY_PATH = PROCESSED_DIR / "weather_data"
DAILY_PATH = PROCESSED_DIR / "aggregated" / "daily_summary"


@dataclass
class ETLReport:
    rows_in: int
    rows_out: int
    cities_processed: list[str]
    partitions_written: list[str]
    daily_rows: int

    def to_dict(self) -> dict:
        return self.__dict__


def _iter_raw_files(target_dates: Iterable[date] | None) -> list[Path]:
    """Either every JSON in raw/, or only the files for ``target_dates``."""
    if target_dates is None:
        return sorted(RAW_DIR.rglob("*.json"))
    paths: list[Path] = []
    for d in target_dates:
        y = f"year={d.year}"
        m = f"month={d.month:02d}"
        day = f"day={d.day:02d}"
        directory = RAW_DIR / y / m / day
        if directory.exists():
            paths.extend(sorted(directory.glob("*.json")))
    return paths


def _flatten(payload: dict, city: str) -> list[dict]:
    """Open-Meteo returns parallel arrays; produce one row per hour."""
    info = CITIES.get(city, {})
    hourly = payload.get("hourly", {})
    times = hourly.get("time") or []
    if not times:
        return []

    def col(name: str) -> list:
        return hourly.get(name) or [None] * len(times)

    rows: list[dict] = []
    now = datetime.now(timezone.utc)
    for i, ts_str in enumerate(times):
        try:
            dt = datetime.fromisoformat(ts_str)
        except ValueError:
            continue
        wmo = col("weather_code")[i]
        desc, cat = WMO_CODES.get(int(wmo), ("Unknown", "Unknown")) if wmo is not None else ("Unknown", "Unknown")
        rows.append({
            "timestamp": dt,
            "date": dt.date(),
            "hour": dt.hour,
            "year": dt.year,
            "month": dt.month,
            "day_of_week": dt.strftime("%A"),
            "season": get_season(dt.month),
            "is_daytime": 6 <= dt.hour < 20,
            "city": city,
            "country": info.get("country", "Romania"),
            "latitude": payload.get("latitude") or info.get("lat"),
            "longitude": payload.get("longitude") or info.get("lon"),
            "temperature_c": col("temperature_2m")[i],
            "feels_like_c": col("apparent_temperature")[i],
            "precipitation_mm": col("precipitation")[i],
            "wind_speed_kmh": col("wind_speed_10m")[i],
            "humidity_pct": col("relative_humidity_2m")[i],
            "pressure_hpa": col("pressure_msl")[i],
            "cloud_cover_pct": col("cloud_cover")[i],
            "weather_code": int(wmo) if wmo is not None else None,
            "weather_description": desc,
            "weather_category": cat,
            "ingestion_timestamp": now,
            "pipeline_version": PIPELINE_VERSION,
        })
    return rows


def _validate_ranges(df: pd.DataFrame) -> pd.DataFrame:
    """Null-out values outside the configured ranges instead of dropping rows."""
    for column, (lo, hi) in VALIDATION_RULES.items():
        if column not in df.columns:
            continue
        bad = df[column].notna() & ((df[column] < lo) | (df[column] > hi))
        if bad.any():
            log.warning(f"{column}: {int(bad.sum())} values out of [{lo}, {hi}] -> null")
            df.loc[bad, column] = None
    return df


def _add_derived(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["city", "timestamp"]).reset_index(drop=True)

    # 24h rolling average per city
    df["temp_rolling_avg_24h"] = (
        df.groupby("city", group_keys=False)["temperature_c"]
          .transform(lambda s: s.rolling(window=24, min_periods=1).mean().round(2))
    )

    # Anomaly vs that day's average for the same city
    daily_avg = df.groupby(["city", "date"])["temperature_c"].transform("mean")
    df["temp_anomaly"] = (df["temperature_c"] - daily_avg).round(2)

    # Wind category and extreme-event flag
    df["wind_category"] = df["wind_speed_kmh"].apply(wind_category)
    df["is_extreme_event"] = (
        (df["temperature_c"] > 35)
        | (df["temperature_c"] < -15)
        | (df["precipitation_mm"] > 20)
        | (df["wind_speed_kmh"] > 80)
    ).fillna(False)

    return df


def _write_partitioned(df: pd.DataFrame, root: Path, partitions: list[str]) -> list[str]:
    """Partitioned Parquet write with **one file per date inside each partition**.

    Naming each file ``data_YYYYMMDD.parquet`` means a single-day ETL run
    only touches that day's file and other days in the same month survive
    untouched — matches the idempotent behaviour the AWS plan assumes.
    """
    written: list[str] = []
    if df.empty:
        return written
    if "date" not in df.columns:
        raise ValueError("partitioned writer requires a 'date' column")

    grouped = df.groupby(partitions, dropna=False)
    for keys, sub in grouped:
        if not isinstance(keys, tuple):
            keys = (keys,)
        leaf = root
        for col, val in zip(partitions, keys):
            leaf = leaf / f"{col}={val}"
        leaf.mkdir(parents=True, exist_ok=True)

        for day_value, day_df in sub.groupby("date"):
            day_str = pd.Timestamp(day_value).strftime("%Y%m%d")
            target = leaf / f"data_{day_str}.parquet"
            day_df.drop(columns=partitions).to_parquet(target, index=False, compression="snappy")
            written.append(str(target.relative_to(PROCESSED_DIR.parent)))
    return written


def _build_daily_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    grouped = df.groupby(["city", "date", "year", "month", "season"], as_index=False)
    summary = grouped.agg(
        avg_temp=("temperature_c", "mean"),
        min_temp=("temperature_c", "min"),
        max_temp=("temperature_c", "max"),
        total_precipitation=("precipitation_mm", "sum"),
        avg_humidity=("humidity_pct", "mean"),
        avg_wind_speed=("wind_speed_kmh", "mean"),
        max_wind_speed=("wind_speed_kmh", "max"),
        avg_cloud_cover=("cloud_cover_pct", "mean"),
        extreme_hours=("is_extreme_event", "sum"),
    )
    # Most frequent weather description per city/date.
    dominant = (
        df.dropna(subset=["weather_description"])
          .groupby(["city", "date"])["weather_description"]
          .agg(lambda s: s.mode().iat[0] if not s.mode().empty else None)
          .reset_index(name="dominant_weather")
    )
    summary = summary.merge(dominant, on=["city", "date"], how="left")
    for col in ("avg_temp", "min_temp", "max_temp", "total_precipitation",
                "avg_humidity", "avg_wind_speed", "max_wind_speed", "avg_cloud_cover"):
        summary[col] = summary[col].round(2)
    summary["extreme_hours"] = summary["extreme_hours"].astype(int)
    return summary


def run_etl(target_dates: Iterable[date] | None = None) -> ETLReport:
    ensure_dirs()
    paths = _iter_raw_files(target_dates)
    if not paths:
        log.warning("no raw files matched — nothing to process")
        return ETLReport(0, 0, [], [], 0)

    all_rows: list[dict] = []
    cities_seen: set[str] = set()
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            log.error(f"{path}: invalid JSON ({exc})")
            continue
        city = payload.get("_metadata", {}).get("city") or path.stem.split("_")[0]
        cities_seen.add(city)
        rows = _flatten(payload, city)
        all_rows.extend(rows)
        log.debug(f"flattened {path.name}: +{len(rows)} rows")

    if not all_rows:
        return ETLReport(0, 0, sorted(cities_seen), [], 0)

    df = pd.DataFrame(all_rows)
    rows_in = len(df)

    df = _validate_ranges(df)
    df = _add_derived(df)
    df = df.drop_duplicates(subset=["city", "timestamp"]).reset_index(drop=True)
    rows_out = len(df)
    log.info(f"validated/derived: {rows_in} -> {rows_out} rows ({rows_in - rows_out} dropped)")

    partitions_written = _write_partitioned(df, HOURLY_PATH, ["city", "year", "month"])
    log.info(f"wrote {len(partitions_written)} hourly partitions")

    daily = _build_daily_summary(df)
    daily_partitions = _write_partitioned(daily, DAILY_PATH, ["city", "year", "month"]) if not daily.empty else []
    log.info(f"wrote {len(daily_partitions)} daily-summary partitions ({len(daily)} daily rows)")

    return ETLReport(
        rows_in=rows_in,
        rows_out=rows_out,
        cities_processed=sorted(cities_seen),
        partitions_written=partitions_written + daily_partitions,
        daily_rows=len(daily),
    )


if __name__ == "__main__":
    import argparse
    from datetime import timedelta

    parser = argparse.ArgumentParser(description="WeatherLens ETL")
    parser.add_argument("--date", help="YYYY-MM-DD")
    parser.add_argument("--start", help="Backfill start YYYY-MM-DD")
    parser.add_argument("--end", help="Backfill end YYYY-MM-DD")
    parser.add_argument("--all", action="store_true", help="Process every JSON in data/raw")
    args = parser.parse_args()

    if args.all:
        report = run_etl(None)
    elif args.start and args.end:
        s = datetime.strptime(args.start, "%Y-%m-%d").date()
        e = datetime.strptime(args.end, "%Y-%m-%d").date()
        days = []
        cur = s
        while cur <= e:
            days.append(cur)
            cur += timedelta(days=1)
        report = run_etl(days)
    elif args.date:
        report = run_etl([datetime.strptime(args.date, "%Y-%m-%d").date()])
    else:
        report = run_etl(None)

    print(json.dumps(report.to_dict(), indent=2, default=str))
