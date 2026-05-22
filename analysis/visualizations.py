"""
Visualization functions for EONET event analysis.

Each function answers one research question and returns a Plotly figure.
They don't call fig.show() — the caller decides whether to display,
save to file, or pass to a dashboard.

All functions expect a CLEANED DataFrame (output of clean_events).
"""

import logging
import plotly.express as px
import pandas as pd

logger = logging.getLogger(__name__)


# ── Q1: Where do natural disasters cluster most densely? ──────
def create_density_map(df):
    """
    Global heatmap of event locations.
    Original: NASAProject.py lines 82-94
    """
    logger.info("Creating global density map...")

    df = df.copy()
    df["count"] = 1

    fig = px.density_mapbox(
        df,
        lat="latitude",
        lon="longitude",
        z="count",
        radius=15,
        center=dict(lat=0, lon=0),
        zoom=2,
        mapbox_style="open-street-map",
        title="Global Distribution of NASA EONET Events",
    )

    return fig


# ── Q2: Is the frequency of event types increasing over time? ─
def create_frequency_chart(df):
    """
    Line chart showing event count by type over monthly periods.
    Original: NASAProject.py lines 96-110

    Note from your original analysis: severe storms appear
    underrepresented due to reporting bias — EONET relies on
    specific source agencies (USGS, GDACs, InciWeb) and
    storm-tracking agencies like NOAA/NWS don't always feed in.
    """
    logger.info("Creating event frequency chart...")

    df = df.copy()
    df["month"] = df["date"].dt.to_period("M").astype(str)

    monthly_counts = (
        df.groupby(["month", "event_type"])["id"]
        .count()
        .reset_index(name="event_count")
    )

    fig = px.line(
        monthly_counts,
        x="month",
        y="event_count",
        color="event_type",
        title="Frequency of Event Types Over Time",
        labels={"event_count": "Number of Events", "month": "Month"},
    )

    return fig


# ── Q3: Which months/seasons see the highest activity? ────────
def create_monthly_activity_chart(df):
    """
    Bar chart of monthly event counts grouped by type.
    Original: NASAProject.py lines 112-122
    """
    logger.info("Creating monthly activity chart...")

    df = df.copy()
    df["month"] = df["date"].dt.to_period("M").astype(str)

    monthly_counts = (
        df.groupby(["month", "event_type"])["id"]
        .count()
        .reset_index(name="event_count")
    )

    fig = px.bar(
        monthly_counts,
        x="month",
        y="event_count",
        color="event_type",
        title="Monthly Event Activity",
        barmode="group",
        labels={"event_count": "Number of Events", "month": "Month"},
    )

    return fig


# ── Q4: Which regions are prone to specific disaster types? ───
def create_wildfire_regional_analysis(df):
    """
    Bar charts showing top countries and US states by wildfire count.
    Original: NASAProject.py lines 124-163

    Returns a tuple: (country_fig, state_fig)
    """
    import reverse_geocoder as rg

    logger.info("Running wildfire regional analysis...")

    df_wildfires = df[df["event_type"] == "Wildfires"].copy()
    logger.info(f"Total wildfire events: {len(df_wildfires)}")

    if df_wildfires.empty:
        logger.warning("No wildfire events found")
        return None, None

    # Reverse geocode coordinates to country/state
    coordinates = list(zip(df_wildfires["latitude"], df_wildfires["longitude"]))
    results = rg.search(coordinates)

    df_wildfires["country"] = [r["cc"] for r in results]
    df_wildfires["state"] = [r["admin1"] for r in results]

    # Global view — top 15 countries
    country_counts = df_wildfires["country"].value_counts().head(15)
    logger.info(f"Top 15 countries by wildfire count:\n{country_counts}")

    fig_country = px.bar(
        x=country_counts.index,
        y=country_counts.values,
        title="Top 15 Countries by Wildfire Event Count",
        labels={"x": "Country Code", "y": "Number of Wildfire Events"},
    )

    # US-specific view — top 15 states
    df_us = df_wildfires[df_wildfires["country"] == "US"]
    state_counts = df_us["state"].value_counts().head(15)
    logger.info(f"Top 15 US states by wildfire count:\n{state_counts}")

    fig_state = px.bar(
        x=state_counts.index,
        y=state_counts.values,
        title="Top 15 US States by Wildfire Event Count",
        labels={"x": "State", "y": "Number of Wildfire Events"},
    )

    return fig_country, fig_state


# ── Q5: How many events are active vs closed? ─────────────────
def create_status_chart(df):
    """
    Grouped bar chart of active vs closed events by type.
    Original: NASAProject.py lines 165-175

    Requires 'status' column — added during cleaning step.
    """
    logger.info("Creating active vs closed status chart...")

    if "status" not in df.columns:
        logger.error("'status' column missing — was clean_events() run?")
        return None

    event_status = (
        df.groupby(["event_type", "status"])["id"]
        .count()
        .reset_index(name="event_count")
    )

    fig = px.bar(
        event_status,
        x="event_type",
        y="event_count",
        color="status",
        title="Active vs Closed Events by Type",
        barmode="group",
        labels={"event_count": "Number of Events", "event_type": "Event Type"},
    )

    return fig
