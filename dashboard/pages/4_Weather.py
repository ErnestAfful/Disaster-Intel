"""
Weather page — climate conditions at event sites.

Q6: Distribution of weather variables across event types (box plots)
Q8: Weather fingerprint radar chart (normalised per-type profiles)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from dashboard.data import load_data, apply_filters
from dashboard.sidebar import render_sidebar
from analysis.phase2_charts import weather_conditions_by_type, weather_signatures

st.set_page_config(page_title="Weather — disaster-intel", layout="wide")

df_full = load_data()
event_types, date_range, statuses = render_sidebar(df_full)
df = apply_filters(df_full, event_types, date_range, statuses)

st.title("🌤️ Weather Conditions")
st.caption("Climate conditions recorded at event locations during events.")
st.divider()

WEATHER_COLS = ["temperature_max", "temperature_min",
                "precipitation", "windspeed_max", "humidity"]

df_weather = df.dropna(subset=WEATHER_COLS, how="all")

if df_weather.empty:
    st.info("No weather-enriched data available for the current filters. Run overnight enrichment first.")
    st.stop()

# ── Q6: Box plots ────────────────────────────────────────────────────────
st.subheader("Q6 — Do events cluster around specific weather conditions?")

figs = weather_conditions_by_type(df_weather)
# Display in 2-column grid
for i in range(0, len(figs), 2):
    cols = st.columns(2)
    cols[0].plotly_chart(figs[i], use_container_width=True)
    if i + 1 < len(figs):
        cols[1].plotly_chart(figs[i + 1], use_container_width=True)

st.divider()

# ── Q8: Weather fingerprint radar ────────────────────────────────────────
st.subheader("Q8 — Do disaster types have distinct weather fingerprints?")

# Build normalised summary from filtered data
summary = (
    df_weather.groupby("event_type")[WEATHER_COLS]
    .median()
    .reset_index()
)

if len(summary) < 2:
    st.info("At least 2 event types needed to compare fingerprints.")
else:
    normalised = summary.copy()
    for col in WEATHER_COLS:
        col_min, col_max = summary[col].min(), summary[col].max()
        normalised[col] = (
            (summary[col] - col_min) / (col_max - col_min)
            if col_max > col_min else 0.0
        )
    fig_radar = weather_signatures(normalised)
    st.plotly_chart(fig_radar, use_container_width=True)
