---
sdk: docker
app_port: 7860
license: mit
---

# WeatherLens — Romanian Weather Analytics ($0 Local Stack)

> **Live demo:** **<https://AlexOnData-weather-analytics-aws.hf.space>** *(Hugging Face Spaces · Docker · free tier)*

End-to-end weather analytics platform that pulls hourly data from
[Open-Meteo](https://open-meteo.com) for **five Romanian cities**
(Bucuresti, Cluj-Napoca, Constanta, Timisoara, Brasov), runs an ETL
pipeline, catalogs the result in DuckDB, and serves an interactive
**4-page Streamlit dashboard** (Overview · Calendar · Day Insights ·
Data Explorer) with charts, drill-downs, activity recommendations and
CSV / Excel / JSON export.

The project was originally designed as a full **AWS deployment**
(S3 + Lambda + Glue + Athena + Step Functions + QuickSight) and was
later pivoted to a **100% local, free stack** so it costs **$0** to run.
The AWS architecture is preserved as the academic backbone and is
explained in the accompanying presentation
([`WeatherLens_Prezentare.pptx`](WeatherLens_Prezentare.pptx), 18 slides).

The dashboard is hosted publicly on **Hugging Face Spaces** (Docker SDK,
free CPU tier — 2 vCPU / 16 GB RAM) and the daily refresh is automated
by a **GitHub Actions cron** (`.github/workflows/daily.yml`, 06:00 UTC).

---

## About the project

**Context.** WeatherLens was built as a university project for the
*Interactiunea Om-Calculator* (Human-Computer Interaction) course. The
brief asked for an end-to-end data product with a real dashboard, so we
built a weather pipeline that:

1. **Ingests** hourly data from Open-Meteo (no API key, no rate limit).
2. **Validates** the payload (schema + sanity checks).
3. **Transforms** raw JSON to partitioned Parquet, plus a daily summary.
4. **Catalogs** the partitions in DuckDB (Athena-equivalent SQL).
5. **Serves** an interactive dashboard with KPIs, calendar, day
   drill-down, activity scores and downloadable exports.

**Local-first stack.** Every AWS service has a free local equivalent:

| AWS service       | Local equivalent                              |
|-------------------|-----------------------------------------------|
| S3                | filesystem with Hive-style partitions (`data/`) |
| Lambda            | plain Python scripts (`src/ingest/`)          |
| Glue PySpark      | pandas + pyarrow (`src/etl/`)                 |
| Athena + Catalog  | DuckDB views (`src/catalog/`)                 |
| Step Functions    | orchestrator class with retry/catch           |
| QuickSight        | Streamlit + Plotly multipage                  |
| EventBridge       | APScheduler / Task Scheduler / GitHub Actions |
| CloudWatch        | loguru → `logs/*.log`                         |

**Snapshot included in repo:** the build is reproducible from scratch
with `scripts/bootstrap.py`. A typical run pulls **119 days** ×
**5 cities** → **14 280 hourly rows** + **595 daily summaries**,
finishing in **<1 second** on a laptop.

---

## Quickstart

```bash
pip install -r requirements.txt
python scripts/bootstrap.py --days 119      # backfill history
streamlit run dashboard/app.py              # open the dashboard
```

The dashboard opens at <http://localhost:8501>.

---

## Project structure (what's in the repo)

```
weather-analytics-aws/
├── README.md                       ← this file (HF Spaces frontmatter included)
├── Dockerfile                      ← container image for HF Spaces deploy
├── WeatherLens_Prezentare.pptx     ← academic presentation (18 slides)
├── requirements.txt                ← Python dependencies
├── .gitignore
│
├── pipeline.py                     ← convenience wrapper for the orchestrator
├── run.bat                         ← Windows launcher (bootstrap + dashboard)
├── run_dashboard.py                ← starts the Streamlit dashboard
│
├── src/
│   ├── config.py                   ← single source of truth (paths, cities, etc.)
│   ├── ingest/                     ← Lambda equivalents
│   │   ├── ingest.py               ← fetch Open-Meteo → raw JSON
│   │   ├── validate.py             ← schema + sanity checks
│   │   └── export.py               ← CSV / Excel / JSON exports
│   ├── etl/                        ← Glue equivalent
│   │   └── etl.py                  ← JSON → Parquet + daily summaries
│   ├── catalog/                    ← Athena + Glue Catalog equivalent
│   │   ├── catalog.py              ← DuckDB views over partitioned Parquet
│   │   └── queries.py              ← named-query runner
│   ├── orchestrator/               ← Step Functions equivalent
│   │   └── pipeline.py             ← retry/catch pipeline runner
│   ├── monitoring/                 ← CloudWatch equivalent
│   │   └── logger.py               ← loguru wrapper
│   └── scheduler/                  ← EventBridge equivalent
│       └── scheduler.py            ← APScheduler daily runner
│
├── dashboard/
│   ├── app.py                      ← multipage entry (run this)
│   ├── Overview.py                 ← page 1 — KPIs + trend + bars/donuts + top 10
│   ├── pages/
│   │   ├── 2_Calendar.py           ← page 2 — monthly calendar + drill-down
│   │   ├── 3_Day_Insights.py       ← page 3 — single-day fact sheet + activity scores
│   │   └── 4_Data_Explorer.py      ← page 4 — table + CSV / Excel / JSON export
│   ├── _filters.py                 ← global sidebar (cities popover · period · season)
│   ├── _data.py                    ← cached DuckDB queries
│   ├── _charts.py                  ← Plotly chart factories (dark theme)
│   ├── _calendar.py                ← calendar grid renderer + temperature legend
│   └── _recommendations.py         ← rule-based activity scoring
│
├── athena_queries/                 ← 10 SQL queries (DuckDB-flavoured Athena)
│
├── scripts/
│   ├── bootstrap.py                ← one-shot history backfill
│   ├── strip_diacritics.py         ← idempotent ASCII-fier for source files
│   └── build_presentation.py       ← regenerates WeatherLens_Prezentare.pptx
│
├── tests/                          ← pytest unit tests (12, all passing)
│
├── scheduler/
│   └── weatherlens_daily.xml       ← optional: Windows Task Scheduler import file
│
├── data/                           ← seed data (parquet + DuckDB), shipped in the repo
├── .streamlit/config.toml          ← dark theme palette
└── .github/workflows/daily.yml     ← GitHub Actions cron (06:00 UTC daily refresh)
```

Runtime artefacts (`data/raw/`, `data/exports/`, `logs/`, virtualenvs,
caches) are created on first run and excluded via `.gitignore`. The
seed snapshot under `data/processed/` and `data/catalog/` IS committed
so the live dashboard can boot instantly without running an ingest.

---

## Dashboard pages

| Page | Purpose |
|---|---|
| **Overview** | 7 KPI strip (avg/feels temp · precipitatii · vant · umiditate · zile extreme · vreme dominanta) · big trend line · 2 bars + 2 donuts (precipitatii per oras · weather distribution · avg temp per oras · wind categories) · top 10 hot/cold/rainy days. Donuts respond to clicks (slice → focus + centre count). |
| **Calendar** | Monthly view — pick city + month from dropdowns, header KPI row, calendar grid with week-number column on the left and 7-day columns. Each cell shows day# + temp + emoji + feels-like / humidity / rain. Click "Vezi Detalii" → switches to Day Insights with the date pre-selected. Temperature legend at the bottom. |
| **Day Insights** | Pick city + day, see hero card with weather emoji + temperature + inline stats, hourly chart (temp + feels-like + precipitation bars), 6 activity scores (Alergat · Ciclism · Drumetie · Picnic · Fotografie · Stat in casa). |
| **Data Explorer** | Granularity dropdown (Rezumat zilnic vs Rezumat orar) + 3 export buttons inline at the top, per-column average KPIs (in column order, 9 daily / 8 hourly), tall sortable table (780px). All filters live in the global sidebar — no page-specific filters. |

The global sidebar (identical on every page) hosts a **PowerBI-style
cities popover** (Select all + checkboxes, dynamic label), period
preset, season filter and a two-line "Date disponibile" caption.

---

## Common commands

```bash
# Run the daily pipeline for a single date
python -m src.orchestrator.pipeline --date 2026-04-29

# Backfill a window
python -m src.orchestrator.pipeline --start 2026-04-01 --end 2026-04-29

# Refresh the catalog after manual file drops
python -m src.catalog.catalog

# Run a named query and print the result
python -c "from src.catalog.queries import run_named; print(run_named('05_weather_frequency'))"

# Generate an Excel export from the CLI
python -m src.ingest.export --query 10_full_export --format xlsx --params city=bucharest year=2026

# Tests
python -m pytest tests/ -v

# Schedule daily runs (APScheduler, foreground)
python -m src.scheduler.scheduler --hour 6 --minute 0

# Regenerate the academic presentation (.pptx)
python scripts/build_presentation.py
```

---

## Cost & data volumes

* Open-Meteo: free tier, no API key, no rate limit at this volume.
* Storage: ~1 KB raw JSON + ~2 KB Parquet per city/day. 119 days × 5 cities ≈ 14 MB seed parquet + 268 KB DuckDB on disk.
* Compute: full pipeline for one day finishes in **<1 second** on a laptop.
* Dashboard: idle ~80 MB RAM, ~140 MB peak with cached queries.

**Total monthly cost: $0.**

---

## Deployment

The live dashboard is hosted on **Hugging Face Spaces** (Docker SDK,
free CPU tier — 2 vCPU / 16 GB RAM):
**<https://AlexOnData-weather-analytics-aws.hf.space>**

The Space is built from this repository's `Dockerfile`, which installs
`requirements.txt` and runs `streamlit run dashboard/app.py` on port
**7860** (the port HF Spaces routes public traffic to). The YAML
frontmatter at the top of this README controls the Space metadata
(`sdk: docker`, `app_port: 7860`).

Daily data refresh runs on **GitHub Actions** (`.github/workflows/daily.yml`)
every day at 06:00 UTC; the job fetches yesterday's weather, runs the
ETL and uploads the resulting parquet partitions as an artifact.
