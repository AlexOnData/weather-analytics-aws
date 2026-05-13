"""WeatherLens — Validation step (Lambda `weatherlens-validate` equivalent).

Re-reads the raw JSON files for a date and confirms each one has the
required schema and a sane number of hourly records, before the ETL runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable

from src.config import CITIES, raw_key
from src.monitoring.logger import configure_logging, get_logger

configure_logging("validate")
log = get_logger("validate")

REQUIRED_TOP = ("latitude", "longitude", "hourly", "hourly_units")
REQUIRED_HOURLY = ("time", "temperature_2m", "precipitation", "wind_speed_10m")
MIN_RECORDS = 20  # Open-Meteo returns 24/day; allow a couple of nulls.


@dataclass
class CityValidation:
    city: str
    valid: bool
    errors: list[str] = field(default_factory=list)
    records: int = 0


@dataclass
class ValidationReport:
    date: str
    results: list[CityValidation]

    @property
    def valid_cities(self) -> list[str]:
        return [r.city for r in self.results if r.valid]

    @property
    def passed(self) -> bool:
        return bool(self.valid_cities)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "passed": self.passed,
            "valid_cities": self.valid_cities,
            "results": [r.__dict__ for r in self.results],
        }


def _validate_file(path: Path) -> tuple[list[str], int]:
    if not path.exists():
        return [f"file not found: {path}"], 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"], 0

    errors: list[str] = []
    for field_name in REQUIRED_TOP:
        if field_name not in data:
            errors.append(f"missing top-level field: {field_name}")

    records = 0
    if "hourly" in data:
        for field_name in REQUIRED_HOURLY:
            if field_name not in data["hourly"]:
                errors.append(f"missing hourly field: {field_name}")
        records = len(data["hourly"].get("time", []))
        if records < MIN_RECORDS:
            errors.append(f"too few records: {records} < {MIN_RECORDS}")

    return errors, records


def validate_date(target: date, cities: Iterable[str] | None = None) -> ValidationReport:
    selected = list(cities) if cities else list(CITIES.keys())
    results = []
    for city in selected:
        path = raw_key(city, target.isoformat())
        errors, records = _validate_file(path)
        results.append(CityValidation(city=city, valid=not errors, errors=errors, records=records))
        log.info(f"validate {city}: valid={not errors} records={records} errors={errors}")
    return ValidationReport(date=target.isoformat(), results=results)


if __name__ == "__main__":
    import argparse
    from datetime import datetime, timedelta, timezone

    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD (default: yesterday)")
    args = parser.parse_args()
    target = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date else (datetime.now(timezone.utc).date() - timedelta(days=1))
    )
    report = validate_date(target)
    print(json.dumps(report.to_dict(), indent=2))
