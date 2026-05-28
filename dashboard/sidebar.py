"""
Shared sidebar component.

Each page imports and calls render_sidebar(df) to get consistent
filter controls. Returns the three filter values for apply_filters().
"""

import streamlit as st
import pandas as pd


def render_sidebar(df: pd.DataFrame) -> tuple:
    """
    Render the filter sidebar and return (event_types, date_range, statuses).

    Args:
        df: Full unfiltered enriched DataFrame (used to derive options)

    Returns:
        Tuple of (event_types list, date_range tuple, statuses list)
    """
    st.sidebar.title("disaster-intel")
    st.sidebar.caption("NASA EONET enriched event data")
    st.sidebar.divider()

    st.sidebar.header("Filters")

    # ── Event type ────────────────────────────────────────────────
    all_types = sorted(df["event_type"].dropna().unique().tolist())
    event_types = st.sidebar.multiselect(
        "Event Type",
        options=all_types,
        default=all_types,
    )

    # ── Date range ────────────────────────────────────────────────
    min_date = df["event_date"].min().date()
    max_date = df["event_date"].max().date()
    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    # ── Status ────────────────────────────────────────────────────
    statuses = st.sidebar.multiselect(
        "Status",
        options=["active", "closed"],
        default=["active", "closed"],
    )

    st.sidebar.divider()
    st.sidebar.caption("Filters apply to all charts on this page.")

    return event_types, date_range, statuses
