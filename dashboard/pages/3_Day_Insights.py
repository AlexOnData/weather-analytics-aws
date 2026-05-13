"""WeatherLens — Day Insights (per-day drill-down + activity recommendations)."""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard import _charts, _data, _filters, _recommendations  # noqa: E402
from dashboard._calendar import WEATHER_FROM_DESC  # noqa: E402
from src.config import CITIES  # noqa: E402

CITY_DISPLAY = {k: v["display"] for k, v in CITIES.items()}

VERDICT_COLORS = {
    "Excelent":      "#10B981",
    "Bun":           "#3B82F6",
    "Acceptabil":    "#F59E0B",
    "Nu recomandam": "#EF4444",
}


def _parse_session_date(value: str | None, default: date) -> date:
    if not value:
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return default


def _hero_color(temp: float | None) -> str:
    if temp is None:
        return "#1E293B"
    if temp < 0:    return "#1E3A8A"
    if temp < 10:   return "#2563EB"
    if temp < 20:   return "#10B981"
    if temp < 28:   return "#F59E0B"
    return "#EF4444"


def render() -> None:
    filters = _filters.render(allow_season=False)
    min_d, max_d = filters["min_d"], filters["max_d"]

    st.title("Day Insights")
    st.caption("Alege ziua si locatia pentru detalii si recomandari de activitati.")

    default_city = st.session_state.get("day_insights_city") or "bucharest"
    if default_city not in CITIES:
        default_city = "bucharest"
    default_date = _parse_session_date(st.session_state.get("day_insights_date"), max_d)
    default_date = max(min_d, min(max_d, default_date))

    # ── Row 2 — two dropdowns side by side, mirroring Calendar layout ──
    sel_cols = st.columns([1, 1], gap="large")
    with sel_cols[0]:
        day = st.date_input(
            "Ziua",
            value=default_date,
            min_value=min_d, max_value=max_d,
            key="day_insights_date_input",
        )
    with sel_cols[1]:
        city = st.selectbox(
            "Locatie",
            options=list(CITIES.keys()),
            format_func=lambda k: CITY_DISPLAY[k],
            index=list(CITIES.keys()).index(default_city),
            key="day_insights_city_select",
        )

    daily = _data.day_summary(city, day)
    hourly = _data.day_hourly(city, day)

    if daily is None or hourly.empty:
        st.warning(f"Nu exista date pentru {CITY_DISPLAY[city]} in ziua {day}.")
        return

    # ── Row 3 — single-row hero with temp + inline stats ─────────────
    bg = _hero_color(daily["avg_temp"])
    emoji = WEATHER_FROM_DESC.get(daily["dominant_weather"], "•")

    def _safe(value, fmt: str, default: str = "—") -> str:
        if value is None or pd.isna(value):
            return default
        return format(value, fmt)

    feels_avg = hourly["feels_like_c"].mean() if not hourly["feels_like_c"].dropna().empty else None
    avg_temp_str = _safe(daily["avg_temp"], ".1f") + "°C" if pd.notna(daily["avg_temp"]) else "—"
    inline_stats = " · ".join([
        daily["dominant_weather"] or "—",
        f"resimtit {_safe(feels_avg, '.1f')}°",
        f"ploaie {_safe(daily['total_precipitation'], '.1f')} mm",
        f"vant max {_safe(daily['max_wind_speed'], '.0f')} km/h",
        f"umiditate {_safe(daily['avg_humidity'], '.0f')}%",
    ])

    st.markdown(
        f"""<div style='padding:18px 24px; border-radius:12px; background:{bg};
        color:#FFFFFF; display:flex; align-items:center; gap:24px;
        box-shadow:0 4px 12px rgba(0,0,0,.35);'>
        <div style='font-size:56px; line-height:1; flex-shrink:0;'>{emoji}</div>
        <div style='font-size:42px; font-weight:700; line-height:1; flex-shrink:0;
                    white-space:nowrap;'>{avg_temp_str}</div>
        <div style='flex:1; min-width:0; display:flex; flex-direction:column; gap:4px;'>
            <div style='font-size:13px; opacity:0.78; letter-spacing:0.02em;
                        text-transform:uppercase;'>{CITY_DISPLAY[city]} · {day}</div>
            <div style='font-size:14px; opacity:0.92; line-height:1.4;'>{inline_stats}</div>
        </div></div>""",
        unsafe_allow_html=True,
    )

    st.markdown("")

    # ── Hourly chart ─────────────────────────────────────────────
    st.subheader("Evolutie orara")
    st.plotly_chart(_charts.hourly_chart(hourly), use_container_width=True)

    # ── Activity scores ──────────────────────────────────────────
    st.subheader("Recomandari activitati")
    scores = _recommendations.compute_scores(daily, hourly)

    # 2 rows × 3 cols, large gap between cards.
    rows = [scores[i:i + 3] for i in range(0, len(scores), 3)]
    for row_idx, row in enumerate(rows):
        cols = st.columns(len(row), gap="large")
        for col, item in zip(cols, row):
            color = VERDICT_COLORS.get(item["verdict"], "#94A3B8")
            reasons_html = "<br>".join(f"• {r}" for r in item["reasons"])
            col.markdown(
                f"""<div style='padding:18px; border-radius:12px; background:#1E293B;
                border-left:6px solid {color}; min-height:200px;
                box-shadow:0 2px 6px rgba(0,0,0,.3);'>
                <div style='display:flex; justify-content:space-between; align-items:center;'>
                    <div style='font-size:18px;'>{item['icon']} <strong>{item['name']}</strong></div>
                    <div style='font-size:28px; font-weight:700; color:{color};'>{item['score']}</div>
                </div>
                <div style='color:{color}; font-weight:600; margin-top:6px; font-size:13px;'>{item['verdict']}</div>
                <div style='color:#94A3B8; font-size:12px; margin-top:10px; line-height:1.6;'>
                    {reasons_html}
                </div>
                </div>""",
                unsafe_allow_html=True,
            )
        if row_idx < len(rows) - 1:
            st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)


render()
