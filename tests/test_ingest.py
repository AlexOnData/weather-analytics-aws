"""Tests for src.ingest — the Open-Meteo ingestion."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock


def _stub_payload(city: str, target: date) -> dict:
    times = [f"{target.isoformat()}T{h:02d}:00" for h in range(24)]
    return {
        "latitude": 44.43,
        "longitude": 26.10,
        "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
        "hourly": {
            "time": times,
            "temperature_2m": [10.0 + h for h in range(24)],
            "apparent_temperature": [9.0 + h for h in range(24)],
            "precipitation": [0.0] * 24,
            "wind_speed_10m": [5.0] * 24,
            "relative_humidity_2m": [60] * 24,
            "pressure_msl": [1013.0] * 24,
            "weather_code": [0] * 24,
            "cloud_cover": [10] * 24,
        },
    }


def test_ingest_single_day_writes_one_file_per_city(tmp_workspace, monkeypatch):
    from src.ingest import ingest as ingest_mod

    target = date(2026, 4, 1)

    def fake_get(url, params=None, timeout=None):
        resp = MagicMock()
        resp.json.return_value = _stub_payload(params["latitude"], target)
        resp.raise_for_status = lambda: None
        return resp

    monkeypatch.setattr(ingest_mod.requests, "get", fake_get)

    result = ingest_mod.ingest_date(target)
    expected_cities = sorted(ingest_mod.CITIES.keys())
    assert sorted(result.success) == expected_cities
    assert result.failed == []

    raw_dir = tmp_workspace / "data" / "raw" / "year=2026" / "month=04" / "day=01"
    files = sorted(p.name for p in raw_dir.glob("*.json"))
    assert files == sorted(f"{c}_20260401.json" for c in expected_cities)

    payload = json.loads((raw_dir / "bucharest_20260401.json").read_text(encoding="utf-8"))
    assert "_metadata" in payload
    assert payload["_metadata"]["city"] == "bucharest"
    assert payload["_metadata"]["date"] == "2026-04-01"
    assert len(payload["hourly"]["time"]) == 24


def test_ingest_collects_failures(tmp_workspace, monkeypatch):
    from src.ingest import ingest as ingest_mod

    target = date(2026, 4, 2)
    call_counter = {"n": 0}

    def fake_get(url, params=None, timeout=None):
        call_counter["n"] += 1
        if call_counter["n"] == 2:
            raise ConnectionError("simulated outage")
        resp = MagicMock()
        resp.json.return_value = _stub_payload("x", target)
        resp.raise_for_status = lambda: None
        return resp

    monkeypatch.setattr(ingest_mod.requests, "get", fake_get)
    result = ingest_mod.ingest_date(target)
    expected_total = len(ingest_mod.CITIES)
    assert len(result.success) == expected_total - 1
    assert len(result.failed) == 1
    assert "simulated outage" in result.failed[0]["error"]


def test_unknown_city_is_reported(tmp_workspace):
    from src.ingest import ingest as ingest_mod
    result = ingest_mod.ingest_date(date(2026, 4, 3), cities=["atlantis"])
    assert result.success == []
    assert result.failed[0]["city"] == "atlantis"
