"""
Dashboard data layer.

Loads the enriched events DataFrame once per hour and exposes a
filter helper used by every page. Chart functions receive filtered
DataFrames — no DB calls happen inside chart code.
"""

import sys
from pathlib import Path

# Ensure project root is on the path regardless of how Streamlit is invoked
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st
from pipeline.database import enriched_events


@st.cache_data(ttl=3600)
def load_data() -> pd.DataFrame:
    """
    Load the full enriched dataset (events + weather + AQI) from the DB.
    Result is cached for 1 hour — reloads automatically after that.
    """
    df = enriched_events()
    df["event_date"] = (
        pd.to_datetime(df["event_date"], errors="coerce", utc=True)
        .dt.tz_convert(None)  # convert from UTC to naive — tz_localize(None) errors on tz-aware
    )
    # Normalise status to lowercase so sidebar filters match ("Active" → "active")
    df["status"] = df["status"].str.lower()
    return df


def apply_filters(
    df: pd.DataFrame,
    event_types: list,
    date_range: tuple,
    statuses: list,
) -> pd.DataFrame:
    """
    Apply display-level filters to the enriched DataFrame.
    All filtering happens in memory — the query layer is not touched.
    """
    if event_types:
        df = df[df["event_type"].isin(event_types)]

    if date_range and len(date_range) == 2:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        df = df[(df["event_date"] >= start) & (df["event_date"] <= end)]

    if statuses:
        df = df[df["status"].isin(statuses)]

    return df.copy()


def kpi_stats(df: pd.DataFrame) -> dict:
    """
    Compute the 4 KPI cards shown on the Overview page.
    Returns a dict with keys: total, pct_weather, pct_aqi, top_type
    """
    total = len(df)
    if total == 0:
        return {"total": 0, "pct_weather": 0, "pct_aqi": 0, "top_type": "—"}

    pct_weather = round(df["temperature_max"].notna().sum() / total * 100, 1)

    aqi_done = (
        df["pm25"].notna() & (df["station_name"] != "NONE_FOUND")
    ).sum()
    pct_aqi = round(aqi_done / total * 100, 1)

    top_type = df["event_type"].value_counts().idxmax() if total > 0 else "—"

    return {
        "total": total,
        "pct_weather": pct_weather,
        "pct_aqi": pct_aqi,
        "top_type": top_type,
    }
