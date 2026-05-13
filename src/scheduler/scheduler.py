"""WeatherLens — Scheduler (EventBridge equivalent).

Three free alternatives are offered, listed by setup cost:

1. **In-process APScheduler** — `python -m src.scheduler.scheduler`. Keeps
   running in the foreground; runs the pipeline daily at 06:00 local time.
2. **Windows Task Scheduler** — see ``scheduler/weatherlens_daily.xml``
   for an importable definition.
3. **GitHub Actions** — see ``.github/workflows/daily.yml``; free cron for
   public repos.

All three call the same orchestrator: :func:`src.orchestrator.pipeline.run_pipeline`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.monitoring.logger import configure_logging, get_logger
from src.orchestrator.pipeline import run_pipeline

configure_logging("scheduler")
log = get_logger("scheduler")


def daily_job() -> None:
    target = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    log.info(f"scheduler kicking off pipeline for {target}")
    run = run_pipeline(target)
    log.info(f"scheduled run finished status={run.status} metrics={run.metrics}")


def main(hour: int = 6, minute: int = 0) -> None:
    scheduler = BlockingScheduler(timezone="Europe/Bucharest")
    scheduler.add_job(
        daily_job,
        CronTrigger(hour=hour, minute=minute),
        id="weatherlens-daily",
        name="WeatherLens daily ingest+ETL",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    log.info(f"APScheduler started — will run daily at {hour:02d}:{minute:02d} Europe/Bucharest")
    log.info("Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler stopped")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--hour", type=int, default=6)
    parser.add_argument("--minute", type=int, default=0)
    parser.add_argument("--run-now", action="store_true", help="run the daily job once and exit")
    args = parser.parse_args()
    if args.run_now:
        daily_job()
    else:
        main(args.hour, args.minute)
