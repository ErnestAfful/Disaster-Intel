"""
Fetch natural disaster events from NASA EONET API.

This module handles ONLY the API call and raw JSON extraction.
It does NOT clean, transform, or save anything — that's clean_events.py's job.
"""

import logging
import requests
import pandas as pd
from pipeline.config import EONET_BASE_URL, NASA_API_KEY, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


def fetch_eonet_events(
    days=None,
    start=None,
    end=None,
    status="all",
    limit=10000,
):
    """
    Pull events from NASA EONET API.

    Two modes:
        - Incremental:  pass days=1  (for hourly pipeline runs)
        - Historical:   pass start="2020-01-01", end="2026-03-31"  (for backfill)

    Args:
        days:    Number of days to look back (use this OR start/end, not both)
        start:   Start date string "YYYY-MM-DD" (for historical pulls)
        end:     End date string "YYYY-MM-DD" (for historical pulls)
        status:  "open", "closed", or "all"
        limit:   Max events to return

    Returns:
        pd.DataFrame with raw event data, or empty DataFrame on failure
    """

    # Build params — only include what's specified
    params = {
        "limit": limit,
        "status": status,
    }

    if NASA_API_KEY:
        params["api_key"] = NASA_API_KEY

    # Incremental mode vs historical mode
    if days is not None:
        params["days"] = days
    elif start and end:
        params["start"] = start
        params["end"] = end

    logger.info(f"Fetching EONET events with params: {params}")

    try:
        response = requests.get(
            EONET_BASE_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        data = response.json()
        events = data.get("events", [])

        logger.info(f"Fetched {len(events)} events from EONET")

        if not events:
            logger.warning("No events returned from EONET")
            return pd.DataFrame()

        # Log first and last for quick sanity check
        logger.info(f"First event: {events[0]['title']}")
        logger.info(f"Last event:  {events[-1]['title']}")

        return pd.DataFrame(events)

    except requests.exceptions.RequestException as e:
        logger.error(f"EONET API request failed: {e}")
        return pd.DataFrame()
