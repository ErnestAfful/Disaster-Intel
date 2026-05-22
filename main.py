"""
disaster-intel: main entry point.

This script does exactly what NASAProject.py did — but using
the modular pipeline. Same results, cleaner structure.

Usage:
    python main.py                  # default: all events, 2020-2026
    python main.py --days 7         # last 7 days only
    python main.py --no-charts      # fetch + clean without visualization
"""

import argparse
import logging
from pipeline.config import DATA_DIR
from pipeline.fetch_eonet import fetch_eonet_events
from pipeline.clean_events import clean_events
from pipeline.database import init_db, upsert_events 
from analysis.visualizations import (
    create_density_map,
    create_frequency_chart,
    create_monthly_activity_chart,
    create_wildfire_regional_analysis,
    create_status_chart,
)

logger = logging.getLogger(__name__)


def persist_events(df):
    """Initialize the database and upsert cleaned events into it."""
    init_db()
    inserted, updated = upsert_events(df)
    logger.info(f"Database: {inserted} inserted, {updated} updated")
    return inserted, updated


def main(days=None, start="2020-01-01", end="2026-03-31", show_charts=True):
    """
    Run the full pipeline: fetch → clean → save → visualize.

    This replaces NASAProject.py entirely.
    """

    # ── Step 1: Fetch 
    logger.info("=" * 60)
    logger.info("STARTING PIPELINE RUN")
    logger.info("=" * 60)

    if days:
        df_raw = fetch_eonet_events(days=days)
    else:
        df_raw = fetch_eonet_events(start=start, end=end)

    if df_raw.empty:
        logger.error("No data returned from EONET. Stopping.")
        return

    # ── Step 2: Clean 
    df = clean_events(df_raw)

    if df.empty:
        logger.error("No events survived cleaning. Stopping.")
        return

    # ── Step 3: Persist to database ─
    persist_events(df)

    # ── Step 4: Save ─
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    raw_path = DATA_DIR / "eonet_events_raw.csv"
    clean_path = DATA_DIR / "eonet_events_cleaned.csv"

    df_raw.to_csv(raw_path, index=False)
    df.to_csv(clean_path, index=False)
    logger.info(f"Raw data saved to {raw_path}")
    logger.info(f"Clean data saved to {clean_path}")

    # ── Step 5: Visualize 
    if not show_charts:
        logger.info("Skipping charts (--no-charts flag)")
        return

    logger.info("Generating visualizations...")

    # Q1 — density map
    fig_density = create_density_map(df)
    fig_density.show()

    # Q2 — frequency over time
    fig_freq = create_frequency_chart(df)
    fig_freq.show()

    # Q3 — monthly activity
    fig_monthly = create_monthly_activity_chart(df)
    fig_monthly.show()

    # Q4 — wildfire regions
    fig_country, fig_state = create_wildfire_regional_analysis(df)
    if fig_country:
        fig_country.show()
    if fig_state:
        fig_state.show()

    # Q5 — active vs closed
    fig_status = create_status_chart(df)
    if fig_status:
        fig_status.show()

    logger.info("Pipeline run complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="disaster-intel pipeline")
    parser.add_argument("--days", type=int, help="Fetch last N days only")
    parser.add_argument("--start", default="2020-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2026-03-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--no-charts", action="store_true", help="Skip visualizations")

    args = parser.parse_args()

    main(
        days=args.days,
        start=args.start,
        end=args.end,
        show_charts=not args.no_charts,
    )
