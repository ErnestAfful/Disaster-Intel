"""
Clean and transform raw EONET event data.

Takes the raw DataFrame from fetch_eonet.py and produces a flat,
analysis-ready table with one row per event.

This module handles:
    - Flattening nested geometry/category JSON
    - Coordinate extraction (handling EONET's [lon, lat] format)
    - Deduplication
    - Null removal
    - Date parsing
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)


def extract_geometry(df):
    """
    Flatten EONET's nested geometry column into lat, lon, and date columns.

    EONET stores coordinates as [longitude, latitude] — GeoJSON standard.
    This is reversed from what most tools expect (lat, lon).
    We fix that here so every downstream module gets (latitude, longitude).

    Design decision: we take the LAST geometry point [-1], not the first [0].
    Why? For moving events (hurricanes, storms), the last point is the
    most recent position. Your original code used [0] — the earliest.
    """
    logger.info("Extracting geometry data from nested JSON...")

    df = df.copy()

    df["latitude"] = df["geometry"].apply(
        lambda x: x[-1]["coordinates"][1] if x and len(x) > 0 else None
    )
    df["longitude"] = df["geometry"].apply(
        lambda x: x[-1]["coordinates"][0] if x and len(x) > 0 else None
    )
    df["date"] = df["geometry"].apply(
        lambda x: x[-1]["date"] if x and len(x) > 0 else None
    )
    df["event_type"] = df["categories"].apply(
        lambda x: x[0]["title"] if x and len(x) > 0 else None
    )

    # Count how many geometry points exist — useful for identifying
    # events that moved over time (hurricanes, storms)
    df["geometry_count"] = df["geometry"].apply(
        lambda x: len(x) if x else 0
    )

    return df


def clean_events(df):
    """
    Take a raw EONET DataFrame and return a clean, flat table.

    This is the full cleaning pipeline:
        1. Extract geometry (lat, lon, date, event_type)
        2. Drop the nested columns we no longer need
        3. Remove duplicates
        4. Remove rows missing critical fields
        5. Parse dates into proper datetime objects

    Args:
        df: Raw DataFrame from fetch_eonet_events()

    Returns:
        Cleaned DataFrame ready for analysis or enrichment
    """
    if df.empty:
        logger.warning("Received empty DataFrame — nothing to clean")
        return df

    logger.info(f"Cleaning {len(df)} raw events...")

    # Step 1 — flatten nested JSON
    df = extract_geometry(df)

    # Step 2 — drop nested columns that are now extracted
    # Sources dropped because it was mostly missing values
    # and not relevant to analysis (your original comment, line 71)
    cols_to_drop = ["geometry", "categories", "sources"]
    existing_cols = [c for c in cols_to_drop if c in df.columns]
    df = df.drop(columns=existing_cols)

    # Step 3 — deduplicate
    before = len(df)
    df = df.drop_duplicates(subset=["id"])  # dedupe by event ID, not all columns
    after = len(df)
    if before > after:
        logger.info(f"Removed {before - after} duplicate events")

    # Step 4 — drop rows missing critical fields
    required = ["latitude", "longitude", "date", "event_type"]
    before = len(df)
    df = df.dropna(subset=required)
    after = len(df)
    if before > after:
        logger.warning(f"Dropped {before - after} events with missing critical fields")

    # Step 5 — parse dates
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Step 6 — derive status column (used in Q5 of your analysis)
    if "closed" in df.columns:
        df["status"] = df["closed"].apply(
            lambda x: "Active" if pd.isna(x) else "Closed"
        )

    logger.info(f"Cleaning complete — {len(df)} events ready")

    return df
