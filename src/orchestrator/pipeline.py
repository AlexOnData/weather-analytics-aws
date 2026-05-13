"""WeatherLens — Pipeline orchestrator (Step Functions equivalent).

Re-implements the ETL state machine from
``08_STEP_FUNCTIONS_PRESENTATION.md`` as plain Python: typed steps,
exponential-backoff retries, catch/log on failure, and a final summary
that we emit as a CloudWatch-style metrics dict.

::

    Ingest  ─►  Validate  ─►  ETL  ─►  RefreshCatalog  ─►  EmitMetrics
                   │             │           │
                   └─ on fail ───┴───────────┴──►  NotifyFailure (logs + metrics)
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable

from src.catalog.catalog import refresh_catalog
from src.etl.etl import run_etl
from src.ingest.ingest import IngestResult, ingest_date
from src.ingest.validate import validate_date
from src.monitoring.logger import configure_logging, get_logger

configure_logging("orchestrator")
log = get_logger("orchestrator")


@dataclass
class StepResult:
    name: str
    status: str  # "SUCCEEDED" | "FAILED" | "SKIPPED"
    attempts: int
    duration_seconds: float
    output: Any = None
    error: str | None = None


@dataclass
class PipelineRun:
    processing_date: str
    started_at: str
    finished_at: str | None = None
    status: str = "RUNNING"  # SUCCEEDED | FAILED | RUNNING
    steps: list[StepResult] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _retry(label: str, fn: Callable[[], Any], *, attempts: int = 3, base_delay: float = 2.0) -> StepResult:
    """Run ``fn`` with exponential backoff; mirrors the SFN ``Retry`` block."""
    started = time.time()
    last_error: str | None = None
    for attempt in range(1, attempts + 1):
        try:
            output = fn()
            return StepResult(
                name=label, status="SUCCEEDED", attempts=attempt,
                duration_seconds=round(time.time() - started, 2), output=output,
            )
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            log.warning(f"[{label}] attempt {attempt}/{attempts} failed: {last_error}")
            if attempt < attempts:
                delay = base_delay * (2 ** (attempt - 1))
                log.info(f"[{label}] sleeping {delay:.1f}s before retry")
                time.sleep(delay)
    return StepResult(
        name=label, status="FAILED", attempts=attempts,
        duration_seconds=round(time.time() - started, 2), error=last_error,
    )


def run_pipeline(
    target: date,
    cities: Iterable[str] | None = None,
    *,
    skip_ingest: bool = False,
) -> PipelineRun:
    """End-to-end run for a single date.

    Set ``skip_ingest=True`` when JSON already exists locally (e.g. tests
    or a backfill that landed earlier).
    """
    started = datetime.now(timezone.utc).isoformat()
    run = PipelineRun(processing_date=target.isoformat(), started_at=started)

    # ── Step 1: Ingest ──────────────────────────────────────────
    if skip_ingest:
        run.steps.append(StepResult(name="Ingest", status="SKIPPED", attempts=0, duration_seconds=0.0))
    else:
        step = _retry("Ingest", lambda: ingest_date(target, cities))
        if isinstance(step.output, IngestResult):
            step.output = step.output.to_dict()
        run.steps.append(step)
        if step.status == "FAILED":
            return _finalize(run, success=False)

    # ── Step 2: Validate ────────────────────────────────────────
    val_step = _retry("Validate", lambda: validate_date(target, cities))
    if val_step.status == "SUCCEEDED":
        report = val_step.output
        val_step.output = report.to_dict()
        if not report.passed:
            log.error(f"validation failed for all cities: {val_step.output}")
            run.steps.append(val_step)
            return _finalize(run, success=False)
    run.steps.append(val_step)
    if val_step.status == "FAILED":
        return _finalize(run, success=False)

    # ── Step 3: ETL ─────────────────────────────────────────────
    etl_step = _retry("ETL", lambda: run_etl([target]))
    if etl_step.status == "SUCCEEDED":
        etl_step.output = etl_step.output.to_dict()
    run.steps.append(etl_step)
    if etl_step.status == "FAILED":
        return _finalize(run, success=False)

    # ── Step 4: Catalog refresh ────────────────────────────────
    cat_step = _retry("RefreshCatalog", refresh_catalog)
    run.steps.append(cat_step)
    if cat_step.status == "FAILED":
        return _finalize(run, success=False)

    return _finalize(run, success=True)


def _finalize(run: PipelineRun, *, success: bool) -> PipelineRun:
    run.finished_at = datetime.now(timezone.utc).isoformat()
    run.status = "SUCCEEDED" if success else "FAILED"
    duration = sum(s.duration_seconds for s in run.steps)
    run.metrics = {
        "Namespace": "WeatherLens",
        "PipelineSuccess": int(success),
        "PipelineFailures": int(not success),
        "DurationSeconds": round(duration, 2),
        "StepsRun": len(run.steps),
        "StepsFailed": sum(1 for s in run.steps if s.status == "FAILED"),
    }
    log.info(f"pipeline {run.status} for {run.processing_date} in {duration:.1f}s | metrics={run.metrics}")
    return run


def run_backfill(start: date, end: date, cities: Iterable[str] | None = None) -> list[PipelineRun]:
    if start > end:
        raise ValueError("start must be <= end")
    runs: list[PipelineRun] = []
    cur = start
    while cur <= end:
        runs.append(run_pipeline(cur, cities))
        cur += timedelta(days=1)
    return runs


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="WeatherLens pipeline runner")
    parser.add_argument("--date", help="YYYY-MM-DD (default: yesterday UTC)")
    parser.add_argument("--start", help="Backfill start YYYY-MM-DD")
    parser.add_argument("--end", help="Backfill end YYYY-MM-DD")
    parser.add_argument("--cities", nargs="*")
    parser.add_argument("--skip-ingest", action="store_true", help="reuse existing raw files")
    args = parser.parse_args()

    if args.start and args.end:
        s = datetime.strptime(args.start, "%Y-%m-%d").date()
        e = datetime.strptime(args.end, "%Y-%m-%d").date()
        results = run_backfill(s, e, args.cities)
        ok = sum(1 for r in results if r.status == "SUCCEEDED")
        print(json.dumps({"days": len(results), "succeeded": ok, "failed": len(results) - ok}, indent=2))
    else:
        target = (
            datetime.strptime(args.date, "%Y-%m-%d").date()
            if args.date else (datetime.now(timezone.utc).date() - timedelta(days=1))
        )
        result = run_pipeline(target, args.cities, skip_ingest=args.skip_ingest)
        print(json.dumps(result.to_dict(), indent=2, default=str))
