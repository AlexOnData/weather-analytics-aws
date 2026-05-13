"""Top-level entry point — runs the full WeatherLens pipeline.

Just delegates to :mod:`src.orchestrator.pipeline` so it can be invoked as
``python pipeline.py --date 2026-04-29``.
"""

from src.orchestrator.pipeline import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("src.orchestrator.pipeline", run_name="__main__")
