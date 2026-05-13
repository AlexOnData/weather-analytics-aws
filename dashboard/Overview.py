"""WeatherLens — Overview (default landing page).

The filename ``Overview.py`` is what Streamlit uses as the sidebar label
for the entry script. Renaming it from ``streamlit_app.py`` was the
cleanest way to get the right caption in the multipage navigation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard import _charts, _data, _filters  # noqa: E402
from src.config import CITIES  # noqa: E402

CITY_DISPLAY = {k: v["display"] for k, v in CITIES.items()}


def _delta_str(delta: float | None, suffix: str = "", precision: int = 1) -> str | None:
    if delta is None:
        return None
    if abs(delta) < 10 ** (-precision):
        return None
    sign = "+" if delta > 0 else ""
    return f"{sign}{delta:.{precision}f}{suffix}"


def _read_chart_focus(state_key: str) -> str | None:
    """Read the label of the slice clicked on a Plotly chart with on_select='rerun'.

    Streamlit stores the chart's interaction state under ``st.session_state[key]``
    as a ``PlotlyState`` (dict-like). For pie/donut clicks the path is
    ``state['selection']['points'][0]['label']``.
    """
    state = st.session_state.get(state_key)
    if not state:
        return None
    sel = state.get("selection") if hasattr(state, "get") else None
    if not sel:
        return None
    pts = sel.get("points") if hasattr(sel, "get") else None
    if not pts:
        return None
    first = pts[0]
    return first.get("label") if hasattr(first, "get") else getattr(first, "label", None)


def _format_top_table(df: pd.DataFrame, value_label: str, unit: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Data", "Oras", value_label, "Vreme"])
    return pd.DataFrame({
        "Data": pd.to_datetime(df["date"]).dt.strftime("%d %b %Y"),
        "Oras": df["city"].map(CITY_DISPLAY).fillna(df["city"]),
        value_label: df["value"].apply(lambda v: f"{v:.1f} {unit}" if pd.notna(v) else "—"),
        "Vreme": df["dominant_weather"].fillna("—"),
    })


def render() -> None:
    filters = _filters.render()
    daily = _data.fetch_daily(filters["cities"], filters["start"], filters["end"], filters["season"])

    st.title("Overview")
    unique_days = int(daily["date"].nunique()) if not daily.empty else 0
    st.caption(
        f"{unique_days} zile · {len(filters['cities'])} orase · "
        f"{filters['start']} → {filters['end']}"
    )

    # ── KPI strip — all 7 on a single row ────────────────────────────
    kpis = _data.overview_kpis(filters["cities"], filters["start"], filters["end"])
    cur, dlt = kpis["current"], kpis["delta"]

    cols = st.columns(7, gap="small")
    cols[0].metric(
        "Temperatura medie",
        f"{cur['avg_temp']:.1f} °C" if cur["avg_temp"] is not None else "—",
        _delta_str(dlt["avg_temp"], " °C"),
        help=(
            "Media aritmetica a temperaturilor zilnice (avg_temp) pentru orasele "
            "si perioada selectate. Delta = comparatie cu o perioada precedenta "
            "de aceeasi durata, exact inainte de start."
        ),
    )
    cols[1].metric(
        "Temperatura resimtita",
        f"{cur['avg_feels_like']:.1f} °C" if cur["avg_feels_like"] is not None else "—",
        _delta_str(dlt["avg_feels_like"], " °C"),
        help=(
            "Media temperaturii resimtite (apparent_temperature) pe toate orele "
            "din perioada si orasele selectate. Tine cont de vant + umiditate."
        ),
    )
    cols[2].metric(
        "Precipitatii (total)",
        f"{cur['total_precip']:.0f} mm" if cur["total_precip"] is not None else "—",
        _delta_str(dlt["total_precip"], " mm", precision=0),
        help=(
            "Suma precipitatiilor zilnice (total_precipitation) pe orasele si "
            "perioada selectate. Delta = comparatie cu perioada precedenta."
        ),
    )
    cols[3].metric(
        "Vant mediu",
        f"{cur['avg_wind']:.1f} km/h" if cur["avg_wind"] is not None else "—",
        _delta_str(dlt["avg_wind"], " km/h"),
        help=(
            "Media zilnica a vitezei vantului (avg_wind_speed) pe orasele si "
            "perioada selectate."
        ),
    )
    cols[4].metric(
        "Umiditate medie",
        f"{cur['avg_humidity']:.0f}%" if cur["avg_humidity"] is not None else "—",
        _delta_str(dlt["avg_humidity"], " p.p.", precision=0),
        help=(
            "Media zilnica a umiditatii relative (avg_humidity) pe orasele si "
            "perioada selectate. Delta exprimata in puncte procentuale."
        ),
    )
    cols[5].metric(
        "Zile fenomene extreme",
        f"{cur['extreme_days']}" if cur["extreme_days"] is not None else "—",
        _delta_str(dlt["extreme_days"], precision=0),
        help=(
            "Numarul de zile in care cel putin o ora a indeplinit criteriul de "
            "fenomen extrem (temperatura > 35°C sau < -15°C, precipitatii > 20 mm "
            "sau vant > 80 km/h)."
        ),
    )
    cols[6].metric(
        "Vreme dominanta",
        cur["dominant_weather"] or "—",
        help=(
            "Cea mai frecventa descriere a vremii (mode) pe perioada si orasele "
            "selectate, calculata din rezumatul zilnic."
        ),
    )

    if daily.empty:
        st.info("Niciun rezultat pentru filtrele selectate.")
        return

    st.divider()

    # ── Big chart: trend ──────────────────────────────────────────
    st.subheader("Evolutie temperatura zilnica")
    st.plotly_chart(
        _charts.temperature_trend(daily),
        use_container_width=True,
        config=_charts.PLOTLY_CONFIG,
    )

    # ── Row A — bars + weather donut ─────────────────────────────
    rowA_left, rowA_right = st.columns(2, gap="large")
    with rowA_left:
        st.subheader("Precipitatii totale per oras")
        precip = _data.precipitation_per_city(filters["cities"], filters["start"], filters["end"])
        if precip.empty or precip["total_mm"].fillna(0).sum() == 0:
            st.caption("Nu s-au inregistrat precipitatii in intervalul selectat.")
        else:
            st.plotly_chart(
                _charts.precipitation_by_city(precip),
                use_container_width=True,
                config=_charts.PLOTLY_CONFIG,
            )
    with rowA_right:
        st.subheader("Distributie tipuri de vreme")
        share = _data.overall_weather_share(filters["cities"], filters["start"], filters["end"])
        if share.empty:
            st.caption("Nu exista date despre vreme dominanta.")
        else:
            focus_label = _read_chart_focus("weather_donut")
            st.plotly_chart(
                _charts.weather_donut(share, focus_label=focus_label),
                use_container_width=True,
                config=_charts.PLOTLY_CONFIG,
                on_select="rerun",
                selection_mode="points",
                key="weather_donut",
            )
            if focus_label:
                if st.button(f"Reseteaza focus: {focus_label}", key="reset_weather_donut"):
                    st.session_state.pop("weather_donut", None)
                    st.rerun()

    # ── Row B — avg temp per city + wind categories donut ────────
    rowB_left, rowB_right = st.columns(2, gap="large")
    with rowB_left:
        st.subheader("Temperatura medie per oras")
        temps = _data.avg_temp_per_city(filters["cities"], filters["start"], filters["end"])
        if temps.empty:
            st.caption("Nu exista date.")
        else:
            st.plotly_chart(
                _charts.avg_temp_by_city(temps),
                use_container_width=True,
                config=_charts.PLOTLY_CONFIG,
            )
    with rowB_right:
        st.subheader("Distributie categorii de vant")
        wind_share = _data.wind_category_share(filters["cities"], filters["start"], filters["end"])
        if wind_share.empty:
            st.caption("Nu exista date pentru categorii de vant.")
        else:
            wind_focus = _read_chart_focus("wind_donut")
            st.plotly_chart(
                _charts.wind_donut(wind_share, focus_label=wind_focus),
                use_container_width=True,
                config=_charts.PLOTLY_CONFIG,
                on_select="rerun",
                selection_mode="points",
                key="wind_donut",
            )
            if wind_focus:
                if st.button(f"Reseteaza focus: {wind_focus}", key="reset_wind_donut"):
                    st.session_state.pop("wind_donut", None)
                    st.rerun()

    st.divider()

    # ── Bottom: top extremes ─────────────────────────────────────
    st.subheader("Top 10 zile extreme")
    t1, t2, t3 = st.columns(3, gap="large")
    hot  = _data.top_extreme_days(filters["cities"], filters["start"], filters["end"], "hot",  limit=10)
    cold = _data.top_extreme_days(filters["cities"], filters["start"], filters["end"], "cold", limit=10)
    rain = _data.top_extreme_days(filters["cities"], filters["start"], filters["end"], "rain", limit=10)
    with t1:
        st.markdown("**Cele mai calde**")
        st.dataframe(_format_top_table(hot, "Max temp", "°C"), use_container_width=True, hide_index=True)
    with t2:
        st.markdown("**Cele mai reci**")
        st.dataframe(_format_top_table(cold, "Min temp", "°C"), use_container_width=True, hide_index=True)
    with t3:
        st.markdown("**Cele mai ploioase**")
        st.dataframe(_format_top_table(rain, "Precipitatii", "mm"), use_container_width=True, hide_index=True)


render()
