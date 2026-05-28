"""
AQI enrichment via OpenAQ v3.

For each event without air quality data, this module:
  1. Finds the nearest monitoring station within 25 km
  2. Fetches daily readings for PM2.5, PM10, O3, NO2, SO2 on the event date
  3. Saves the results to the air_quality table

Events with no station nearby are saved with NULL pollutant values and
station_name = "NONE_FOUND" so they are not retried on every run.

Usage (called automatically by main.py, but can be run standalone):
    python -m pipeline.enrich_aqi
"""

import time
import logging
import requests
from pipeline.config import (
    AQI_BATCH_SIZE,
    MAX_RETRIES,
    OPENAQ_BASE_URL,
    OPENAQ_API_KEY,
    REQUEST_TIMEOUT,
)
from pipeline.database import get_events_without_aqi, save_aqi
from pipeline.request_cache import get_cached_session

logger = logging.getLogger(__name__)

# Pollutants I care about: must match OpenAQ parameter names
TARGET_PARAMETERS = ["pm25", "pm10", "o3", "no2", "so2"]

# How far from the event to search for a monitoring station (metres)
SEARCH_RADIUS_M = 25_000  # 25 km — OpenAQ v3 hard cap

def _headers():
    """Build the request headers, including the API key if set."""
    h = {"Accept": "application/json"}
    if OPENAQ_API_KEY:
        h["X-API-Key"] = OPENAQ_API_KEY
    return h

def _find_nearest_location(latitude, longitude):
    """
    Return the nearest OpenAQ location within SEARCH_RADIUS_M that has at
    least one of our target parameters.  Returns (location_id, station_name,
    sensors_dict) or (None, None, {}) when nothing is found.

    sensors_dict maps parameter name → sensor_id, e.g.
        {"pm25": 12345, "no2": 67890}
    """
    params = {
        "coordinates": f"{latitude},{longitude}",
        "radius": SEARCH_RADIUS_M,
        "limit": 5,
    }
    session = get_cached_session()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(
                f"{OPENAQ_BASE_URL}/locations",
                params=params,
                headers=_headers(),
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            results = response.json().get("results", [])

            for loc in results:
                sensors = {}
                for sensor in loc.get("sensors", []):
                    param_name = (
                        sensor.get("parameter", {}).get("name", "").lower()
                    )
                    if param_name in TARGET_PARAMETERS:
                        sensors[param_name] = sensor["id"]

                if sensors:  #at least one useful parameter
                    return loc["id"], loc.get("name", "unknown"), sensors

            return None, None, {}  #no usable station nearby

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            body = e.response.text[:300] if e.response is not None else "no body"
            if status == 429:
                wait = 10 * attempt  # 10s, 20s, 30s — back off hard on rate limit
                logger.warning(f"Rate limited on location lookup (attempt {attempt}/{MAX_RETRIES}), sleeping {wait}s")
                time.sleep(wait)
            else:
                logger.warning(
                    f"Location lookup failed (attempt {attempt}/{MAX_RETRIES}): {e} | body: {body}"
                )
                if attempt < MAX_RETRIES:
                    time.sleep(attempt)
        except requests.RequestException as e:
            logger.warning(
                f"Location lookup failed (attempt {attempt}/{MAX_RETRIES}): {e}"
            )
            if attempt < MAX_RETRIES:
                time.sleep(attempt)

    # Return a sentinel that signals "rate-limited/failed" — not a genuine no-station result
    return "RATE_LIMITED", None, {}

def _fetch_sensor_daily_value(sensor_id, date_str):
    """
    Return the average daily value for one sensor on a given date (YYYY-MM-DD).
    Returns None if no measurements are found or the request fails.
    """
    #OpenAQ v3 daily aggregates endpoint
    url = f"{OPENAQ_BASE_URL}/sensors/{sensor_id}/measurements/daily"
    params = {
        "date_from": f"{date_str}T00:00:00Z",
        "date_to": f"{date_str}T23:59:59Z",
        "limit": 1,
    }
    session = get_cached_session()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(
                url,
                params=params,
                headers=_headers(),
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                #daily endpoint returns a summary value field
                return results[0].get("value")
            return None

        except requests.RequestException as e:
            logger.warning(
                f"Sensor {sensor_id} fetch failed (attempt {attempt}/{MAX_RETRIES}): {e}"
            )
            if attempt < MAX_RETRIES:
                time.sleep(attempt)
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Unexpected AQI response format for sensor {sensor_id}: {e}")
            return None

    return None

def get_aqi_for_event(latitude, longitude, event_date):
    """
    Fetch AQI data for a single event location and date.

    Returns a dict ready to pass to save_aqi(), or None on hard failure.
    When no station is found, returns a dict with all-NULL pollutants and
    station_name = 'NONE_FOUND' so the event is not retried.
    """
    date_str = str(event_date)[:10]  # YYYY-MM-DD

    location_id, station_name, sensors = _find_nearest_location(latitude, longitude)

    if location_id == "RATE_LIMITED":
        # Don't save anything — let the event be retried next round
        logger.warning(f"Skipping ({latitude:.3f}, {longitude:.3f}) on {date_str} — rate limited, will retry")
        return None

    if not location_id:
        logger.info(
            f"No AQI station within {SEARCH_RADIUS_M // 1000} km of "
            f"({latitude:.3f}, {longitude:.3f}) on {date_str}"
        )
        return {
            "pm25": None,
            "pm10": None,
            "o3": None,
            "no2": None,
            "so2": None,
            "station_name": "NONE_FOUND",
        }

    #Fetch each pollutant value from its sensor
    readings = {}
    for param in TARGET_PARAMETERS:
        sensor_id = sensors.get(param)
        if sensor_id:
            readings[param] = _fetch_sensor_daily_value(sensor_id, date_str)
            time.sleep(0.05)  # brief pause between sensor requests
        else:
            readings[param] = None  # station doesn't measure this pollutant

    logger.debug(
        f"AQI for ({latitude:.3f}, {longitude:.3f}) on {date_str} "
        f"from '{station_name}': {readings}"
    )

    return {
        "pm25": readings.get("pm25"),
        "pm10": readings.get("pm10"),
        "o3": readings.get("o3"),
        "no2": readings.get("no2"),
        "so2": readings.get("so2"),
        "station_name": station_name,
    }


def enrich_missing_aqi(
    batch_size=AQI_BATCH_SIZE,
    north_america_only=True,
    run_until_done=False,
    max_rounds=None,
):
    """
    Enrich one AQI batch by default, or keep looping in backfill mode.

    north_america_only: restrict to lat 15-72, lon -168--52 (default True).
    OpenAQ coverage is sparse outside North America, so global mode burns
    API calls on NONE_FOUND results.
    run_until_done: process every currently missing AQI row when True.
    """
    total_enriched = 0
    round_num = 0

    while True:
        if max_rounds is not None and round_num >= max_rounds:
            logger.warning(
                f"Stopping AQI enrichment after {max_rounds} rounds. "
                f"Total processed this run: {total_enriched}"
            )
            break

        all_events = get_events_without_aqi(north_america_only=north_america_only)
        remaining = len(all_events)

        if all_events.empty:
            logger.info(
                f"All events processed for AQI! Total enriched this run: {total_enriched}"
            )
            break

        round_num += 1
        batch = all_events.head(batch_size)
        logger.info(
            f"[AQI Round {round_num}] Processing {len(batch)} of {remaining} remaining events..."
        )

        enriched = 0
        for _, event in batch.iterrows():
            aqi_data = get_aqi_for_event(
                event["latitude"], event["longitude"], event["event_date"]
            )
            if aqi_data is not None:
                save_aqi(event["id"], aqi_data)
                #Count as enriched even if NONE_FOUND then it was processed
                enriched += 1
            time.sleep(0.5)  # ~2 events/sec — stays under OpenAQ rate limit

        total_enriched += enriched
        logger.info(
            f"[AQI Round {round_num}] {enriched}/{len(batch)} processed. "
            f"{remaining - len(batch)} still pending."
        )

        if enriched == 0:
            logger.warning(
                "Stopping AQI enrichment because this round saved 0 rows. "
                "This usually means OpenAQ is rate-limiting or consistently failing."
            )
            break

        if not run_until_done:
            break

if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    enrich_missing_aqi()
