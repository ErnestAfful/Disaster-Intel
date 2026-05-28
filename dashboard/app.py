"""
disaster-intel dashboard — Overview page.

Run from the project root:
    streamlit run dashboard/app.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from dashboard.data import load_data, apply_filters, kpi_stats
from dashboard.sidebar import render_sidebar
from analysis.visualizations import (
    create_density_map,
    create_frequency_chart,
    create_status_chart,
)

st.set_page_config(
    page_title="disaster-intel",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Data ──────────────────────────────────────────────────────────────────────
df_full = load_data()

if df_full.empty:
    st.error("No data in the database yet. Run `python main.py` first.")
    st.stop()

event_types, date_range, statuses = render_sidebar(df_full)
df = apply_filters(df_full, event_types, date_range, statuses)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🌍 disaster-intel")
st.caption("NASA EONET natural disaster events enriched with weather and air quality data.")
st.divider()

# ── KPI strip ─────────────────────────────────────────────────────────────────
stats = kpi_stats(df)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Events", f"{stats['total']:,}")
k2.metric("Weather Enriched", f"{stats['pct_weather']}%")
k3.metric("AQI Enriched", f"{stats['pct_aqi']}%")
k4.metric("Most Active Type", stats["top_type"])

st.divider()

if df.empty:
    st.info("No events match the current filters.")
    st.stop()

# ── Q1: Global density map ─────────────────────────────────────────────────
st.subheader("Q1 — Where do natural disasters cluster most densely?")
fig_density = create_density_map(df)
st.plotly_chart(fig_density, use_container_width=True)

# ── Q2: Frequency over time ────────────────────────────────────────────────
st.subheader("Q2 — Is the frequency of event types increasing over time?")
fig_freq = create_frequency_chart(df)
st.plotly_chart(fig_freq, use_container_width=True)

# ── Q5: Active vs closed ──────────────────────────────────────────────────
st.subheader("Q5 — How many events are active vs closed?")
fig_status = create_status_chart(df)
if fig_status:
    st.plotly_chart(fig_status, use_container_width=True)
else:
    st.info("Status data not available.")
