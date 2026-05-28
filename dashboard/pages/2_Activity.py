"""
Activity page — temporal patterns.

Q3: Monthly event activity by type
Q9: Seasonal trends grounded in actual climate conditions
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from dashboard.data import load_data, apply_filters
from dashboard.sidebar import render_sidebar
from analysis.visualizations import create_monthly_activity_chart
from analysis.phase2_charts import seasonal_climate_trends

st.set_page_config(page_title="Activity — disaster-intel", layout="wide", initial_sidebar_state="collapsed")

df_full = load_data()
event_types, date_range, statuses = render_sidebar(df_full)
df = apply_filters(df_full, event_types, date_range, statuses)

st.title("📅 Activity")
st.caption("Temporal patterns across event types.")
st.divider()

if df.empty:
    st.info("No events match the current filters.")
    st.stop()

# ── Q3: Monthly activity ───────────────────────────────────────────────────
st.subheader("Q3 — Which months and seasons see the highest activity?")
fig_monthly = create_monthly_activity_chart(df)
st.plotly_chart(fig_monthly, use_container_width=True)

# ── Q9: Seasonal trends vs climate ────────────────────────────────────────
st.subheader("Q9 — Do seasonal patterns hold up against actual climate data?")

df_weather = df.dropna(subset=["temperature_max", "precipitation"])
if df_weather.empty:
    st.info("No enriched weather data available yet for the current filters. Run overnight enrichment first.")
else:
    df_weather["month"] = df_weather["event_date"].dt.to_period("M").astype(str)
    df_seasonal = (
        df_weather.groupby(["month", "event_type"])
        .agg(
            event_count=("id", "count"),
            avg_temperature_max=("temperature_max", "mean"),
            avg_precipitation=("precipitation", "mean"),
        )
        .reset_index()
        .sort_values("month")
    )
    fig_seasonal = seasonal_climate_trends(df_seasonal)
    st.plotly_chart(fig_seasonal, use_container_width=True)
