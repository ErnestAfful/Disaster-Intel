"""
Regional page — where events cluster by geography.

Q4: Wildfire breakdown by country and US state
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from dashboard.data import load_data, apply_filters
from dashboard.sidebar import render_sidebar
from analysis.visualizations import create_wildfire_regional_analysis

st.set_page_config(page_title="Regional — disaster-intel", layout="wide", initial_sidebar_state="collapsed")

df_full = load_data()
event_types, date_range, statuses = render_sidebar(df_full)
df = apply_filters(df_full, event_types, date_range, statuses)

st.title("🗺️ Regional")
st.caption("Geographic breakdown of event types.")
st.divider()

if df.empty:
    st.info("No events match the current filters.")
    st.stop()

# ── Q4: Wildfire regional analysis ────────────────────────────────────────
st.subheader("Q4 — Which regions are most prone to wildfires?")

wildfires = df[df["event_type"] == "Wildfires"]
if wildfires.empty:
    st.info("No wildfire events in the current filter selection.")
else:
    with st.spinner("Reverse geocoding coordinates..."):
        fig_country, fig_state = create_wildfire_regional_analysis(df)

    if fig_country:
        st.plotly_chart(fig_country, use_container_width=True)
    if fig_state:
        st.plotly_chart(fig_state, use_container_width=True)
