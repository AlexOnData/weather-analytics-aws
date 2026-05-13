"""Tests for src.orchestrator.pipeline — retry, success, and failure handling."""

from __future__ import annotations

from datetime import date


def test_retry_eventually_succeeds(tmp_workspace, monkeypatch):
    from src.orchestrator import pipeline

    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient")
        return {"ok": True}

    result = pipeline._retry("flaky", flaky, attempts=5, base_delay=0.0)
    assert result.status == "SUCCEEDED"
    assert result.attempts == 3
    assert result.output == {"ok": True}


def test_retry_gives_up(tmp_workspace, monkeypatch):
    from src.orchestrator import pipeline
    result = pipeline._retry(
        "always_fails",
        lambda: (_ for _ in ()).throw(ValueError("nope")),
        attempts=2, base_delay=0.0,
    )
    assert result.status == "FAILED"
    assert "nope" in result.error
    assert result.attempts == 2


def test_pipeline_happy_path(tmp_workspace, monkeypatch):
    """End-to-end with mocked Open-Meteo."""
    from unittest.mock import MagicMock
    from src.orchestrator import pipeline

    def fake_get(url, params=None, timeout=None):
        resp = MagicMock()
        target = params["start_date"]
        resp.json.return_value = {
            "latitude": params["latitude"], "longitude": params["longitude"],
            "hourly_units": {},
            "hourly": {
                "time": [f"{target}T{h:02d}:00" for h in range(24)],
                "temperature_2m": [12.0] * 24,
                "apparent_temperature": [11.0] * 24,
                "precipitation": [0.0] * 24,
                "wind_speed_10m": [5.0] * 24,
                "relative_humidity_2m": [60] * 24,
                "pressure_msl": [1013.0] * 24,
                "weather_code": [0] * 24,
                "cloud_cover": [10] * 24,
            },
        }
        resp.raise_for_status = lambda: None
        return resp

    import src.ingest.ingest as ingest_mod
    monkeypatch.setattr(ingest_mod.requests, "get", fake_get)

    run = pipeline.run_pipeline(date(2026, 4, 1))
    assert run.status == "SUCCEEDED"
    statuses = [s.status for s in run.steps]
    assert statuses == ["SUCCEEDED"] * 4
    assert run.metrics["PipelineSuccess"] == 1


def test_pipeline_fails_when_validation_empty(tmp_workspace, monkeypatch):
    """No raw files, skip_ingest=True -> validation fails -> pipeline FAILED."""
    from src.orchestrator import pipeline

    run = pipeline.run_pipeline(date(2026, 4, 1), skip_ingest=True)
    assert run.status == "FAILED"
    assert run.metrics["PipelineFailures"] == 1
