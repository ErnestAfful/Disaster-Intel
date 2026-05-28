"""
Forecast page — Phase 5.

Q13 — What is the projected event frequency for the next 3 months?
Q14 — Which event types are trending up or down?
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from dashboard.data import load_data, apply_filters
from dashboard.sidebar import render_sidebar
from analysis.predict import forecast_event_counts, trend_direction
from analysis.theme import apply_theme, themed_colors

st.set_page_config(
    page_title="Forecast — disaster-intel",
    page_icon="📈",
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
st.title("📈 Event Frequency Forecast")
st.caption(
    "Linear trend forecast for the next 3 months, fit on monthly event counts "
    "per event type. Shaded bands show a 95% confidence interval."
)
st.divider()

if df.empty:
    st.info("No events match the current filters.")
    st.stop()

# ── Compute forecast ──────────────────────────────────────────────────────────
with st.spinner("Fitting trend models…"):
    history_df, forecast_df, trend_df = forecast_event_counts(df, months_ahead=3)
    trends = trend_direction(df, months_ahead=3)

if history_df.empty:
    st.warning("Not enough historical data to build a forecast (need ≥ 6 months per type).")
    st.stop()


def _to_rgba(color: str, alpha: float = 0.15) -> str:
    """Convert any Plotly-valid color string to an rgba() string with alpha."""
    color = color.strip()
    if color.startswith("#"):
        h = color.lstrip("#")
        if len(h) == 6:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f"rgba({r},{g},{b},{alpha})"
    if color.startswith("rgba"):
        return color  # already has alpha
    if color.startswith("rgb("):
        return color.replace("rgb(", "rgba(").replace(")", f",{alpha})")
    return color  # fallback — return as-is


# ── Q13: Observed vs forecast chart ───────────────────────────────────────────
st.subheader("Q13 — Projected event frequency for the next 3 months")

# Event type selector
available_types = sorted(history_df["event_type"].unique())
selected_types = st.multiselect(
    "Select event types to display",
    options=available_types,
    default=available_types[:5] if len(available_types) > 5 else available_types,
)

if selected_types:
    colors = themed_colors()
    color_map = {t: colors[i % len(colors)] for i, t in enumerate(available_types)}

    fig = go.Figure()

    for etype in selected_types:
        color = color_map[etype]

        # Historical line
        hist = history_df[history_df["event_type"] == etype].sort_values("month_str")
        fig.add_trace(go.Scatter(
            x=hist["month_str"],
            y=hist["count"],
            mode="lines+markers",
            name=etype,
            line=dict(color=color, width=2),
            marker=dict(size=4),
            legendgroup=etype,
        ))

        # Trend line (dashed, same color)
        tr = trend_df[trend_df["event_type"] == etype].sort_values("month_str")
        fig.add_trace(go.Scatter(
            x=tr["month_str"],
            y=tr["trend"],
            mode="lines",
            name=f"{etype} (trend)",
            line=dict(color=color, width=1.5, dash="dot"),
            legendgroup=etype,
            showlegend=False,
        ))

        # Forecast with confidence band
        fcast = forecast_df[forecast_df["event_type"] == etype].sort_values("month_str")
        if not fcast.empty:
            # Connect last history point to first forecast point
            last_hist = hist.iloc[-1]
            x_connect = [last_hist["month_str"]] + fcast["month_str"].tolist()
            y_connect = [last_hist["count"]] + fcast["count"].tolist()

            fig.add_trace(go.Scatter(
                x=x_connect,
                y=y_connect,
                mode="lines+markers",
                name=f"{etype} (forecast)",
                line=dict(color=color, width=2, dash="dash"),
                marker=dict(size=6, symbol="diamond"),
                legendgroup=etype,
                showlegend=False,
            ))

            # Confidence band
            x_band = fcast["month_str"].tolist()
            fig.add_trace(go.Scatter(
                x=x_band + x_band[::-1],
                y=fcast["upper"].tolist() + fcast["lower"].tolist()[::-1],
                fill="toself",
                fillcolor=_to_rgba(color, 0.15),
                line=dict(color="rgba(0,0,0,0)"),
                legendgroup=etype,
                showlegend=False,
                hoverinfo="skip",
            ))

    # Vertical line marking forecast start (add_vline doesn't support string axes)
    last_history_month = history_df["month_str"].max()
    fig.add_shape(
        type="line",
        xref="x", yref="paper",
        x0=last_history_month, x1=last_history_month,
        y0=0, y1=1,
        line=dict(dash="dash", color="#888", width=1.5),
    )
    fig.add_annotation(
        xref="x", yref="paper",
        x=last_history_month, y=1.02,
        text="◀ history  |  forecast ▶",
        showarrow=False,
        font=dict(size=11, color="#888"),
        xanchor="center",
    )

    fig.update_layout(
        title="Event Frequency: Observed vs Forecast",
        xaxis_title="Month",
        yaxis_title="Event Count",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    apply_theme(fig)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Select at least one event type above.")

st.divider()

# ── Q14: Trend direction summary ──────────────────────────────────────────────
st.subheader("Q14 — Which event types are trending up or down?")

if not trends.empty:
    col_a, col_b = st.columns([2, 1])

    with col_a:
        # Horizontal bar chart of % change
        bar_colors = [
            "#E63946" if d.startswith("↑") else
            "#2196F3" if d.startswith("↓") else
            "#888888"
            for d in trends["direction"]
        ]

        fig_bar = go.Figure(go.Bar(
            x=trends["pct_change"],
            y=trends["event_type"],
            orientation="h",
            marker_color=bar_colors,
            text=[f"{v:+.1f}%" for v in trends["pct_change"]],
            textposition="outside",
        ))
        fig_bar.update_layout(
            title="Projected % Change Over Next 3 Months",
            xaxis_title="% Change",
            yaxis_title="",
            yaxis=dict(autorange="reversed"),
        )
        apply_theme(fig_bar)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_b:
        st.markdown("**Trend Summary**")
        display_trends = trends[["event_type", "direction", "pct_change", "avg_monthly"]].copy()
        display_trends.columns = ["Event Type", "Trend", "% Change", "Avg/Month"]
        display_trends["% Change"] = display_trends["% Change"].apply(lambda x: f"{x:+.1f}%")
        st.dataframe(display_trends, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Forecast method: ordinary least-squares linear trend fit on monthly counts. "
    "Confidence bands = ±1.96 × residual standard deviation. "
    "Minimum 6 months of history required per event type."
)
