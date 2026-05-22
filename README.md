# disaster-intel

A modular environmental event enrichment pipeline using NASA EONET data combined with real-time and historical weather intelligence.

## What it does

Tracks natural disaster events globally — wildfires, storms, volcanoes, floods — and enriches each event with weather conditions, air quality data, and population impact metrics.

## Project phases

- **Phase 0** ✅ — Refactor into modular architecture
- **Phase 1** 🔲 — Data pipeline (database, weather + AQI enrichment, scheduling)
- **Phase 2** 🔲 — Analysis layer (research questions, correlation analysis)
- **Phase 3** 🔲 — Live Streamlit dashboard
- **Phase 4** 🔲 — Population impact and risk scoring
- **Phase 5** 🔲 — Prediction and scaling

## Quick start

```bash
git clone https://github.com/YOUR_USERNAME/disaster-intel.git
cd disaster-intel
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # add your NASA API key (optional)
python main.py
```

## Data sources

| Source | What it provides | Auth required |
|--------|-----------------|---------------|
| [NASA EONET](https://eonet.gsfc.nasa.gov/) | Natural disaster events with coordinates | No (optional key) |
| [Open-Meteo](https://open-meteo.com/) | Historical weather at event locations | No |
| [OpenAQ](https://openaq.org/) | Air quality measurements | No |

## Project structure

```
disaster-intel/
├── main.py                 # Entry point — runs the full pipeline
├── pipeline/               # ETL logic
│   ├── config.py           # All settings in one place
│   ├── fetch_eonet.py      # NASA EONET API client
│   └── clean_events.py     # Data cleaning and transformation
├── analysis/               # Research questions and visualizations
│   └── visualizations.py   # Plotly charts for each research question
├── dashboard/              # Streamlit app (Phase 3)
├── data/                   # Local database and cached data
├── logs/                   # Pipeline run logs
└── tests/                  # Unit tests
```
