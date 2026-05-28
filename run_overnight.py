"""
run_overnight.py COB trigger.

Overnight run: 
Designed to be run once daily (e.g. via cron or Task Scheduler) to keep the database up-to-date with minimal manual intervention.

    python run_overnight.py

What it does:
  1. Fetches the latest EONET events (last 3 days, to catch any late updates)
  2. Persists new/updated events to the database
  3. Backfills ALL missing weather enrichment (runs until none left)
  4. Backfills ALL missing AQI enrichment (runs until none left)

Results are written to logs/overnight_YYYY-MM-DD.log so I can review
them in the morning. The terminal also shows a live summary.

No flags needed. 
"""

import logging
import sys
import time
from datetime import date
from pathlib import Path

# ── Logging setup — file + console 
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_file = LOG_DIR / f"overnight_{date.today()}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)

# ── Import pipeline after logging is configured 
from pipeline.config import WEATHER_BATCH_SIZE, AQI_BATCH_SIZE
from pipeline.fetch_eonet import fetch_eonet_events
from pipeline.clean_events import clean_events
from pipeline.database import init_db, upsert_events
from pipeline.enrich_weather import enrich_missing_weather
from pipeline.enrich_aqi import enrich_missing_aqi


def run():
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("OVERNIGHT RUN STARTING")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 60)

    # ── Step 1: Fresh fetch (last 3 days to catch late updates) 
    logger.info("Step 1/4 — Fetching latest EONET events (last 3 days)...")
    df_raw = fetch_eonet_events(days=3)

    if df_raw.empty:
        logger.warning("No events returned from EONET — skipping to enrichment.")
    else:
        df = clean_events(df_raw)
        if df.empty:
            logger.warning("No events survived cleaning.")
        else:
            init_db()
            inserted, updated = upsert_events(df)
            logger.info(f"  → {inserted} new events, {updated} updated")

    # ── Step 2: Backfill weather
    logger.info("Step 2/4 — Backfilling weather enrichment (run until done)...")
    enrich_missing_weather(batch_size=WEATHER_BATCH_SIZE, run_until_done=True)

    # ── Step 3: Backfill AQI ──────────────────────────────────────────────────
    logger.info("Step 3/4 — Backfilling AQI enrichment (run until done)...")
    enrich_missing_aqi(
        batch_size=AQI_BATCH_SIZE,
        north_america_only=True,
        run_until_done=True,
    )
    
    # ── Step 4: Summary 
    elapsed = time.time() - start_time
    minutes, seconds = divmod(int(elapsed), 60)

    logger.info("=" * 60)
    logger.info(f"OVERNIGHT RUN COMPLETE — {minutes}m {seconds}s")
    logger.info(f"Full log saved to: {log_file}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run()
