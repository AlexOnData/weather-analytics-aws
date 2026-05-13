"""Monthly calendar grid renderer for page 3."""

from __future__ import annotations

import calendar
from datetime import date

import pandas as pd
import streamlit as st

WEATHER_FROM_DESC = {
    "Clear sky": "☀️", "Mainly clear": "🌤️", "Partly cloudy": "⛅", "Overcast": "☁️",
    "Fog": "🌫️", "Icy fog": "🌫️",
    "Light drizzle": "🌦️", "Moderate drizzle": "🌧️", "Dense drizzle": "🌧️",
    "Slight rain": "🌧️", "Moderate rain": "🌧️", "Heavy rain": "🌧️",
    "Slight showers": "🌦️", "Moderate showers": "🌧️", "Violent showers": "⛈️",
    "Slight snow": "🌨️", "Moderate snow": "❄️", "Heavy snow": "❄️", "Snow grains": "🌨️",
    "Snow showers": "🌨️", "Heavy snow showers": "❄️",
    "Thunderstorm": "⛈️", "Thunderstorm + hail": "⛈️", "Thunderstorm + heavy hail": "⛈️",
}

# (upper-bound exclusive, color, label)
TEMP_BANDS = [
    (-5,  "#1E3A8A", "< -5"),
    (5,   "#1D4ED8", "-5 → 5"),
    (12,  "#0EA5E9", "5 → 12"),
    (20,  "#10B981", "12 → 20"),
    (26,  "#F59E0B", "20 → 26"),
    (1e9, "#EF4444", "> 26"),
]


def _temp_color(temp: float | None) -> str:
    if temp is None or pd.isna(temp):
        return "#1E293B"
    for upper, color, _ in TEMP_BANDS:
        if temp < upper:
            return color
    return "#1E293B"


def _fmt(value, suffix: str = "", precision: int = 0, default: str = "—") -> str:
    if value is None or pd.isna(value):
        return default
    return f"{value:.{precision}f}{suffix}"


def _empty_cell(day_num: int) -> str:
    return (
        "<div style='height:128px; padding:10px 12px; border:1px dashed #334155;"
        " border-radius:10px 10px 0 0; background:#0F172A; color:#475569;'>"
        f"<div style='font-size:15px; font-weight:600;'>{day_num}</div>"
        "<div style='font-size:12px; margin-top:8px;'>fara date</div>"
        "</div>"
    )


def _stat_row(emoji: str, label: str, value: str) -> str:
    """One row of the stacked stat list — emoji | label | value, aligned."""
    return (
        "<div style='display:flex; align-items:center; gap:8px; font-size:13px;"
        " line-height:1.45; white-space:nowrap;'>"
        f"<span style='width:16px; flex-shrink:0;'>{emoji}</span>"
        f"<span style='flex:1; opacity:0.92; overflow:hidden; text-overflow:ellipsis;'>{label}</span>"
        f"<span style='font-weight:600; flex-shrink:0;'>{value}</span>"
        "</div>"
    )


def _filled_cell(day_num: int, row: pd.Series) -> str:
    avg_temp = row.get("avg_temp")
    feels = row.get("feels_like")
    precip = row.get("total_precipitation")
    humidity = row.get("avg_humidity")
    extreme_hours = row.get("extreme_hours") or 0
    desc = row.get("dominant_weather") or ""
    emoji = WEATHER_FROM_DESC.get(desc, "•")
    bg = _temp_color(avg_temp)
    extreme_badge = (
        "<span style='background:rgba(127,29,29,0.85); color:#FECACA; font-size:9px;"
        " padding:2px 5px; border-radius:5px; margin-left:5px; vertical-align:middle;'>"
        "extrem</span>"
        if extreme_hours > 0 else ""
    )
    big_temp = _fmt(avg_temp, "°", precision=0)

    return (
        f"<div style='height:128px; padding:10px 12px; border-radius:10px 10px 0 0;"
        f" background:{bg}; color:#FFFFFF; line-height:1.2;'>"
        # Header row: day# left · temp+emoji right
        f"<div style='display:flex; justify-content:space-between; align-items:flex-start;"
        f" margin-bottom:6px; gap:8px; white-space:nowrap;'>"
        f"<span style='font-size:15px; font-weight:700;'>{day_num}{extreme_badge}</span>"
        f"<span style='font-size:22px; font-weight:700; line-height:1; white-space:nowrap;'>"
        f"{big_temp}<span style='font-size:18px; margin-left:5px;'>{emoji}</span></span>"
        f"</div>"
        # Stacked stats — emoji | label | value, all aligned
        f"<div style='display:flex; flex-direction:column; gap:2px;'>"
        + _stat_row("🌡️", "Resimtit",  _fmt(feels,    "°",     precision=0))
        + _stat_row("💧", "Umiditate", _fmt(humidity, "%",     precision=0))
        + _stat_row("🌧️", "Ploaie",    _fmt(precip,   " mm",   precision=1))
        + "</div>"
        + "</div>"
    )


def render_calendar(
    city: str, year: int, month: int, df: pd.DataFrame
) -> tuple[date | None, str | None]:
    """Render the calendar grid with a week-number column on the left.

    Returns ``(clicked_date, clicked_city)`` when the user clicks a day;
    ``(None, None)`` otherwise.
    """
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)

    by_day: dict[int, pd.Series] = {}
    if not df.empty:
        for _, row in df.iterrows():
            d = row["date"]
            if hasattr(d, "day"):
                by_day[d.day] = row

    weekdays = ["Luni", "Marti", "Miercuri", "Joi", "Vineri", "Sambata", "Duminica"]
    column_widths = [0.5] + [1.0] * 7

    header_cols = st.columns(column_widths, gap="small")
    header_cols[0].markdown(
        "<div style='text-align:center; color:#64748B; font-size:11px;"
        " padding-bottom:4px;'>Sapt.</div>",
        unsafe_allow_html=True,
    )
    for col, label in zip(header_cols[1:], weekdays):
        col.markdown(
            f"<div style='text-align:center; color:#94A3B8; font-weight:600;"
            f" font-size:12px; padding-bottom:4px; letter-spacing:0.05em;"
            f" text-transform:uppercase;'>{label}</div>",
            unsafe_allow_html=True,
        )

    clicked_date: date | None = None
    for week in weeks:
        cols = st.columns(column_widths, gap="small")
        # Week number on the left, derived from the first non-zero day.
        first_day = next((d for d in week if d > 0), None)
        if first_day:
            iso_week = date(year, month, first_day).isocalendar().week
            cols[0].markdown(
                f"<div style='display:flex; align-items:center; justify-content:center;"
                f" height:160px; color:#94A3B8; font-weight:600; font-size:15px;'>"
                f"{iso_week}</div>",
                unsafe_allow_html=True,
            )
        else:
            cols[0].markdown("<div style='height:160px'></div>", unsafe_allow_html=True)

        for col, day_num in zip(cols[1:], week):
            if day_num == 0:
                col.markdown("<div style='height:160px'></div>", unsafe_allow_html=True)
                continue
            row = by_day.get(day_num)
            if row is None:
                col.markdown(_empty_cell(day_num), unsafe_allow_html=True)
                continue
            col.markdown(_filled_cell(day_num, row), unsafe_allow_html=True)
            if col.button(
                "Vezi Detalii",
                key=f"day_{year}_{month}_{day_num}",
                use_container_width=True,
                type="secondary",
            ):
                clicked_date = date(year, month, day_num)

    return clicked_date, city if clicked_date else None


def render_temperature_legend() -> None:
    """Inline color legend matching ``_temp_color`` bands."""
    pieces = []
    for upper, color, label in TEMP_BANDS:
        pieces.append(
            "<div style='display:flex; align-items:center; gap:6px;'>"
            f"<span style='display:inline-block; width:22px; height:14px;"
            f" background:{color}; border-radius:3px; border:1px solid rgba(255,255,255,0.08);'></span>"
            f"<span style='font-size:12px; color:#94A3B8;'>{label} °C</span>"
            "</div>"
        )
    legend_html = (
        "<div style='display:flex; flex-wrap:wrap; gap:18px; padding:16px 4px;"
        " border-top:1px solid #1E293B; margin-top:8px;"
        " justify-content:center; align-items:center;'>"
        "<span style='font-size:12px; color:#64748B;'>"
        "Legenda culori (temperatura medie zilnica):</span>"
        + "".join(pieces) + "</div>"
    )
    st.markdown(legend_html, unsafe_allow_html=True)
