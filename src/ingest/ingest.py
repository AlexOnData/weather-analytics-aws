"""WeatherLens — Ingestion module (Lambda `weatherlens-ingest` equivalent).

Calls Open-Meteo for the configured cities and writes one JSON file per
city/day to ``data/raw/year=Y/month=M/day=D/<city>_YYYYMMDD.json`` —
the same partitioned layout the AWS S3 plan uses.

The `forecast` endpoint covers ~the last 7 days; older dates fall back
to the `archive` endpoint, which lags by ~5 days. We pick automatically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

import requests

from src.config import (
    CITIES,
    HOURLY_VARIABLES,
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_FORECAST_URL,
    TIMEZONE,
    ensure_dirs,
    raw_key,
)
from src.monitoring.logger import configure_logging, get_logger

configure_logging("ingest")
log = get_logger("ingest")

ARCHIVE_LAG_DAYS = 7  # Anything older than this goes to the archive API.


@dataclass
class IngestResult:
    date: str
    success: list[str] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "success": self.success,
            "failed": self.failed,
        }


def _pick_endpoint(target: date) -> str:
    today = datetime.now(timezone.utc).date()
    if (today - target).days > ARCHIVE_LAG_DAYS:
        return OPEN_METEO_ARCHIVE_URL
    return OPEN_METEO_FORECAST_URL


def fetch_weather(city: str, lat: float, lon: float, target: date, timeout: int = 30) -> dict:
    """Hit Open-Meteo for a single city/date and return the parsed JSON."""
    url = _pick_endpoint(target)
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_VARIABLES),
        "start_date": target.isoformat(),
        "end_date": target.isoformat(),
        "timezone": TIMEZONE,
    }
    log.debug(f"GET {url} params={params}")
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    payload["_metadata"] = {
        "city": city,
        "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
        "date": target.isoformat(),
        "source_url": url,
    }
    return payload


def save_raw(city: str, target: date, payload: dict) -> str:
    """Persist the JSON to its partition path. Returns the absolute path."""
    path = raw_key(city, target.isoformat())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    log.info(f"saved {path.relative_to(path.parents[4])}")
    return str(path)


def ingest_date(target: date, cities: Iterable[str] | None = None) -> IngestResult:
    """Ingest the configured cities for ``target``. Returns a summary."""
    ensure_dirs()
    selected = list(cities) if cities else list(CITIES.keys())
    result = IngestResult(date=target.isoformat())

    for city in selected:
        if city not in CITIES:
            result.failed.append({"city": city, "error": "unknown city"})
            continue
        info = CITIES[city]
        try:
            payload = fetch_weather(city, info["lat"], info["lon"], target)
            save_raw(city, target, payload)
            result.success.append(city)
        except Exception as exc:  # network, JSON, file IO — all surface here
            log.exception(f"ingest failed for {city}")
            result.failed.append({"city": city, "error": str(exc)})

    log.info(f"ingest done date={result.date} ok={result.success} failed={[f['city'] for f in result.failed]}")
    return result


def backfill(start: date, end: date, cities: Iterable[str] | None = None) -> list[IngestResult]:
    """Inclusive backfill from ``start`` to ``end``."""
    if start > end:
        raise ValueError("start must be <= end")
    results: list[IngestResult] = []
    current = start
    while current <= end:
        results.append(ingest_date(current, cities))
        current += timedelta(days=1)
    return results


def parse_date(raw: str) -> date:
    return datetime.strptime(raw, "%Y-%m-%d").date()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest WeatherLens raw data from Open-Meteo")
    parser.add_argument("--date", help="YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--start", help="Backfill start date YYYY-MM-DD")
    parser.add_argument("--end", help="Backfill end date YYYY-MM-DD")
    parser.add_argument("--cities", nargs="*", help="Subset of cities (default: all)")
    args = parser.parse_args()

    if args.start and args.end:
        results = backfill(parse_date(args.start), parse_date(args.end), args.cities)
        ok = sum(len(r.success) for r in results)
        bad = sum(len(r.failed) for r in results)
        print(json.dumps({"days": len(results), "ok": ok, "failed": bad}, indent=2))
    else:
        target = parse_date(args.date) if args.date else (datetime.now(timezone.utc).date() - timedelta(days=1))
        result = ingest_date(target, args.cities)
        print(json.dumps(result.to_dict(), indent=2))
