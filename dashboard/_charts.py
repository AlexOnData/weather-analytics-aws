"""Plotly chart factories — one place to keep theme + palette consistent."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.config import CITIES

THEME = "plotly_dark"

CITY_DISPLAY = {k: v["display"] for k, v in CITIES.items()}

# Stable, color-blind friendly palette for the 5 cities.
CITY_COLORS = {
    "bucharest": "#3B82F6",  # blue
    "cluj":      "#10B981",  # green
    "constanta": "#F59E0B",  # amber
    "timisoara": "#EF4444",  # red
    "brasov":    "#A78BFA",  # purple
}

WEATHER_COLORS = {
    "Clear":  "#FBBF24",
    "Cloudy": "#94A3B8",
    "Rain":   "#06B6D4",
    "Snow":   "#E0E7FF",
    "Fog":    "#64748B",
    "Storm":  "#7C3AED",
}


def _layout(fig: go.Figure, title: str | None = None, height: int = 380) -> go.Figure:
    """Apply the standard dark layout. Avoid passing ``title=None`` explicitly —
    Plotly renders a literal ``"undefined"`` placeholder in some versions.
    """
    layout_kwargs = {
        "template": THEME,
        "height": height,
        "margin": dict(l=20, r=20, t=50 if title else 30, b=20),
        "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        "hovermode": "x unified",
    }
    if title:
        layout_kwargs["title"] = title
    fig.update_layout(**layout_kwargs)
    return fig


PLOTLY_CONFIG = {
    "responsive": True,
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "filename": "weatherlens_chart"},
}


def temperature_trend(daily: pd.DataFrame) -> go.Figure:
    """Multi-city daily temperature line chart.

    Hovermode is ``x unified`` so the date appears once at the top of the
    tooltip. Per-trace hovertemplate intentionally omits the date so it
    isn't repeated for every city.
    """
    df = daily.copy().sort_values(["city", "date"])
    fig = go.Figure()
    for city, sub in df.groupby("city"):
        fig.add_trace(go.Scatter(
            x=sub["date"], y=sub["avg_temp"],
            mode="lines+markers",
            name=CITY_DISPLAY.get(city, city),
            line=dict(color=CITY_COLORS.get(city, "#94A3B8"), width=2),
            marker=dict(size=4),
            hovertemplate="<b>%{fullData.name}</b>: %{y:.1f} °C<extra></extra>",
        ))
    fig.update_layout(xaxis_title="Data", yaxis_title="Temperatura (°C)")
    return _layout(fig, height=420)


def precipitation_by_city(precip: pd.DataFrame) -> go.Figure:
    """Single-trace bar chart, sorted descending by total."""
    df = precip.copy()
    df["total_mm"] = df["total_mm"].fillna(0)
    df = df.sort_values("total_mm", ascending=False)
    cities = df["city"].tolist()
    labels = [CITY_DISPLAY.get(c, c) for c in cities]
    colors = [CITY_COLORS.get(c, "#94A3B8") for c in cities]
    text = [f"{v:.0f} mm" for v in df["total_mm"]]

    fig = go.Figure(go.Bar(
        name="Precipitatii",
        x=labels,
        y=df["total_mm"],
        marker_color=colors,
        text=text,
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>%{y:.1f} mm<extra></extra>",
        width=0.6,
    ))
    fig.update_layout(
        xaxis_title=None,
        yaxis_title="Total (mm)",
        showlegend=False,
        bargap=0.3,
    )
    return _layout(fig, height=360)


def avg_temp_by_city(temps: pd.DataFrame) -> go.Figure:
    """Average daily temperature per city, sorted descending."""
    df = temps.copy()
    df["avg_temp"] = df["avg_temp"].fillna(0)
    df = df.sort_values("avg_temp", ascending=False)
    cities = df["city"].tolist()
    labels = [CITY_DISPLAY.get(c, c) for c in cities]
    colors = [CITY_COLORS.get(c, "#94A3B8") for c in cities]
    text = [f"{v:.1f} °C" for v in df["avg_temp"]]

    fig = go.Figure(go.Bar(
        name="Temperatura medie",
        x=labels,
        y=df["avg_temp"],
        marker_color=colors,
        text=text,
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>%{y:.1f} °C<extra></extra>",
        width=0.6,
    ))
    fig.update_layout(
        xaxis_title=None,
        yaxis_title="Temperatura medie (°C)",
        showlegend=False,
        bargap=0.3,
    )
    return _layout(fig, height=360)


WIND_PALETTE = {
    "Calm":     "#CBD5E1",
    "Light":    "#10B981",
    "Moderate": "#3B82F6",
    "Strong":   "#F59E0B",
    "Storm":    "#EF4444",
}
WIND_ORDER = ["Calm", "Light", "Moderate", "Strong", "Storm"]


def wind_donut(share: pd.DataFrame, focus_label: str | None = None) -> go.Figure:
    """Donut over wind categories with total hours in the centre.

    When ``focus_label`` is set, the matching slice is pulled out and the
    centre number reflects only that slice.
    """
    if share.empty:
        return _layout(go.Figure(), height=360)
    df = share.copy()
    # Reorder by intensity (Calm → Storm) for legend readability.
    df["wind_category"] = pd.Categorical(df["wind_category"], categories=WIND_ORDER, ordered=True)
    df = df.dropna(subset=["wind_category"]).sort_values("wind_category")

    colors = [WIND_PALETTE.get(c, "#94A3B8") for c in df["wind_category"]]
    pull = [0.08 if focus_label and str(c) == focus_label else 0 for c in df["wind_category"]]
    line_colors = ["#FFFFFF" if focus_label and str(c) == focus_label else "rgba(0,0,0,0)"
                   for c in df["wind_category"]]
    total = int(df["hours"].sum())

    if focus_label:
        focused = int(df.loc[df["wind_category"].astype(str) == focus_label, "hours"].sum())
        center_main = f"{focused:,}"
        center_sub = f"ore · {focus_label}"
    else:
        center_main = f"{total:,}"
        center_sub = "ore total"

    fig = go.Figure(go.Pie(
        name="Vant",
        labels=df["wind_category"].astype(str),
        values=df["hours"],
        hole=0.62,
        marker=dict(colors=colors, line=dict(color=line_colors, width=2)),
        pull=pull,
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>%{value} ore (%{percent})<extra></extra>",
        sort=False,
    ))
    fig.update_layout(
        showlegend=True,
        hovermode=False,
        annotations=[
            dict(
                text=f"<b style='font-size:30px'>{center_main}</b><br>"
                     f"<span style='font-size:13px; color:#94A3B8'>{center_sub}</span>",
                showarrow=False, x=0.5, y=0.5,
                font=dict(color="#E2E8F0"),
            )
        ],
    )
    return _layout(fig, height=380)


WEATHER_PALETTE = {
    "Clear sky":       "#FBBF24",
    "Mainly clear":    "#FCD34D",
    "Partly cloudy":   "#94A3B8",
    "Overcast":        "#64748B",
    "Fog":             "#475569",
    "Icy fog":         "#475569",
    "Light drizzle":   "#7DD3FC",
    "Moderate drizzle":"#38BDF8",
    "Dense drizzle":   "#0EA5E9",
    "Slight rain":     "#06B6D4",
    "Moderate rain":   "#0891B2",
    "Heavy rain":      "#0E7490",
    "Slight showers":  "#22D3EE",
    "Moderate showers":"#06B6D4",
    "Violent showers": "#0E7490",
    "Slight snow":     "#E0E7FF",
    "Moderate snow":   "#C7D2FE",
    "Heavy snow":      "#A5B4FC",
    "Snow grains":     "#E0E7FF",
    "Snow showers":    "#C7D2FE",
    "Heavy snow showers": "#A5B4FC",
    "Thunderstorm":    "#7C3AED",
    "Thunderstorm + hail": "#5B21B6",
    "Thunderstorm + heavy hail": "#4C1D95",
}


def weather_donut(share: pd.DataFrame, focus_label: str | None = None) -> go.Figure:
    """Donut chart with center annotation. If ``focus_label`` is given, that
    slice is pulled out and the center number reflects only that slice.
    """
    if share.empty:
        return _layout(go.Figure(), height=380)
    df = share.copy().sort_values("days", ascending=False)
    colors = [WEATHER_PALETTE.get(w, "#94A3B8") for w in df["weather"]]
    pull = [0.08 if focus_label and w == focus_label else 0 for w in df["weather"]]
    opacity = [1.0 if (not focus_label or w == focus_label) else 0.35 for w in df["weather"]]
    # Plotly Pie has no per-slice opacity, but ``marker.line`` highlights work.
    line_colors = ["#FFFFFF" if focus_label and w == focus_label else "rgba(0,0,0,0)"
                   for w in df["weather"]]

    total_days = int(df["days"].sum())
    if focus_label:
        focused_days = int(df.loc[df["weather"] == focus_label, "days"].sum())
        center_main = f"{focused_days}"
        center_sub = focus_label
    else:
        center_main = f"{total_days}"
        center_sub = "zile total"

    fig = go.Figure(go.Pie(
        name="Vreme",
        labels=df["weather"],
        values=df["days"],
        hole=0.62,
        marker=dict(colors=colors, line=dict(color=line_colors, width=2)),
        pull=pull,
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>%{value} zile (%{percent})<extra></extra>",
        sort=False,
    ))
    fig.update_layout(
        showlegend=True,
        hovermode=False,
        annotations=[
            dict(
                text=f"<b style='font-size:32px'>{center_main}</b><br>"
                     f"<span style='font-size:13px; color:#94A3B8'>{center_sub}</span>",
                showarrow=False, x=0.5, y=0.5,
                font=dict(color="#E2E8F0"),
            )
        ],
    )
    # ``opacity`` per slice is not a Plotly feature, so we drop it; the
    # line + pull on the focused slice already gives clear emphasis.
    _ = opacity  # retained for clarity if Plotly adds support later
    return _layout(fig, height=380)


def hourly_chart(hourly: pd.DataFrame) -> go.Figure:
    """Two-axis: temp + feels-like as lines, precipitation as bars."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hourly["hour"], y=hourly["temperature_c"],
        mode="lines+markers", name="Temperatura (°C)",
        line=dict(color="#EF4444", width=3),
        hovertemplate="Ora %{x}:00<br>%{y:.1f} °C<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=hourly["hour"], y=hourly["feels_like_c"],
        mode="lines", name="Resimtita (°C)",
        line=dict(color="#F59E0B", width=2, dash="dot"),
        hovertemplate="Ora %{x}:00<br>resimtit %{y:.1f} °C<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=hourly["hour"], y=hourly["precipitation_mm"],
        name="Precipitatii (mm)", yaxis="y2",
        marker_color="#06B6D4", opacity=0.6,
        hovertemplate="Ora %{x}:00<br>%{y:.1f} mm<extra></extra>",
    ))
    fig.update_layout(
        template=THEME,
        height=380,
        xaxis=dict(title="Ora", dtick=2),
        yaxis=dict(title="Temperatura (°C)"),
        yaxis2=dict(title="Precipitatii (mm)", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=40, t=30, b=20),
        hovermode="x unified",
        barmode="overlay",
    )
    return fig
