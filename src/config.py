"""WeatherLens — Central configuration.

All paths, city coordinates, schema constants, and tunables live here so
that the ingest / ETL / catalog / dashboard modules stay aligned.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

# Streamlit Community Cloud mounts the repo at /mount/src/<repo>/ which is
# read-only. Redirect everything that writes (raw JSON, parquet, DuckDB,
# logs) to /tmp/weatherlens — the only sandbox path guaranteed writable.
RUNTIME_ROOT: Final[Path] = (
    Path("/tmp/weatherlens")
    if str(PROJECT_ROOT).replace("\\", "/").startswith("/mount/src/")
    else PROJECT_ROOT
)

DATA_DIR: Final[Path] = RUNTIME_ROOT / "data"
RAW_DIR: Final[Path] = DATA_DIR / "raw"
PROCESSED_DIR: Final[Path] = DATA_DIR / "processed"
EXPORTS_DIR: Final[Path] = DATA_DIR / "exports"
CATALOG_DIR: Final[Path] = DATA_DIR / "catalog"
QUERY_RESULTS_DIR: Final[Path] = DATA_DIR / "athena_results"
LOGS_DIR: Final[Path] = RUNTIME_ROOT / "logs"

DUCKDB_PATH: Final[Path] = CATALOG_DIR / "weatherlens.duckdb"

CITIES: Final[dict[str, dict]] = {
    "bucharest": {"lat": 44.43, "lon": 26.10, "country": "Romania", "display": "Bucuresti"},
    "cluj":      {"lat": 46.77, "lon": 23.60, "country": "Romania", "display": "Cluj-Napoca"},
    "constanta": {"lat": 44.18, "lon": 28.65, "country": "Romania", "display": "Constanta"},
    "timisoara": {"lat": 45.75, "lon": 21.23, "country": "Romania", "display": "Timisoara"},
    "brasov":    {"lat": 45.66, "lon": 25.61, "country": "Romania", "display": "Brasov"},
}

HOURLY_VARIABLES: Final[list[str]] = [
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "wind_speed_10m",
    "relative_humidity_2m",
    "pressure_msl",
    "weather_code",
    "cloud_cover",
]

WMO_CODES: Final[dict[int, tuple[str, str]]] = {
    0:  ("Clear sky", "Clear"),
    1:  ("Mainly clear", "Clear"),
    2:  ("Partly cloudy", "Cloudy"),
    3:  ("Overcast", "Cloudy"),
    45: ("Fog", "Fog"),
    48: ("Icy fog", "Fog"),
    51: ("Light drizzle", "Rain"),
    53: ("Moderate drizzle", "Rain"),
    55: ("Dense drizzle", "Rain"),
    61: ("Slight rain", "Rain"),
    63: ("Moderate rain", "Rain"),
    65: ("Heavy rain", "Rain"),
    71: ("Slight snow", "Snow"),
    73: ("Moderate snow", "Snow"),
    75: ("Heavy snow", "Snow"),
    77: ("Snow grains", "Snow"),
    80: ("Slight showers", "Rain"),
    81: ("Moderate showers", "Rain"),
    82: ("Violent showers", "Rain"),
    85: ("Snow showers", "Snow"),
    86: ("Heavy snow showers", "Snow"),
    95: ("Thunderstorm", "Storm"),
    96: ("Thunderstorm + hail", "Storm"),
    99: ("Thunderstorm + heavy hail", "Storm"),
}

VALIDATION_RULES: Final[dict[str, tuple[float, float]]] = {
    "temperature_c":    (-50.0, 55.0),
    "feels_like_c":     (-60.0, 65.0),
    "precipitation_mm": (0.0, 500.0),
    "wind_speed_kmh":   (0.0, 300.0),
    "humidity_pct":     (0, 100),
    "pressure_hpa":     (870.0, 1084.0),
    "cloud_cover_pct":  (0, 100),
}

OPEN_METEO_FORECAST_URL: Final[str] = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL: Final[str] = "https://archive-api.open-meteo.com/v1/archive"
TIMEZONE: Final[str] = "Europe/Bucharest"

PIPELINE_VERSION: Final[str] = "1.0-local"


def ensure_dirs() -> None:
    """Idempotently create every directory the pipeline writes to."""
    for directory in (
        DATA_DIR, RAW_DIR, PROCESSED_DIR, EXPORTS_DIR,
        CATALOG_DIR, QUERY_RESULTS_DIR, LOGS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def raw_key(city: str, date_str: str) -> Path:
    """Return the raw JSON path for a city/date — mirrors the S3 layout."""
    y, m, d = date_str.split("-")
    return RAW_DIR / f"year={y}" / f"month={m}" / f"day={d}" / f"{city}_{y}{m}{d}.json"


def get_season(month: int) -> str:
    if month in (12, 1, 2):
        return "Winter"
    if month in (3, 4, 5):
        return "Spring"
    if month in (6, 7, 8):
        return "Summer"
    return "Autumn"


def wind_category(speed_kmh: float | None) -> str | None:
    if speed_kmh is None:
        return None
    if speed_kmh < 1:
        return "Calm"
    if speed_kmh < 20:
        return "Light"
    if speed_kmh < 40:
        return "Moderate"
    if speed_kmh < 60:
        return "Strong"
    return "Storm"
