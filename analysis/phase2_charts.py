"""
Phase 2 chart functions: enrichment-aware analysis.

Each function takes a DataFrame from analysis.queries and returns a
Plotly figure. Nothing here touches the database or calls queries
directly.

Research questions answered:
  Q6 — Do events cluster around specific weather conditions?
  Q7 — How do events affect local air quality?
  Q8 — Do disaster types have distinct weather fingerprints?
  Q9 — Do seasonal patterns hold up against actual climate data?
"""

import logging
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from analysis.theme import apply_theme, themed_colors, COLORS

logger = logging.getLogger(__name__)

# Q6: Weather conditions by event type 
def weather_conditions_by_type(df: pd.DataFrame) -> list:
    """
    Box plots showing the distribution of each weather variable
    across event types.

    Args:
        df: Output of queries.weather_profiles()

    Returns:
        List of 4 Plotly figures (one per variable):
          temperature_max, precipitation, windspeed_max, humidity
    """
    logger.info("Q6 — Generating weather conditions box plots...")

    variables = {
        "temperature_max": ("Max Temperature (°C)", "reds"),
        "precipitation":   ("Precipitation (mm)",   "blues"),
        "windspeed_max":   ("Max Wind Speed (km/h)", "greens"),
        "humidity":        ("Relative Humidity (%)", "purples"),
    }

    figs = []
    for col, (label, color_seq) in variables.items():
        if col not in df.columns:
            logger.warning(f"  Column '{col}' missing — skipping")
            continue
        fig = px.box(
            df,
            x="event_type",
            y=col,
            color="event_type",
            title=f"Q6 — {label} by Event Type",
            labels={"event_type": "Event Type", col: label},
            color_discrete_sequence=themed_colors(),
        )
        fig.update_layout(showlegend=False)
        apply_theme(fig)
        figs.append(fig)

    logger.info(f"  → {len(figs)} weather box plots created")
    return figs

# Q7: AQI impact by event type

def aqi_impact_by_type(df: pd.DataFrame) -> go.Figure:
    """
    Grouped bar chart of median pollutant levels per event type.
    Wildfires should show elevated PM2.5 and PM10.

    Args:
        df: Output of queries.aqi_by_event_type()

    Returns:
        Single Plotly figure
    """
    logger.info("Q7 — Generating AQI impact chart...")

    pollutants = {
        "pm25": "PM2.5 (μg/m³)",
        "pm10": "PM10 (μg/m³)",
        "o3":   "Ozone O3 (μg/m³)",
        "no2":  "NO2 (μg/m³)",
    }

    # Melt to long form for grouped bars
    available = [c for c in pollutants if c in df.columns]
    df_long = df.melt(
        id_vars="event_type",
        value_vars=available,
        var_name="pollutant",
        value_name="median_value",
    )
    df_long["pollutant_label"] = df_long["pollutant"].map(pollutants)

    fig = px.bar(
        df_long,
        x="event_type",
        y="median_value",
        color="pollutant_label",
        barmode="group",
        title="Q7 — Median Air Quality Pollutants by Event Type",
        labels={
            "event_type":    "Event Type",
            "median_value":  "Median Concentration (μg/m³)",
            "pollutant_label": "Pollutant",
        },
        color_discrete_sequence=themed_colors(),
    )
    apply_theme(fig)
    return fig

# Q8: Weather fingerprint radar chart 
def weather_signatures(df: pd.DataFrame) -> go.Figure:
    """
    Radar / spider chart showing the normalised weather profile for
    each event type. All 5 variables are scaled 0–1 so they're
    comparable on the same axes.

    Args:
        df: Output of queries.weather_signatures()

    Returns:
        Single Plotly figure
    """
    logger.info("Q8 — Generating weather signature radar chart...")

    weather_cols = ["temperature_max", "temperature_min",
                    "precipitation", "windspeed_max", "humidity"]
    axis_labels  = ["Max Temp", "Min Temp", "Precipitation",
                    "Max Wind", "Humidity"]

    available_cols   = [c for c in weather_cols if c in df.columns]
    available_labels = [axis_labels[weather_cols.index(c)] for c in available_cols]

    fig = go.Figure()

    for i, (_, row) in enumerate(df.iterrows()):
        values = [row[c] for c in available_cols]
        # Close the polygon
        values_closed = values + [values[0]]
        labels_closed = available_labels + [available_labels[0]]

        fig.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill="toself",
            name=row["event_type"],
            line=dict(color=COLORS[i % len(COLORS)], width=2),
            fillcolor=COLORS[i % len(COLORS)],
            opacity=0.5,
        ))

    fig.update_layout(
        title="Q8 — Weather Fingerprints by Disaster Type (Normalised 0–1)",
        paper_bgcolor="rgba(0,0,0,0)",
        polar=dict(
            bgcolor="#FFFFFF",
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                gridcolor="#c8d0dc",
                linecolor="#8a94a6",
                tickfont=dict(color="#1a1a2e"),
            ),
            angularaxis=dict(
                gridcolor="#c8d0dc",
                linecolor="#8a94a6",
                tickfont=dict(color="#1a1a2e", size=13),
            ),
        ),
        font=dict(color="#1a1a2e"),
        legend=dict(
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#c8d0dc",
            borderwidth=1,
            font=dict(color="#1a1a2e"),
        ),
        showlegend=True,
    )
    return fig

# Q9: Seasonal trends grounded in climate data 
def seasonal_climate_trends(df: pd.DataFrame) -> go.Figure:
    """
    Dual-axis chart: event counts per month (bars) overlaid with
    average maximum temperature and precipitation (lines).

    Shows whether seasonal event spikes align with climate conditions
    rather than just calendar months.

    Args:
        df: Output of queries.seasonal_enriched()

    Returns:
        Single Plotly figure
    """
    logger.info("Q9 — Generating seasonal climate trends chart...")

    # Aggregate across event types for the climate overlay
    monthly = (
        df.groupby("month")
        .agg(
            total_events=("event_count", "sum"),
            avg_temp=("avg_temperature_max", "mean"),
            avg_precip=("avg_precipitation", "mean"),
        )
        .reset_index()
        .sort_values("month")
    )

    # Per-type counts for stacked bars
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Stacked bars — one trace per event type
    event_types = df["event_type"].unique()
    colors = px.colors.qualitative.Plotly

    for i, etype in enumerate(event_types):
        type_df = df[df["event_type"] == etype].sort_values("month")
        fig.add_trace(
            go.Bar(
                x=type_df["month"],
                y=type_df["event_count"],
                name=etype,
                marker_color=COLORS[i % len(COLORS)],
                opacity=0.85,
            ),
            secondary_y=False,
        )
    # Temperature line
    fig.add_trace(
        go.Scatter(
            x=monthly["month"],
            y=monthly["avg_temp"],
            name="Avg Max Temp (°C)",
            line=dict(color="firebrick", width=2, dash="dot"),
            mode="lines+markers",
        ),
        secondary_y=True,
    )
    # Precipitation line
    fig.add_trace(
        go.Scatter(
            x=monthly["month"],
            y=monthly["avg_precip"],
            name="Avg Precipitation (mm)",
            line=dict(color="steelblue", width=2, dash="dash"),
            mode="lines+markers",
        ),
        secondary_y=True,
    )
    fig.update_layout(
        title="Q9 — Monthly Event Activity vs Climate Conditions",
        barmode="stack",
        xaxis_title="Month",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_yaxes(title_text="Number of Events", secondary_y=False)
    fig.update_yaxes(title_text="Temperature (°C) / Precipitation (mm)",
                     secondary_y=True)
    apply_theme(fig)
    return fig
