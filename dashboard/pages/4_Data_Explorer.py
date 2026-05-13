"""WeatherLens — Data Explorer (export-focused). All filters live in the sidebar.

Top control row: granularity dropdown + 3 export buttons, all on the same line.
Below: a grid of average-per-column KPIs (in column order), then the table.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard import _data, _filters  # noqa: E402
from src.config import CITIES  # noqa: E402

CITY_DISPLAY = {k: v["display"] for k, v in CITIES.items()}

# ── KPI metadata: which columns to average + how to label / format ──
# Order here MUST match the order of columns in the table for each
# granularity, so the grid reads top-to-bottom in the same direction
# the user sees the table headers.
KPI_DAILY: list[tuple[str, str, str]] = [
    # (column,                 label,                  format string)
    ("avg_temp",               "Avg Temperatura",      "{:.1f} °C"),
    ("min_temp",               "Avg Temp Minima",      "{:.1f} °C"),
    ("max_temp",               "Avg Temp Maxima",      "{:.1f} °C"),
    ("total_precipitation",    "Avg Precipitatii/zi",  "{:.1f} mm"),
    ("avg_humidity",           "Avg Umiditate",        "{:.0f}%"),
    ("avg_wind_speed",         "Avg Vant",             "{:.1f} km/h"),
    ("max_wind_speed",         "Avg Vant Max",         "{:.1f} km/h"),
    ("avg_cloud_cover",        "Avg Nori",             "{:.0f}%"),
    ("extreme_hours",          "Avg Ore Extreme/zi",   "{:.2f}"),
]

KPI_HOURLY: list[tuple[str, str, str]] = [
    ("temperature_c",          "Avg Temperatura",      "{:.1f} °C"),
    ("feels_like_c",           "Avg Resimtita",        "{:.1f} °C"),
    ("precipitation_mm",       "Avg Ploaie/ora",       "{:.2f} mm"),
    ("wind_speed_kmh",         "Avg Vant",             "{:.1f} km/h"),
    ("humidity_pct",           "Avg Umiditate",        "{:.0f}%"),
    ("pressure_hpa",           "Avg Presiune",         "{:.0f} hPa"),
    ("cloud_cover_pct",        "Avg Nori",             "{:.0f}%"),
    ("is_extreme_event",       "% Ore Extreme",        "{:.1f}%"),
]


def _to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="WeatherLens")
        ws = writer.sheets["WeatherLens"]
        ws.freeze_panes = "A2"
    return buffer.getvalue()


def _render_export_buttons(slots: list, df_view: pd.DataFrame, base_name: str) -> None:
    """Drop the 3 download buttons into the slots provided (sub-columns)."""
    csv_bytes  = df_view.to_csv(index=False).encode("utf-8")
    json_bytes = df_view.to_json(
        orient="records", date_format="iso", force_ascii=False, indent=2
    ).encode("utf-8")
    xlsx_bytes = _to_excel_bytes(df_view)
    with slots[0]:
        st.download_button(
            "📄 CSV",
            data=csv_bytes,
            file_name=f"{base_name}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with slots[1]:
        st.download_button(
            "📊 Excel",
            data=xlsx_bytes,
            file_name=f"{base_name}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with slots[2]:
        st.download_button(
            "🧾 JSON",
            data=json_bytes,
            file_name=f"{base_name}.json",
            mime="application/json",
            use_container_width=True,
        )


def _column_mean(series: pd.Series) -> float | None:
    """Average that handles bool, NaN, and empty-after-dropna correctly."""
    if series.dtype == bool:
        return float(series.mean()) if len(series) else None
    if pd.api.types.is_numeric_dtype(series):
        non_null = series.dropna()
        if non_null.empty:
            return None
        return float(non_null.mean())
    return None


def _render_kpi_grid(df: pd.DataFrame, kpi_specs: list[tuple[str, str, str]]) -> None:
    """Render KPI averages in a 5-column grid; wraps to a second row when needed."""
    PER_ROW = 5

    # Compute values up-front so missing columns gracefully show "—".
    items: list[tuple[str, str]] = []
    for col, label, fmt in kpi_specs:
        if col not in df.columns:
            items.append((label, "—"))
            continue
        mean = _column_mean(df[col])
        if mean is None:
            items.append((label, "—"))
            continue
        # is_extreme_event is a 0/1 bool — mean is the fraction; show as %.
        if col == "is_extreme_event":
            items.append((label, fmt.format(mean * 100)))
        else:
            items.append((label, fmt.format(mean)))

    for start in range(0, len(items), PER_ROW):
        chunk = items[start:start + PER_ROW]
        slots = st.columns(PER_ROW, gap="medium")
        for slot, (label, value) in zip(slots, chunk):
            slot.metric(label, value)
        # Visual breathing room between rows.
        if start + PER_ROW < len(items):
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)


def render() -> None:
    filters = _filters.render()

    st.title("Data Explorer")
    st.caption("Filtreaza din sidebar si exporta rezultatul direct in CSV / Excel / JSON.")

    # ── Top control row: dropdown + 3 export buttons, same line ─────
    controls = st.columns([3, 1, 1, 1], gap="small", vertical_alignment="bottom")

    with controls[0]:
        granularity = st.selectbox(
            "Granularitate",
            ["Rezumat zilnic", "Rezumat orar"],
            key="dx_granularity",
        )
    is_hourly = granularity == "Rezumat orar"

    if is_hourly:
        df = _data.fetch_hourly(filters["cities"], filters["start"], filters["end"])
    else:
        df = _data.fetch_daily(filters["cities"], filters["start"], filters["end"], filters["season"])

    if df.empty:
        st.info("Nu exista randuri pentru filtrele globale curente. Largeste perioada sau adauga orase.")
        return

    df_view = df.copy()
    if "city" in df_view.columns and not df_view.empty:
        insert_at = df_view.columns.get_loc("city") + 1
        df_view.insert(insert_at, "oras", df_view["city"].map(CITY_DISPLAY).fillna(df_view["city"]))
        df_view = df_view.drop(columns=["city"])

    base_name = (
        f"weatherlens_{granularity.lower().replace(' ', '_')}"
        f"_{filters['start']}_{filters['end']}"
    )
    _render_export_buttons(controls[1:], df_view, base_name)

    # ── KPI grid: average per column, in column order ───────────────
    kpi_specs = KPI_HOURLY if is_hourly else KPI_DAILY
    _render_kpi_grid(df, kpi_specs)

    # ── Table ───────────────────────────────────────────────────────
    st.dataframe(df_view, use_container_width=True, hide_index=True, height=780)


render()
