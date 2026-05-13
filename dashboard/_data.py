"""Cached DuckDB queries for the dashboard.

All functions return pandas DataFrames and use ``@st.cache_data`` so the
underlying connection is hit once per filter combination per 5 minutes.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.catalog.catalog import connect, list_tables, refresh_catalog
from src.config import DUCKDB_PATH


# ── Catalog bootstrap ──────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def ensure_catalog() -> dict:
    if not DUCKDB_PATH.exists() or not list_tables():
        return refresh_catalog()
    con = connect(read_only=True)
    try:
        return {
            "weather_hourly": con.execute("SELECT COUNT(*) FROM weather_hourly").fetchone()[0],
            "daily_summary": con.execute("SELECT COUNT(*) FROM daily_summary").fetchone()[0],
        }
    except Exception:
        return refresh_catalog()
    finally:
        con.close()


# ── Bounds & lookups ───────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=300)
def date_bounds() -> tuple[date, date] | None:
    con = connect(read_only=True)
    try:
        row = con.execute("SELECT MIN(date), MAX(date) FROM daily_summary").fetchone()
    except Exception:
        return None
    finally:
        con.close()
    if not row or row[0] is None:
        return None
    return row[0], row[1]


@st.cache_data(show_spinner=False, ttl=300)
def available_months() -> list[tuple[int, int]]:
    """Return distinct (year, month) pairs that have data."""
    con = connect(read_only=True)
    try:
        rows = con.execute(
            "SELECT DISTINCT year, month FROM daily_summary ORDER BY year DESC, month DESC"
        ).fetchall()
    finally:
        con.close()
    return [(int(r[0]), int(r[1])) for r in rows]


# ── Daily-summary fetches ──────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=300)
def fetch_daily(cities: tuple[str, ...], start: date, end: date, season: str = "All") -> pd.DataFrame:
    placeholders = ",".join(["?"] * len(cities))
    season_clause = "AND season = ?" if season != "All" else ""
    sql = f"""
        SELECT date, city, season, avg_temp, min_temp, max_temp,
               total_precipitation, avg_humidity, avg_wind_speed,
               max_wind_speed, avg_cloud_cover, dominant_weather, extreme_hours
        FROM daily_summary
        WHERE city IN ({placeholders})
          AND date BETWEEN ? AND ?
          {season_clause}
        ORDER BY date, city
    """
    params: list = list(cities) + [start, end]
    if season != "All":
        params.append(season)
    con = connect(read_only=True)
    try:
        return con.execute(sql, params).df()
    finally:
        con.close()


@st.cache_data(show_spinner=False, ttl=300)
def fetch_hourly(cities: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
    placeholders = ",".join(["?"] * len(cities))
    sql = f"""
        SELECT timestamp, date, hour, city, season,
               temperature_c, feels_like_c, precipitation_mm,
               wind_speed_kmh, wind_category, humidity_pct,
               pressure_hpa, cloud_cover_pct,
               weather_description, weather_category, is_extreme_event
        FROM weather_hourly
        WHERE city IN ({placeholders})
          AND date BETWEEN ? AND ?
        ORDER BY timestamp
    """
    con = connect(read_only=True)
    try:
        return con.execute(sql, list(cities) + [start, end]).df()
    finally:
        con.close()


# ── Overview-specific aggregates ───────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=300)
def _avg_feels_like(cities: tuple[str, ...], start: date, end: date) -> float | None:
    placeholders = ",".join(["?"] * len(cities))
    sql = (
        f"SELECT AVG(feels_like_c) FROM weather_hourly "
        f"WHERE city IN ({placeholders}) AND date BETWEEN ? AND ?"
    )
    con = connect(read_only=True)
    try:
        row = con.execute(sql, list(cities) + [start, end]).fetchone()
    finally:
        con.close()
    if not row or row[0] is None:
        return None
    return float(row[0])


@st.cache_data(show_spinner=False, ttl=300)
def overview_kpis(cities: tuple[str, ...], start: date, end: date) -> dict:
    """KPI numbers + deltas vs. the previous window of equal length.

    Deltas are returned as ``None`` when the previous window has no data,
    so the UI can suppress meaningless ``+0`` indicators.
    """
    span_days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span_days - 1)

    df_now = fetch_daily(cities, start, end)
    df_prev = fetch_daily(cities, prev_start, prev_end)
    feels_now = _avg_feels_like(cities, start, end)
    feels_prev = _avg_feels_like(cities, prev_start, prev_end)

    def summarize(df: pd.DataFrame, feels: float | None) -> dict:
        if df.empty:
            return {
                "avg_temp": None, "total_precip": None,
                "extreme_days": None, "dominant_weather": "-",
                "avg_feels_like": feels, "avg_wind": None, "avg_humidity": None,
            }
        dominant = (
            df["dominant_weather"].dropna().mode().iat[0]
            if not df["dominant_weather"].dropna().empty else "-"
        )
        return {
            "avg_temp": float(df["avg_temp"].mean()),
            "total_precip": float(df["total_precipitation"].sum()),
            "extreme_days": int((df["extreme_hours"] > 0).sum()),
            "dominant_weather": dominant,
            "avg_feels_like": feels,
            "avg_wind":     float(df["avg_wind_speed"].mean()) if df["avg_wind_speed"].notna().any() else None,
            "avg_humidity": float(df["avg_humidity"].mean())   if df["avg_humidity"].notna().any()   else None,
        }

    now = summarize(df_now, feels_now)
    prev = summarize(df_prev, feels_prev)

    def safe_delta(a, b):
        if a is None or b is None:
            return None
        return a - b

    return {
        "current": now,
        "previous": prev,
        "previous_window": (prev_start, prev_end) if not df_prev.empty else None,
        "delta": {
            "avg_temp":       safe_delta(now["avg_temp"],       prev["avg_temp"]),
            "total_precip":   safe_delta(now["total_precip"],   prev["total_precip"]),
            "extreme_days":   safe_delta(now["extreme_days"],   prev["extreme_days"]),
            "avg_feels_like": safe_delta(now["avg_feels_like"], prev["avg_feels_like"]),
            "avg_wind":       safe_delta(now["avg_wind"],       prev["avg_wind"]),
            "avg_humidity":   safe_delta(now["avg_humidity"],   prev["avg_humidity"]),
        },
    }


@st.cache_data(show_spinner=False, ttl=300)
def overall_weather_share(cities: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
    """Weather distribution aggregated across all selected cities (donut input)."""
    placeholders = ",".join(["?"] * len(cities))
    sql = f"""
        SELECT dominant_weather AS weather, COUNT(*) AS days
        FROM daily_summary
        WHERE city IN ({placeholders}) AND date BETWEEN ? AND ?
          AND dominant_weather IS NOT NULL
        GROUP BY dominant_weather
        ORDER BY days DESC
    """
    con = connect(read_only=True)
    try:
        return con.execute(sql, list(cities) + [start, end]).df()
    finally:
        con.close()


@st.cache_data(show_spinner=False, ttl=300)
def precipitation_per_city(cities: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
    placeholders = ",".join(["?"] * len(cities))
    sql = f"""
        SELECT city, ROUND(SUM(total_precipitation), 1) AS total_mm,
               COUNT(*) FILTER (WHERE total_precipitation > 0) AS rainy_days
        FROM daily_summary
        WHERE city IN ({placeholders}) AND date BETWEEN ? AND ?
        GROUP BY city ORDER BY total_mm DESC NULLS LAST
    """
    con = connect(read_only=True)
    try:
        return con.execute(sql, list(cities) + [start, end]).df()
    finally:
        con.close()


@st.cache_data(show_spinner=False, ttl=300)
def avg_temp_per_city(cities: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
    placeholders = ",".join(["?"] * len(cities))
    sql = f"""
        SELECT city, ROUND(AVG(avg_temp), 2) AS avg_temp
        FROM daily_summary
        WHERE city IN ({placeholders}) AND date BETWEEN ? AND ?
        GROUP BY city ORDER BY avg_temp DESC NULLS LAST
    """
    con = connect(read_only=True)
    try:
        return con.execute(sql, list(cities) + [start, end]).df()
    finally:
        con.close()


@st.cache_data(show_spinner=False, ttl=300)
def wind_category_share(cities: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
    placeholders = ",".join(["?"] * len(cities))
    sql = f"""
        SELECT wind_category, COUNT(*) AS hours
        FROM weather_hourly
        WHERE city IN ({placeholders}) AND date BETWEEN ? AND ?
          AND wind_category IS NOT NULL
        GROUP BY wind_category
    """
    con = connect(read_only=True)
    try:
        return con.execute(sql, list(cities) + [start, end]).df()
    finally:
        con.close()


@st.cache_data(show_spinner=False, ttl=300)
def weather_distribution(cities: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
    placeholders = ",".join(["?"] * len(cities))
    sql = f"""
        SELECT city, dominant_weather AS weather, COUNT(*) AS days
        FROM daily_summary
        WHERE city IN ({placeholders}) AND date BETWEEN ? AND ?
          AND dominant_weather IS NOT NULL
        GROUP BY city, dominant_weather
        ORDER BY city, days DESC
    """
    con = connect(read_only=True)
    try:
        return con.execute(sql, list(cities) + [start, end]).df()
    finally:
        con.close()


@st.cache_data(show_spinner=False, ttl=300)
def wind_polar(cities: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
    placeholders = ",".join(["?"] * len(cities))
    sql = f"""
        SELECT city, wind_category, COUNT(*) AS hours_count,
               ROUND(AVG(wind_speed_kmh), 1) AS avg_wind
        FROM weather_hourly
        WHERE city IN ({placeholders}) AND date BETWEEN ? AND ?
          AND wind_category IS NOT NULL
        GROUP BY city, wind_category
        ORDER BY city, wind_category
    """
    con = connect(read_only=True)
    try:
        return con.execute(sql, list(cities) + [start, end]).df()
    finally:
        con.close()


@st.cache_data(show_spinner=False, ttl=300)
def top_extreme_days(
    cities: tuple[str, ...], start: date, end: date,
    kind: str = "hot", limit: int = 10,
) -> pd.DataFrame:
    placeholders = ",".join(["?"] * len(cities))
    if kind == "hot":
        order_col, label = "max_temp DESC NULLS LAST", "max_temp"
    elif kind == "cold":
        order_col, label = "min_temp ASC NULLS LAST", "min_temp"
    else:
        order_col, label = "total_precipitation DESC NULLS LAST", "total_precipitation"
    sql = f"""
        SELECT date, city, ROUND({label}, 1) AS value, dominant_weather
        FROM daily_summary
        WHERE city IN ({placeholders}) AND date BETWEEN ? AND ?
        ORDER BY {order_col}
        LIMIT {int(limit)}
    """
    con = connect(read_only=True)
    try:
        return con.execute(sql, list(cities) + [start, end]).df()
    finally:
        con.close()


# ── Calendar & day detail ──────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=300)
def calendar_month(city: str, year: int, month: int) -> pd.DataFrame:
    sql = """
        SELECT date, avg_temp, min_temp, max_temp,
               (SELECT ROUND(AVG(feels_like_c), 1) FROM weather_hourly h
                WHERE h.city = d.city AND h.date = d.date) AS feels_like,
               total_precipitation,
               avg_humidity, avg_wind_speed, max_wind_speed,
               dominant_weather, extreme_hours
        FROM daily_summary d
        WHERE city = ? AND year = ? AND month = ?
        ORDER BY date
    """
    con = connect(read_only=True)
    try:
        return con.execute(sql, [city, year, month]).df()
    finally:
        con.close()


@st.cache_data(show_spinner=False, ttl=300)
def day_summary(city: str, day: date) -> pd.Series | None:
    sql = """
        SELECT date, city, avg_temp, min_temp, max_temp, total_precipitation,
               avg_humidity, avg_wind_speed, max_wind_speed, avg_cloud_cover,
               dominant_weather, extreme_hours
        FROM daily_summary WHERE city = ? AND date = ?
    """
    con = connect(read_only=True)
    try:
        df = con.execute(sql, [city, day]).df()
    finally:
        con.close()
    if df.empty:
        return None
    return df.iloc[0]


@st.cache_data(show_spinner=False, ttl=300)
def day_hourly(city: str, day: date) -> pd.DataFrame:
    sql = """
        SELECT timestamp, hour, temperature_c, feels_like_c,
               precipitation_mm, wind_speed_kmh, humidity_pct,
               weather_description, weather_category
        FROM weather_hourly
        WHERE city = ? AND date = ?
        ORDER BY hour
    """
    con = connect(read_only=True)
    try:
        return con.execute(sql, [city, day]).df()
    finally:
        con.close()
