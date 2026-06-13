# Disaster-intel

Disaster-intel is a full stack natural disaster intelligence platfrom built on the NASA EONET API. It feteches, cleans, scores and visualizes over 7000 natural disaster events globally, but more specific to the United States starting from January 2025 to May 2026. The platform is built across 5 development phases, starting from API ingestion through weather and air quality enrichment, interactice Streamlit dashboard, composite risk scoring engine and linear trend forecast model. The finished model is deployed publicly on Streamlit Cloud. 

# [Link to model](https://disaster-intel-j777swqnseevaz48ygagmm.streamlit.app/)

## Description

- **Phase 0** — Refactor into modular architecture
    Instead of running the entire project in one file, it was separated into different files in order to improve scalability and readability. 
- **Phase 1** — Data pipeline (database)
    The first phase established the full data pipeline from raw API to a structured SQLite format. 
        1: Upsert Logic in database.py: Existing events are now updated on each run rather than being duplicated which enabled incremental refreshes without losing any data. 
        2: Request Cache with SQLite Backend: All Http reponses are cached locally for 30 days. This eliminates redundant API calls on reruns and protecting against rate limits. 
        3: Pipeline Enrichment: Separating each run into an independent module so any stage can be run/rerun without affecting other parts of the data. 
        4: Configuration: URLs, batch sizes, timeouts, and paths live in the pipeline/config.py. 

    Output: 7744 clean events loaded into SQLite with id, title, event_type, coordinates, date, and status. 
- **Phase 2** — Weather & AQI Enrichment
    The second phase extended the dataset with environmental context for every event. This phase created an incremental encrichment. Only events missing enrichment data are processed each run, this reduces the burden of having to constantly call the API. 
        1: Weather enrichment achieved 100% coverage. All 7,744 events have temperature, wind, and precipitation data attached.
        2: AQI enrichment is scoped to North America (lat 15-72, lon -168 to -52) due to OpenAQ station density. 310 events (4%) have PM2.5 readings
        3: Open-Meteo returns -999.0 as a sentinel for missing data. A guard was added in the risk scorer to treat any temperature below -100 as missing.
- **Phase 3** — Live Streamlit dashboard
    This built the interactive dashboard with 5 pages addressing fourteen research questions. 
        Question 1: Where do natural disasters cluster most densely?
        Question 2: Is the frequency of event types increasing over time?
        Question 3: Which months and seasons see the highest activity?
        Question 4: Which regions are most prone to wildfires?
            This process involved reverse geocoding latitude and longitude coordinates in order to determine which Countries was most impacted by Wildfire Counts. The EONET has a North American Bias, hence the focus on North America throughout the rest of the project. 
        Question 5: How many events are active vs closed?
        Question 6: Do events cluster around specific weather conditions?
            This is a mathematical calculation using data from weather and AQ API
        Question 7: How do events affect local air quality?
        Question 8: Do disaster types have distinct weather fingerprints?
        Question 9: Do seasonal patterns hold up against actual climate data?
        Question 10: Which events carry the highest composite risk score?
        Question 11: How does risk score vary across event types?
        Question 12: Where are the highest-risk events geographically?
        Question 13: Projected event frequency for the next 3 months
        Question 14: Which event types are trending up or down?
- **Phase 4** — Risk Scoring Engine
    Phase 4 added a composite risk score (0-100) for every event, stored in the events table and recomputed incrementally on each pipeline run
- **Phase 5** — Prediction and scaling
    The final phase added a 3-month forward forecast for event counts per type using ordinary least-squares linear regression (numpy.polyfit). No external ML dependencies were required.
        History: monthly event counts per type from Jan 2025 to May 2026 (14+ months).
        Model: linear trend fit (degree-1 polynomial) on sequential month indices.
        Confidence interval: +/- 1.96 * residual standard deviation of the fit.
        Minimum 6 months of history required to fit a trend for any given type.


## Quick start
Follow these steps to set up and run the project locally.

1: Clone the repository: 
    git clone https://github.com/ErnestAfful/Disaster-Intel.git
    cd Disaster-Intel
2: Set up Virtual Environment: 
    python3 -m venv venv
    source venv/bin/activate
3: Install dependencies 
    pip install -r requirements.txt
4: Configure environment variables: Copy the example .env file. A NASA API key is optional but recommended for higher rate limits.
    cp .env.example .env 

## Usage
1. Run the Main Pipeline
This command runs the full ETL pipeline: it fetches events from EONET, cleans them, enriches them with weather and AQI data, calculates risk scores, and saves everything to the database.
    python main.py
        By default, this fetches data from 2025-01-01 to 2026-04-30.
        Use --days <N> to fetch data for the last N days (e.g., python main.py --days 7).

2. Launch the Dashboard
Once the database is populated, you can explore the data using the Streamlit dashboard.
    streamlit run dashboard/app.py

3. Run Scheduled Updates
The run_overnight.py script is designed for automated daily execution (e.g., via a cron job). It fetches the latest events and backfills any missing weather or AQI data for the entire database.

python run_overnight.py

## Project Architecture 
The project is organized into distinct modules for clarity and maintainability. 
disaster-intel/
├── main.py                 # Main entry point to run the full pipeline
├── run_overnight.py        # Script for scheduled daily data updates and backfills
├── dashboard/              # The multi-page Streamlit application
├── pipeline/               # Core ETL engine: fetching, cleaning, enrichment, and risk scoring
├── analysis/               # Data analysis, visualization generation, and forecasting logic
├── data/                   # Local data storage (SQLite DB, request cache)
├── logs/                   # Log files for pipeline runs
└── requirements.txt        # Project dependencies

## Data sources

| Source | What it provides | Auth required |
|--------|-----------------|---------------|
| [NASA EONET](https://eonet.gsfc.nasa.gov/) | Natural disaster events with coordinates | No (optional key) |
| [Open-Meteo](https://open-meteo.com/) | Historical weather at event locations | No |
| [OpenAQ](https://openaq.org/) | Air quality measurements | No |

