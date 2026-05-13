"""WeatherLens — Monthly calendar."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard import _calendar, _data, _filters  # noqa: E402
from src.config import CITIES  # noqa: E402

CITY_DISPLAY = {k: v["display"] for k, v in CITIES.items()}
MONTH_RO = {
    1: "Ianuarie", 2: "Februarie", 3: "Martie", 4: "Aprilie",
    5: "Mai", 6: "Iunie", 7: "Iulie", 8: "August",
    9: "Septembrie", 10: "Octombrie", 11: "Noiembrie", 12: "Decembrie",
}


def render() -> None:
    _filters.render(allow_season=False)

    # ── Row 1 — main title ───────────────────────────────────────
    st.title("Calendar")
    st.caption(
        "Vedere lunara: temperatura medie color-codata, plus umiditate si ploaie per zi."
    )

    months = _data.available_months()
    if not months:
        st.info("Nu exista date inca.")
        return

    # ── Row 2 — month + city dropdowns side by side ──────────────
    sel_cols = st.columns([1, 1], gap="large")
    with sel_cols[0]:
        month_label = st.selectbox(
            "Luna",
            options=[f"{MONTH_RO[m]} {y}" for (y, m) in months],
            index=0,
            key="calendar_month",
        )
        year, month = next((y, m) for (y, m) in months if f"{MONTH_RO[m]} {y}" == month_label)
    with sel_cols[1]:
        city = st.selectbox(
            "Locatie",
            options=list(CITIES.keys()),
            format_func=lambda k: CITY_DISPLAY[k],
            key="calendar_city",
        )

    df = _data.calendar_month(city, year, month)

    # ── Row 3 — KPI strip ────────────────────────────────────────
    if df.empty:
        st.info("Nu exista date pentru luna si orasul selectate.")
        return

    hottest  = df.loc[df["max_temp"].idxmax()]
    coldest  = df.loc[df["min_temp"].idxmin()]
    rainiest = df.loc[df["total_precipitation"].idxmax()]
    windiest = df.loc[df["max_wind_speed"].idxmax()]
    total_rain = float(df["total_precipitation"].sum())
    extreme_count = int((df["extreme_hours"] > 0).sum())
    avg_humidity = float(df["avg_humidity"].mean())
    days_with_data = len(df)

    kpi_cols = st.columns(7, gap="small")
    kpi_cols[0].metric(
        "Cea mai calda",
        f"{hottest['max_temp']:.1f} °C",
        f"pe {hottest['date']:%d %b}",
        help="Cea mai mare temperatura maxima zilnica din luna selectata.",
    )
    kpi_cols[1].metric(
        "Cea mai rece",
        f"{coldest['min_temp']:.1f} °C",
        f"pe {coldest['date']:%d %b}",
        help="Cea mai mica temperatura minima zilnica din luna selectata.",
    )
    kpi_cols[2].metric(
        "Total precipitatii",
        f"{total_rain:.1f} mm",
        f"{days_with_data} zile",
        help="Suma precipitatiilor zilnice din luna selectata.",
    )
    kpi_cols[3].metric(
        "Cea mai ploioasa",
        f"{rainiest['total_precipitation']:.1f} mm",
        f"pe {rainiest['date']:%d %b}",
        help="Ziua cu cele mai multe precipitatii din luna selectata.",
    )
    kpi_cols[4].metric(
        "Vant max",
        f"{windiest['max_wind_speed']:.0f} km/h",
        f"pe {windiest['date']:%d %b}",
        help="Cea mai mare valoare a vantului maxim zilnic (max_wind_speed) din luna selectata.",
    )
    kpi_cols[5].metric(
        "Umiditate medie",
        f"{avg_humidity:.0f}%",
        help="Media umiditatii relative zilnice (avg_humidity) pe luna selectata.",
    )
    kpi_cols[6].metric(
        "Zile extreme",
        f"{extreme_count}",
        help=(
            "Numarul de zile in care cel putin o ora a indeplinit criteriul "
            "de fenomen extrem (temp > 35°C sau < -15°C, precipitatii > 20 mm "
            "sau vant > 80 km/h)."
        ),
    )

    st.divider()

    # ── Row 4 — calendar grid (week# column on left + 7 days) ────
    clicked_date, _ = _calendar.render_calendar(city, year, month, df)
    if clicked_date is not None:
        st.session_state["day_insights_date"] = clicked_date.isoformat()
        st.session_state["day_insights_city"] = city
        try:
            st.switch_page("pages/3_Day_Insights.py")
        except Exception:
            st.success(
                f"Selectata: {clicked_date}. Deschide **Day Insights** "
                "din sidebar pentru detalii complete."
            )

    # ── Row 5 — temperature legend ───────────────────────────────
    _calendar.render_temperature_legend()


render()
