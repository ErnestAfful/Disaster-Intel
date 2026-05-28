"""
Trend forecasting module — Phase 5.

Forecasts the next 3 months of event counts per event type using a
linear trend fit (numpy.polyfit) on monthly aggregates.  No external
ML dependencies — numpy + pandas only.

Public API
----------
forecast_event_counts(df, months_ahead=3)
    Returns (history_df, forecast_df, trend_df)

trend_direction(df, months_ahead=3)
    Returns a DataFrame with one row per event type:
    event_type | slope | direction | pct_change
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _monthly_counts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate df into monthly event counts per event type.
    Returns columns: month_str (YYYY-MM), event_type, count, month_idx (int).
    """
    work = df.copy()
    # Ensure tz-naive datetime
    if hasattr(work["event_date"].dtype, "tz") and work["event_date"].dtype.tz is not None:
        work["event_date"] = work["event_date"].dt.tz_convert(None)

    work["month_str"] = work["event_date"].dt.to_period("M").dt.strftime("%Y-%m")

    monthly = (
        work.groupby(["month_str", "event_type"])["id"]
        .count()
        .reset_index(name="count")
    )

    # Assign a sequential integer index to months (needed for polyfit)
    all_months = sorted(monthly["month_str"].unique())
    month_to_idx = {m: i for i, m in enumerate(all_months)}
    monthly["month_idx"] = monthly["month_str"].map(month_to_idx)

    return monthly, all_months


def _next_months(last_month_str: str, n: int) -> list[str]:
    """Return n month strings (YYYY-MM) following last_month_str."""
    period = pd.Period(last_month_str, freq="M")
    return [(period + i + 1).strftime("%Y-%m") for i in range(n)]


# ── Public functions ────────────────────────────────────────────────────────────

def forecast_event_counts(
    df: pd.DataFrame,
    months_ahead: int = 3,
    min_months: int = 6,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Fit a linear trend to each event type's monthly counts and project forward.

    Parameters
    ----------
    df           : enriched events DataFrame (needs event_date, event_type, id)
    months_ahead : how many future months to forecast
    min_months   : minimum months of history needed to fit a trend (skip otherwise)

    Returns
    -------
    history_df  : monthly counts (columns: month_str, event_type, count)
    forecast_df : forecast rows   (columns: month_str, event_type, count, lower, upper)
    trend_df    : fitted trend     (columns: month_str, event_type, trend)
    """
    monthly, all_months = _monthly_counts(df)
    last_month = all_months[-1]
    future_months = _next_months(last_month, months_ahead)
    n_history = len(all_months)

    history_rows  = []
    forecast_rows = []
    trend_rows    = []

    for etype, grp in monthly.groupby("event_type"):
        grp = grp.sort_values("month_idx")

        if len(grp) < min_months:
            logger.debug(f"Skipping {etype}: only {len(grp)} months of data.")
            continue

        x = grp["month_idx"].values.astype(float)
        y = grp["count"].values.astype(float)

        # Fit linear trend
        coeffs = np.polyfit(x, y, deg=1)   # [slope, intercept]
        slope, intercept = coeffs

        # Residual std for confidence interval
        y_fit = np.polyval(coeffs, x)
        residuals = y - y_fit
        std_res = residuals.std()

        # History actuals
        for _, row in grp.iterrows():
            history_rows.append({
                "month_str":  row["month_str"],
                "event_type": etype,
                "count":      int(row["count"]),
            })
            trend_rows.append({
                "month_str":  row["month_str"],
                "event_type": etype,
                "trend":      max(0.0, round(float(np.polyval(coeffs, row["month_idx"])), 1)),
            })

        # Future forecast
        for i, future_month in enumerate(future_months):
            future_idx = n_history + i  # extends integer axis
            pred = max(0.0, float(np.polyval(coeffs, future_idx)))
            forecast_rows.append({
                "month_str":  future_month,
                "event_type": etype,
                "count":      round(pred, 1),
                "lower":      max(0.0, round(pred - 1.96 * std_res, 1)),
                "upper":      round(pred + 1.96 * std_res, 1),
            })

    history_df  = pd.DataFrame(history_rows)
    forecast_df = pd.DataFrame(forecast_rows)
    trend_df    = pd.DataFrame(trend_rows)

    return history_df, forecast_df, trend_df


def trend_direction(
    df: pd.DataFrame,
    months_ahead: int = 3,
    min_months: int = 6,
) -> pd.DataFrame:
    """
    Return a summary of trend direction per event type.

    Columns: event_type | slope | direction | pct_change | avg_monthly
    direction: "↑ Increasing" | "↓ Decreasing" | "→ Stable"
    """
    monthly, all_months = _monthly_counts(df)
    rows = []

    for etype, grp in monthly.groupby("event_type"):
        grp = grp.sort_values("month_idx")
        if len(grp) < min_months:
            continue

        x = grp["month_idx"].values.astype(float)
        y = grp["count"].values.astype(float)
        coeffs = np.polyfit(x, y, deg=1)
        slope = float(coeffs[0])

        avg = float(y.mean())
        pct_change = (slope * months_ahead / avg * 100) if avg > 0 else 0.0

        if abs(pct_change) < 5:
            direction = "→ Stable"
        elif pct_change > 0:
            direction = "↑ Increasing"
        else:
            direction = "↓ Decreasing"

        rows.append({
            "event_type":  etype,
            "slope":       round(slope, 3),
            "direction":   direction,
            "pct_change":  round(pct_change, 1),
            "avg_monthly": round(avg, 1),
        })

    return pd.DataFrame(rows).sort_values("pct_change", ascending=False).reset_index(drop=True)
