"""Shared pytest fixtures.

Each test that needs to write data uses ``tmp_workspace``, which redirects
every ``src.config`` path constant to ``tmp_path``. The fixture re-imports
the modules that captured those paths at import time so they pick up the
new locations.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture
def tmp_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect every WeatherLens path constant to ``tmp_path``."""
    import src.config as cfg

    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(cfg, "RAW_DIR", tmp_path / "data" / "raw")
    monkeypatch.setattr(cfg, "PROCESSED_DIR", tmp_path / "data" / "processed")
    monkeypatch.setattr(cfg, "EXPORTS_DIR", tmp_path / "data" / "exports")
    monkeypatch.setattr(cfg, "CATALOG_DIR", tmp_path / "data" / "catalog")
    monkeypatch.setattr(cfg, "QUERY_RESULTS_DIR", tmp_path / "data" / "athena_results")
    monkeypatch.setattr(cfg, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(cfg, "DUCKDB_PATH", tmp_path / "data" / "catalog" / "weatherlens.duckdb")

    # Reload the modules that imported those constants directly.
    for name in [
        "src.ingest.ingest",
        "src.ingest.validate",
        "src.ingest.export",
        "src.etl.etl",
        "src.catalog.catalog",
        "src.catalog.queries",
        "src.orchestrator.pipeline",
    ]:
        if name in sys.modules:
            importlib.reload(sys.modules[name])

    return tmp_path
