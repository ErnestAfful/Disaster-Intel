"""
Air Quality page — pollution impact of disaster events.

Q7: Median AQI pollutant levels by event type
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from dashboard.data import load_data, apply_filters
from dashboard.sidebar import render_sidebar
from analysis.phase2_charts import aqi_impact_by_type

st.set_page_config(page_title="Air Quality — disaster-intel", layout="wide", initial_sidebar_state="collapsed")

df_full = load_data()
event_types, date_range, statuses = render_sidebar(df_full)
df = apply_filters(df_full, event_types, date_range, statuses)

st.title("💨 Air Quality")
st.caption("Pollution levels recorded near events (North America — OpenAQ stations within 25 km).")
st.divider()

AQI_COLS = ["pm25", "pm10", "o3", "no2", "so2"]

df_aqi = df[
    (df["station_name"] != "NONE_FOUND") &
    df["station_name"].notna()
].dropna(subset=AQI_COLS, how="all")

if df_aqi.empty:
    st.info("No AQI-enriched data available for the current filters. Run overnight enrichment first.")
    st.stop()

# ── Q7: AQI by event type ─────────────────────────────────────────────────
st.subheader("Q7 — How do events affect local air quality?")

coverage = len(df_aqi)
st.caption(f"{coverage:,} events with AQI readings in current selection.")

# Aggregate from filtered data
aqi_summary = (
    df_aqi.groupby("event_type")[AQI_COLS]
    .median()
    .reset_index()
)

fig_aqi = aqi_impact_by_type(aqi_summary)
st.plotly_chart(fig_aqi, use_container_width=True)

# ── Station coverage table ─────────────────────────────────────────────────
st.subheader("Station coverage by event type")
coverage_table = (
    df_aqi.groupby("event_type")
    .agg(events_with_aqi=("id", "count"))
    .reset_index()
    .sort_values("events_with_aqi", ascending=False)
)
st.dataframe(coverage_table, use_container_width=True, hide_index=True)
