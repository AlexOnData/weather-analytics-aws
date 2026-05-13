"""WeatherLens — multipage entry script.

We use ``st.navigation(position="hidden")`` so the auto nav is suppressed
and we can render the sidebar layout manually:

    [WeatherLens title]
    [Overview / Data Explorer / Calendar / Day Insights] (page_link list)
    [global filters from each page]

Run with::

    streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="WeatherLens",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner="Pregatim datele meteo (prima rulare)...")
def _ensure_data_present() -> str:
    """First-run bootstrap so Streamlit Cloud (or any fresh checkout) has
    something to draw.

    Priority order:
    1. If runtime DATA_DIR already has parquet files → done.
    2. If repo ships seed data under PROJECT_ROOT/data and runtime
       differs (Streamlit Cloud) → copy seed to runtime (~14 MB).
    3. Otherwise → fetch last 30 days from Open-Meteo + ETL + catalog."""
    import shutil

    from src.config import (
        DATA_DIR,
        PROCESSED_DIR,
        PROJECT_ROOT,
        RUNTIME_ROOT,
        ensure_dirs,
    )

    ensure_dirs()
    if PROCESSED_DIR.exists() and any(PROCESSED_DIR.rglob("*.parquet")):
        return "ready"

    seed = PROJECT_ROOT / "data"
    if RUNTIME_ROOT != PROJECT_ROOT and seed.exists() and any(seed.rglob("*.parquet")):
        shutil.copytree(seed, DATA_DIR, dirs_exist_ok=True)
        return "seeded"

    from datetime import datetime, timedelta, timezone

    from src.catalog.catalog import refresh_catalog
    from src.etl.etl import run_etl
    from src.ingest.ingest import backfill

    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=29)
    backfill(start, end)
    run_etl(None)
    refresh_catalog()
    return "bootstrapped"


try:
    _ensure_data_present()
except Exception as exc:  # pragma: no cover — surface the real error in the UI
    import traceback

    st.error(f"Bootstrap data step failed: {type(exc).__name__}: {exc}")
    st.code(traceback.format_exc(), language="text")
    st.stop()

# ── App-wide CSS ────────────────────────────────────────────────────
# 1. Slim sidebar so the main content has room for the calendar grid.
# 2. Stretch the main block-container to the full available width.
# 3. Style buttons that live inside the main area (e.g. the calendar
#    "→ detalii" buttons) so they look fused with the cell above them.
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        min-width: 240px !important;
        max-width: 240px !important;
    }
    section[data-testid="stMain"] .block-container,
    .main .block-container {
        max-width: 100% !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        padding-top: 2rem !important;
    }
    /* Calendar/inline buttons in the main area: integrate visually with
       the cell that sits directly above them. */
    section[data-testid="stMain"] .stButton > button {
        background: rgba(0, 0, 0, 0.28) !important;
        border: 1px solid rgba(255, 255, 255, 0.10) !important;
        border-top: none !important;
        color: rgba(255, 255, 255, 0.88) !important;
        margin-top: 0 !important;
        border-radius: 0 0 10px 10px !important;
        padding: 4px 6px !important;
        height: 30px !important;
        min-height: 30px !important;
        font-size: 11px !important;
        line-height: 1 !important;
        transition: background-color 120ms ease, border-color 120ms ease;
    }
    section[data-testid="stMain"] .stButton > button:hover {
        background: rgba(255, 255, 255, 0.14) !important;
        border-color: rgba(255, 255, 255, 0.30) !important;
        color: #FFFFFF !important;
    }
    /* Restore default look for the export / download / reset buttons.
       These have a stronger visual weight (icon + label) and sit on
       their own, not under a coloured cell. */
    section[data-testid="stMain"] [data-testid="stDownloadButton"] > button,
    section[data-testid="stMain"] [data-testid="stForm"] .stButton > button {
        background: rgba(30, 41, 59, 0.85) !important;
        border: 1px solid rgba(255, 255, 255, 0.18) !important;
        border-radius: 8px !important;
        margin-top: 4px !important;
        height: auto !important;
        min-height: 38px !important;
        padding: 8px 14px !important;
        font-size: 14px !important;
    }
    /* Sidebar multiselect: cap the inner tag area height so adding more
       cities doesn't push the rest of the sidebar down. Tags scroll. */
    [data-testid="stSidebar"] div[data-baseweb="select"] > div:first-child {
        max-height: 96px !important;
        overflow-y: auto !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

PAGES = [
    st.Page("Overview.py",                 title="Overview",       icon=":material/dashboard:", default=True),
    st.Page("pages/2_Calendar.py",         title="Calendar",       icon=":material/calendar_month:"),
    st.Page("pages/3_Day_Insights.py",     title="Day Insights",   icon=":material/insights:"),
    st.Page("pages/4_Data_Explorer.py",    title="Data Explorer",  icon=":material/table_view:"),
]

# ── Sidebar — title + manual nav, then the per-page filters ─────────
with st.sidebar:
    st.markdown(
        """<div style='padding:6px 0 8px 0;'>
        <div style='font-size:24px; font-weight:700; color:#E2E8F0; line-height:1.1;'>
            ☁️ WeatherLens
        </div>
        <div style='font-size:11px; color:#94A3B8; padding-top:4px;'>
            Romanian Weather Analytics
        </div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.divider()
    for page in PAGES:
        st.page_link(page, icon=page.icon)
    st.divider()

# Hidden navigation = routing without a built-in nav UI (we drew our own).
nav = st.navigation(PAGES, position="hidden")
nav.run()
