"""Sidebar filters — global (cities/period/season) + per-page extras."""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from dashboard._data import date_bounds, ensure_catalog
from src.config import CITIES

CITY_DISPLAY = {k: v["display"] for k, v in CITIES.items()}
ALL_CITY_KEYS: tuple[str, ...] = tuple(CITIES.keys())

# session_state key prefixes for the cities popover dropdown
_CITY_PREFIX = "city_chk_"          # one boolean per city
_SELECT_ALL_KEY = "city_select_all"  # the "Select all" master checkbox


# ── Cities popover (PowerBI-style) ──────────────────────────────────

def _init_cities_state() -> None:
    """Initialize per-city checkbox states + the master 'Select all' state."""
    for c in ALL_CITY_KEYS:
        if f"{_CITY_PREFIX}{c}" not in st.session_state:
            st.session_state[f"{_CITY_PREFIX}{c}"] = True
    if _SELECT_ALL_KEY not in st.session_state:
        st.session_state[_SELECT_ALL_KEY] = True


def _on_select_all_change() -> None:
    """When the master checkbox flips, propagate to every city checkbox."""
    new_value = bool(st.session_state[_SELECT_ALL_KEY])
    for c in ALL_CITY_KEYS:
        st.session_state[f"{_CITY_PREFIX}{c}"] = new_value


def _on_city_toggle() -> None:
    """When an individual city is toggled, sync the master 'Select all'."""
    all_on = all(st.session_state[f"{_CITY_PREFIX}{c}"] for c in ALL_CITY_KEYS)
    st.session_state[_SELECT_ALL_KEY] = all_on


def _selected_cities() -> list[str]:
    return [c for c in ALL_CITY_KEYS if st.session_state.get(f"{_CITY_PREFIX}{c}", True)]


def _cities_popover_label(selected: list[str]) -> str:
    """The label shown on the collapsed popover button (PowerBI convention)."""
    n_total = len(ALL_CITY_KEYS)
    n_sel = len(selected)
    if n_sel == n_total:
        return "All"
    if n_sel == 0:
        return "(niciun oras)"
    if n_sel == 1:
        return CITY_DISPLAY[selected[0]]
    return "Multiple selections"


def _render_cities_filter() -> list[str]:
    """Render the dropdown-with-checkboxes filter; returns the selected cities."""
    _init_cities_state()
    selected = _selected_cities()
    label = _cities_popover_label(selected)

    st.sidebar.markdown("**Orase**")
    with st.sidebar.popover(label, use_container_width=True):
        st.checkbox(
            "Select all",
            key=_SELECT_ALL_KEY,
            on_change=_on_select_all_change,
        )
        st.divider()
        for c in ALL_CITY_KEYS:
            st.checkbox(
                CITY_DISPLAY[c],
                key=f"{_CITY_PREFIX}{c}",
                on_change=_on_city_toggle,
            )

    # Read the (possibly updated) state after the widgets rendered.
    return _selected_cities()


# ── Public API ──────────────────────────────────────────────────────

def render(*, allow_season: bool = True, key_prefix: str = "global") -> dict:
    """Render the global sidebar filters and return active values.

    The "WeatherLens" title is rendered by ``dashboard/app.py`` (the
    entry script) so it appears above the auto-generated navigation. We
    only emit the "Filtre globale" caption here.
    """
    ensure_catalog()
    st.sidebar.caption("Filtre globale")

    bounds = date_bounds()
    if bounds is None:
        st.sidebar.error("Nu exista date inca. Ruleaza `python scripts/bootstrap.py`.")
        st.stop()
    min_d, max_d = bounds

    cities = _render_cities_filter()
    if not cities:
        st.sidebar.warning("Selecteaza cel putin un oras.")
        st.stop()

    preset = st.sidebar.selectbox(
        "Perioada",
        options=["Tot intervalul", "Ultimele 7 zile", "Ultimele 30 zile", "Personalizat"],
        index=0,
        key=f"{key_prefix}_period",
    )
    if preset == "Ultimele 7 zile":
        start, end = max(min_d, max_d - timedelta(days=6)), max_d
    elif preset == "Ultimele 30 zile":
        start, end = max(min_d, max_d - timedelta(days=29)), max_d
    elif preset == "Personalizat":
        result = st.sidebar.date_input(
            "De la / Pana la",
            value=(max(min_d, max_d - timedelta(days=29)), max_d),
            min_value=min_d, max_value=max_d,
            key=f"{key_prefix}_custom_range",
        )
        # Streamlit may return a single date while the user is mid-edit.
        if isinstance(result, tuple) and len(result) == 2:
            start, end = result
        else:
            start, end = min_d, max_d
    else:
        start, end = min_d, max_d

    season = "All"
    if allow_season:
        season = st.sidebar.selectbox(
            "Sezon", ["All", "Winter", "Spring", "Summer", "Autumn"],
            key=f"{key_prefix}_season",
        )

    st.sidebar.divider()
    st.sidebar.caption(f"Date disponibile:  \n{min_d} - {max_d}")

    return {
        "cities": tuple(cities),
        "start": start,
        "end": end,
        "season": season,
        "min_d": min_d,
        "max_d": max_d,
    }


