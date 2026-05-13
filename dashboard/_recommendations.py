"""Rule-based activity scoring for Day Insights.

Each activity returns ``(score: int 0-100, verdict: str, reasons: list[str])``.
Thresholds and weights are documented in ``docs/BI_DESIGN.md`` § 9.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

VERDICTS = [
    (80, "Excelent"),
    (60, "Bun"),
    (40, "Acceptabil"),
    (0,  "Nu recomandam"),
]


def _verdict(score: int) -> str:
    for cutoff, label in VERDICTS:
        if score >= cutoff:
            return label
    return "Nu recomandam"


@dataclass
class Activity:
    key: str
    icon: str
    name: str
    rule: Callable[[pd.Series, pd.DataFrame], tuple[int, list[str]]]


def _rng(value: float | None, lo: float, hi: float, points: int, label: str) -> tuple[int, str]:
    """Return (points, message) — full points if value is in [lo, hi]."""
    if value is None or pd.isna(value):
        return 0, f"{label}: lipsa"
    if lo <= value <= hi:
        return points, f"{label}: ideal ({value})"
    return 0, f"{label}: {value} (ideal {lo}-{hi})"


def _lt(value: float | None, threshold: float, points: int, label: str) -> tuple[int, str]:
    if value is None or pd.isna(value):
        return 0, f"{label}: lipsa"
    if value < threshold:
        return points, f"{label}: {value} OK (<{threshold})"
    return 0, f"{label}: {value} prea mare"


def _eq_zero(value: float | None, points: int, label: str) -> tuple[int, str]:
    if value is None or pd.isna(value):
        return 0, f"{label}: lipsa"
    if value == 0:
        return points, f"{label}: zero"
    return 0, f"{label}: {value}"


def _running(daily: pd.Series, hourly: pd.DataFrame) -> tuple[int, list[str]]:
    parts = [
        _rng(daily["avg_temp"], 5, 22, 40, "Temperatura"),
        _lt(daily["total_precipitation"], 2, 30, "Precipitatii"),
        _lt(daily["max_wind_speed"], 30, 20, "Vant max"),
        (10, "Fara fenomene extreme") if daily["extreme_hours"] == 0 else (0, "Fenomene extreme"),
    ]
    return sum(p[0] for p in parts), [p[1] for p in parts]


def _cycling(daily: pd.Series, hourly: pd.DataFrame) -> tuple[int, list[str]]:
    parts = [
        _rng(daily["avg_temp"], 10, 25, 40, "Temperatura"),
        _lt(daily["total_precipitation"], 1, 30, "Precipitatii"),
        _lt(daily["max_wind_speed"], 25, 20, "Vant max"),
        _lt(daily["avg_humidity"], 85, 10, "Umiditate"),
    ]
    return sum(p[0] for p in parts), [p[1] for p in parts]


def _hiking(daily: pd.Series, hourly: pd.DataFrame) -> tuple[int, list[str]]:
    parts = [
        _rng(daily["avg_temp"], 5, 25, 40, "Temperatura"),
        _lt(daily["total_precipitation"], 5, 30, "Precipitatii"),
        _lt(daily["max_wind_speed"], 40, 20, "Vant max"),
        (10, "Fara fenomene extreme") if daily["extreme_hours"] == 0 else (0, "Fenomene extreme"),
    ]
    return sum(p[0] for p in parts), [p[1] for p in parts]


def _picnic(daily: pd.Series, hourly: pd.DataFrame) -> tuple[int, list[str]]:
    parts = [
        _rng(daily["avg_temp"], 18, 28, 40, "Temperatura"),
        _eq_zero(daily["total_precipitation"], 30, "Precipitatii"),
        _lt(daily["max_wind_speed"], 20, 20, "Vant max"),
        _lt(daily["avg_cloud_cover"], 70, 10, "Acoperire nori"),
    ]
    return sum(p[0] for p in parts), [p[1] for p in parts]


def _photography(daily: pd.Series, hourly: pd.DataFrame) -> tuple[int, list[str]]:
    cloud = daily["avg_cloud_cover"]
    cloud_score = 30 if (cloud is not None and not pd.isna(cloud) and 20 <= cloud <= 80) else 0
    cloud_msg = (
        f"Nori: {cloud:.0f}% (ideal 20-80)" if cloud_score
        else f"Nori: {cloud:.0f}% (in afara intervalului)" if (cloud is not None and not pd.isna(cloud))
        else "Nori: lipsa"
    )
    parts = [
        _rng(daily["avg_temp"], -5, 30, 20, "Temperatura"),
        _lt(daily["total_precipitation"], 3, 30, "Precipitatii"),
        (cloud_score, cloud_msg),
        _lt(daily["max_wind_speed"], 50, 20, "Vant max"),
    ]
    return sum(p[0] for p in parts), [p[1] for p in parts]


def _stay_home(daily: pd.Series, hourly: pd.DataFrame) -> tuple[int, list[str]]:
    """High score = staying home is the right call."""
    parts: list[tuple[int, str]] = []
    parts.append((40, "Fenomene extreme prezente") if daily["extreme_hours"] > 0 else (0, "Fara fenomene extreme"))
    parts.append((30, "Ploaie abundenta") if (daily["total_precipitation"] or 0) > 10 else (0, "Ploaie sub prag"))
    parts.append((20, "Vant puternic") if (daily["max_wind_speed"] or 0) > 50 else (0, "Vant moderat"))
    avg_temp = daily["avg_temp"]
    if avg_temp is not None and not pd.isna(avg_temp) and (avg_temp < -5 or avg_temp > 32):
        parts.append((10, f"Temperatura extrema ({avg_temp:.1f})"))
    else:
        parts.append((0, "Temperatura normala"))
    return sum(p[0] for p in parts), [p[1] for p in parts]


ACTIVITIES: list[Activity] = [
    Activity("running",     "🏃", "Alergat",          _running),
    Activity("cycling",     "🚴", "Ciclism",          _cycling),
    Activity("hiking",      "🥾", "Drumetie",         _hiking),
    Activity("picnic",      "🧺", "Picnic",           _picnic),
    Activity("photography", "📸", "Fotografie afara", _photography),
    Activity("stay_home",   "🏠", "Stat in casa",     _stay_home),
]


def compute_scores(daily: pd.Series, hourly: pd.DataFrame) -> list[dict]:
    out = []
    for activity in ACTIVITIES:
        score, reasons = activity.rule(daily, hourly)
        out.append({
            "key": activity.key,
            "icon": activity.icon,
            "name": activity.name,
            "score": int(score),
            "verdict": _verdict(score),
            "reasons": reasons,
        })
    return out
