"""
Central configuration for the disaster-intel pipeline.
Every URL, path, timeout, and setting lives here.
Nothing is hardcoded in other files.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# -- Project paths --
# All paths are relative to the project root, not wherever Python runs from
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"

# -- NASA EONET --
EONET_BASE_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
NASA_API_KEY = os.getenv("NASA_API_KEY")

# -- Open-Meteo (weather enrichment) --
# Free, no key required
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"

# -- NASA POWER (weather enrichment) --
# Free, no key required
NASA_POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

# -- OpenAQ (air quality enrichment) --
OPENAQ_BASE_URL = "https://api.openaq.org/v3"
OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY")

# -- Request settings --
REQUEST_TIMEOUT = 30          # seconds before a request gives up
CACHE_EXPIRATION = int(os.getenv("CACHE_EXPIRATION", 30 * 24 * 3600))
MAX_RETRIES = 3               # how many times to retry a failed request
WEATHER_BATCH_SIZE = 500      # max events to enrich per pipeline run
AQI_BATCH_SIZE = 200          # smaller batch - AQI needs 2+ API calls per event
REQUEST_CACHE_NAME = DATA_DIR / "http_cache"

# -- Database --
# SQLite for now - swap this one line for PostgreSQL later
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'disaster_intel.db'}")
