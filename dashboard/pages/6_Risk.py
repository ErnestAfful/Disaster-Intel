"""
Risk Score page — Phase 4.

Three views:
  Q10 — Which events carry the highest composite risk score?
  Q11 — How does risk score vary across event types?
  Q12 — Where are the highest-risk events geographically?
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dashboard.data import load_data, apply_filters
from dashboard.sidebar import render_sidebar
from analysis.theme import apply_theme, themed_colors

st.set_page_config(
    page_title="Risk Score — disaster-intel",
    page_icon="⚠️",
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
st.title("⚠️ Risk Score Analysis")
st.caption(
    "Composite risk score (0–100) combining event-type severity, "
    "weather extremes, air quality, and population exposure."
)
st.divider()

if df.empty:
    st.info("No events match the current filters.")
    st.stop()

# Check if risk scores are available
if "risk_score" not in df.columns or df["risk_score"].isna().all():
    st.warning(
        "Risk scores have not been computed yet. "
        "Run `python main.py` to generate them, then reload this page."
    )
    st.stop()

df_scored = df[df["risk_score"].notna()].copy()

# ── KPI strip ─────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Scored Events", f"{len(df_scored):,}")
k2.metric("Avg Risk Score", f"{df_scored['risk_score'].mean():.1f}")
k3.metric("Max Risk Score", f"{df_scored['risk_score'].max():.1f}")
k4.metric("High Risk (>60)", f"{(df_scored['risk_score'] > 60).sum():,}")

st.divider()

# ── Q10: Top 20 highest-risk events ───────────────────────────────────────────
st.subheader("Q10 — Which events carry the highest composite risk score?")

top20 = (
    df_scored.nlargest(20, "risk_score")[
        ["title", "event_type", "event_date", "risk_score",
         "temperature_max", "windspeed_max", "pm25", "status"]
    ]
    .copy()
)
top20["event_date"] = top20["event_date"].dt.strftime("%Y-%m-%d")
top20["risk_score"] = top20["risk_score"].round(1)
top20.columns = ["Title", "Type", "Date", "Risk Score",
                 "Temp Max (°C)", "Wind Max (km/h)", "PM2.5", "Status"]
top20 = top20.reset_index(drop=True)
top20.index += 1

st.dataframe(
    top20,
    use_container_width=True,
    column_config={
        "Risk Score": st.column_config.ProgressColumn(
            "Risk Score",
            min_value=0,
            max_value=100,
            format="%.1f",
        )
    },
)

st.divider()

# ── Q11: Risk score by event type (box plot) ───────────────────────────────────
st.subheader("Q11 — How does risk score vary across event types?")

type_order = (
    df_scored.groupby("event_type")["risk_score"]
    .median()
    .sort_values(ascending=False)
    .index.tolist()
)

fig_box = px.box(
    df_scored,
    x="event_type",
    y="risk_score",
    color="event_type",
    category_orders={"event_type": type_order},
    title="Risk Score Distribution by Event Type",
    labels={"risk_score": "Risk Score (0–100)", "event_type": "Event Type"},
    color_discrete_sequence=themed_colors(),
)
fig_box.update_layout(showlegend=False, xaxis_tickangle=-30)
apply_theme(fig_box)
st.plotly_chart(fig_box, use_container_width=True)

st.divider()

# ── Q12: Global risk map ───────────────────────────────────────────────────────
st.subheader("Q12 — Where are the highest-risk events geographically?")

df_map = df_scored.dropna(subset=["latitude", "longitude"]).copy()
# Plotly requires size ≥ 0 — clip as a safety net for any edge-case scores
df_map["_size"] = df_map["risk_score"].clip(lower=1)

fig_map = px.scatter_geo(
    df_map,
    lat="latitude",
    lon="longitude",
    color="risk_score",
    size="_size",
    hover_name="title",
    hover_data={
        "event_type": True,
        "risk_score": ":.1f",
        "latitude": False,
        "longitude": False,
    },
    color_continuous_scale=[
        [0.0, "#2196F3"],
        [0.4, "#FFB300"],
        [0.7, "#FF6D00"],
        [1.0, "#E63946"],
    ],
    range_color=(0, 100),
    size_max=18,
    title="Global Risk Score Map",
    projection="natural earth",
)
fig_map.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    geo=dict(
        showframe=False,
        showcoastlines=True,
        coastlinecolor="#c8d0dc",
        showland=True,
        landcolor="#f0f4fa",
        showocean=True,
        oceancolor="#dce6f0",
        showcountries=True,
        countrycolor="#c8d0dc",
    ),
    coloraxis_colorbar=dict(title="Risk Score"),
)
st.plotly_chart(fig_map, use_container_width=True)

# ── Risk score breakdown legend 
st.divider()
st.caption(
    "**Score components:** Event type severity (40 pts) · "
    "Weather extremes — temp/wind/rain (25 pts) · "
    "Air quality PM2.5 (20 pts) · "
    "Population exposure proxy (15 pts)"
)
