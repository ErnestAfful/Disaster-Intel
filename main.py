"""
disaster-intel: main entry point.

This script does exactly what NASAProject.py did — but using
the modular pipeline. Same results, cleaner structure.

Usage:
    python main.py                  # default: all events, 2025-01-01 to 2026-04-30
    python main.py --days 7         # last 7 days only
    python main.py --no-charts      # fetch + clean without visualization
"""

import argparse
import logging
from pipeline.config import DATA_DIR, WEATHER_BATCH_SIZE, AQI_BATCH_SIZE
from pipeline.fetch_eonet import fetch_eonet_events
from pipeline.clean_events import clean_events
from pipeline.database import init_db, upsert_events
from pipeline.enrich_weather import enrich_missing_weather
from pipeline.enrich_aqi import enrich_missing_aqi
from pipeline.score_risk import score_all_events
from analysis.visualizations import (
    create_density_map,
    create_frequency_chart,
    create_monthly_activity_chart,
    create_wildfire_regional_analysis,
    create_status_chart,
)
from analysis import queries as q2
from analysis.phase2_charts import (
    weather_conditions_by_type,
    aqi_impact_by_type,
    weather_signatures,
    seasonal_climate_trends,
)

logger = logging.getLogger(__name__)


def persist_events(df):
    """Initialize the database and upsert cleaned events into it."""
    init_db()
    inserted, updated = upsert_events(df)
    logger.info(f"Database: {inserted} inserted, {updated} updated")
    return inserted, updated


def main(
    days=None,
    start="2025-01-01",
    end="2026-04-30",
    show_charts=True,
    phase2=False,
    weather_batch=WEATHER_BATCH_SIZE,
    aqi_batch=AQI_BATCH_SIZE,
    skip_weather=False,
    skip_aqi=False,
    backfill=False,
    north_america_aqi=True,
    max_weather_rounds=None,
    max_aqi_rounds=None,
):
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
    if not skip_weather:
        enrich_missing_weather(
            batch_size=weather_batch,
            run_until_done=backfill,
            max_rounds=max_weather_rounds,
        )
    else:
        logger.info("Skipping weather enrichment (--no-weather flag)")

    if not skip_aqi:
        enrich_missing_aqi(
            batch_size=aqi_batch,
            north_america_only=north_america_aqi,
            run_until_done=backfill,
            max_rounds=max_aqi_rounds,
        )
    else:
        logger.info("Skipping AQI enrichment (--no-aqi flag)")

    #Step 3b: Risk scoring
    scored = score_all_events()
    logger.info(f"Risk scoring: {scored} events scored.")

    # ── Step 4: Save ─
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    raw_path = DATA_DIR / "eonet_events_raw.csv"
    clean_path = DATA_DIR / "eonet_events_cleaned.csv"

    df_raw.to_csv(raw_path, index=False)
    df.to_csv(clean_path, index=False)
    logger.info(f"Raw data saved to {raw_path}")
    logger.info(f"Clean data saved to {clean_path}")

    #Step 5: Visualize 
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

    #Phase 2: Enrichment-aware analysis 
    if phase2:
        logger.info("Running Phase 2 analysis (enriched data)...")

        # Q6 — weather conditions by event type (box plots)
        df_weather = q2.weather_profiles()
        if not df_weather.empty:
            for fig in weather_conditions_by_type(df_weather):
                fig.show()
        else:
            logger.warning("Q6: No weather data available yet — run overnight enrichment first.")

        # Q7 — AQI impact by event type
        df_aqi_summary = q2.aqi_by_event_type()
        if not df_aqi_summary.empty:
            aqi_impact_by_type(df_aqi_summary).show()
        else:
            logger.warning("Q7: No AQI data available yet.")

        # Q8 — weather fingerprint radar
        df_signatures = q2.weather_signatures()
        if not df_signatures.empty:
            weather_signatures(df_signatures).show()
        else:
            logger.warning("Q8: Not enough weather data for radar chart.")

        # Q9 — seasonal trends vs climate conditions
        df_seasonal = q2.seasonal_enriched()
        if not df_seasonal.empty:
            seasonal_climate_trends(df_seasonal).show()
        else:
            logger.warning("Q9: No enriched seasonal data available yet.")

    logger.info("Pipeline run complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="disaster-intel pipeline")
    parser.add_argument("--days", type=int, help="Fetch last N days only")
    parser.add_argument("--start", default="2025-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2026-04-30", help="End date (YYYY-MM-DD)")
    parser.add_argument("--no-charts", action="store_true", help="Skip visualizations")
    parser.add_argument("--phase2", action="store_true",
                        help="Run Phase 2 enrichment-aware analysis (Q6–Q9)")
    parser.add_argument("--weather-batch", type=int, default=WEATHER_BATCH_SIZE,
                        help=f"Max events to enrich with weather per run (default: {WEATHER_BATCH_SIZE})")
    parser.add_argument("--no-weather", action="store_true", help="Skip weather enrichment")
    parser.add_argument("--no-aqi", action="store_true", help="Skip AQI enrichment")
    parser.add_argument("--aqi-batch", type=int, default=AQI_BATCH_SIZE,
                        help=f"Max events to enrich with AQI per run (default: {AQI_BATCH_SIZE})")
    parser.add_argument("--global-aqi", action="store_true", help="Attempt AQI enrichment outside North America")
    parser.add_argument("--backfill", action="store_true",
                        help="Keep enriching batches until no selected missing rows remain")
    parser.add_argument("--max-weather-rounds", type=int,
                        help="Stop weather enrichment after N rounds")
    parser.add_argument("--max-aqi-rounds", type=int,
                        help="Stop AQI enrichment after N rounds")

    args = parser.parse_args()

    main(
        days=args.days,
        start=args.start,
        end=args.end,
        show_charts=not args.no_charts,
        phase2=args.phase2,
        weather_batch=args.weather_batch,
        aqi_batch=args.aqi_batch,
        skip_weather=args.no_weather,
        skip_aqi=args.no_aqi,
        backfill=args.backfill,
        north_america_aqi=not args.global_aqi,
        max_weather_rounds=args.max_weather_rounds,
        max_aqi_rounds=args.max_aqi_rounds,
    )
