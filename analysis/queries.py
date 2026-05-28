"""
Phase 2 data access layer.

Each function queries the enriched_events() master join and returns a
clean, analysis-ready DataFrame. Chart code never touches the database
directly — it only calls these functions.

All functions silently drop rows that are missing the columns they need
(e.g. events without weather or AQI data yet) so charts degrade
gracefully as enrichment fills in over time.
"""

import logging
import pandas as pd
from pipeline.database import enriched_events

logger = logging.getLogger(__name__)


def _load() -> pd.DataFrame:
    """Load the full enriched dataset once and parse the date column."""
    df = enriched_events()
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    return df


# Q6: Weather conditions by event type

def weather_profiles() -> pd.DataFrame:
    """
    Return all enriched events that have weather data.

    Columns: event_type, event_date, temperature_max, temperature_min,
             precipitation, windspeed_max, humidity
    """
    df = _load()
    weather_cols = ["temperature_max", "temperature_min",
                    "precipitation", "windspeed_max", "humidity"]
    df = df.dropna(subset=weather_cols, how="all")
    df = df[["id", "event_type", "event_date"] + weather_cols].copy()
    logger.info(f"weather_profiles: {len(df)} events with weather data")
    return df


def weather_by_event_type() -> pd.DataFrame:
    """
    Median weather conditions per event type.

    Columns: event_type, temperature_max, temperature_min,
             precipitation, windspeed_max, humidity
    """
    df = weather_profiles()
    weather_cols = ["temperature_max", "temperature_min",
                    "precipitation", "windspeed_max", "humidity"]
    summary = (
        df.groupby("event_type")[weather_cols]
        .median()
        .reset_index()
    )
    logger.info(f"weather_by_event_type: {len(summary)} event types")
    return summary


# Q7: AQI impact by event type

def aqi_profiles() -> pd.DataFrame:
    """
    Return all enriched events that have AQI data (excluding NONE_FOUND rows).

    Columns: event_type, event_date, pm25, pm10, o3, no2, so2
    """
    df = _load()
    aqi_cols = ["pm25", "pm10", "o3", "no2", "so2"]
    # Drop rows where station was not found
    df = df[df["station_name"] != "NONE_FOUND"]
    df = df.dropna(subset=aqi_cols, how="all")
    df = df[["id", "event_type", "event_date"] + aqi_cols].copy()
    logger.info(f"aqi_profiles: {len(df)} events with AQI data")
    return df


def aqi_by_event_type() -> pd.DataFrame:
    """
    Median AQI pollutant levels per event type.

    Columns: event_type, pm25, pm10, o3, no2, so2
    """
    df = aqi_profiles()
    aqi_cols = ["pm25", "pm10", "o3", "no2", "so2"]
    summary = (
        df.groupby("event_type")[aqi_cols]
        .median()
        .reset_index()
    )
    logger.info(f"aqi_by_event_type: {len(summary)} event types")
    return summary


# Q8: Weather signatures (for radar chart)

def weather_signatures() -> pd.DataFrame:
    """
    Normalised (0-1) median weather profile per event type — used for
    the radar/spider chart so all 5 variables sit on the same scale.

    Columns: event_type, temperature_max, temperature_min,
             precipitation, windspeed_max, humidity  (all 0–1)
    """
    df = weather_by_event_type()
    weather_cols = ["temperature_max", "temperature_min",
                    "precipitation", "windspeed_max", "humidity"]
    normalised = df.copy()
    for col in weather_cols:
        col_min = df[col].min()
        col_max = df[col].max()
        if col_max > col_min:
            normalised[col] = (df[col] - col_min) / (col_max - col_min)
        else:
            normalised[col] = 0.0
    return normalised


#  Q9: Seasonal patterns with enriched climate data

def seasonal_enriched() -> pd.DataFrame:
    """
    Monthly event counts alongside average temperature and precipitation.

    Columns: month (str YYYY-MM), event_type, event_count,
             avg_temperature_max, avg_precipitation
    """
    df = _load()
    df = df.dropna(subset=["temperature_max", "precipitation"])
    df["month"] = df["event_date"].dt.to_period("M").astype(str)

    summary = (
        df.groupby(["month", "event_type"])
        .agg(
            event_count=("id", "count"),
            avg_temperature_max=("temperature_max", "mean"),
            avg_precipitation=("precipitation", "mean"),
        )
        .reset_index()
        .sort_values("month")
    )
    logger.info(f"seasonal_enriched: {len(summary)} month/type rows")
    return summary
