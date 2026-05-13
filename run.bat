@echo off
REM One-command demo: bootstrap data (last 30 days) and launch the dashboard.
setlocal

cd /d "%~dp0"

if not exist "data\catalog\weatherlens.duckdb" (
    echo [run.bat] First run detected — backfilling 30 days of history...
    python -m src.ingest.ingest --start %DATE_START% --end %DATE_END% 2>nul
    python scripts\bootstrap.py
)

echo [run.bat] Launching Streamlit dashboard...
python run_dashboard.py
