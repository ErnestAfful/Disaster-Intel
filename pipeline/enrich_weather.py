import time
import logging
import requests
from pipeline.config import (
    MAX_RETRIES,
    NASA_POWER_DAILY_URL,
    REQUEST_TIMEOUT,
    WEATHER_BATCH_SIZE,
)
from pipeline.database import get_events_without_weather, save_weather
from pipeline.request_cache import get_cached_session

logger = logging.getLogger(__name__) 

DAILY_WEATHER_VARIABLES = [
    "T2M_MAX",
    "T2M_MIN",
    "PRECTOTCORR",
    "WS10M",
    "RH2M",
]

def get_weather_for_event (latitude, longitude, event_date):
    date_str = str(event_date)[:10].replace("-", "")
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start": date_str,
        "end": date_str,
        "parameters": ",".join(DAILY_WEATHER_VARIABLES),
        "community": "AG",
        "format": "JSON",
        "time-standard": "UTC",
    }
    session = get_cached_session()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(NASA_POWER_DAILY_URL, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            daily = data.get("properties", {}).get("parameter")
            if not daily:
                logger.warning(
                    f"No daily weather data found for lat={latitude}, lon={longitude} on {event_date}"
                )
                return None
            return {
                "temperature_max": daily["T2M_MAX"][date_str],
                "temperature_min": daily["T2M_MIN"][date_str],
                "precipitation": daily["PRECTOTCORR"][date_str],
                "windspeed_max": daily["WS10M"][date_str],
                "humidity": daily["RH2M"][date_str],
            }
        except requests.RequestException as e:
            logger.warning(
                f"Weather request failed for {date_str} (attempt {attempt}/{MAX_RETRIES}): {e}"
            )
            if attempt < MAX_RETRIES:
                time.sleep(attempt)
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Unexpected weather response format: {e}")
            return None
    return None

def enrich_missing_weather(batch_size=WEATHER_BATCH_SIZE, run_until_done=False, max_rounds=None):
    """Enrich one weather batch by default, or keep looping in backfill mode."""
    total_enriched = 0
    round_num = 0

    while True:
        if max_rounds is not None and round_num >= max_rounds:
            logger.warning(
                f"Stopping weather enrichment after {max_rounds} rounds. "
                f"Total enriched this run: {total_enriched}"
            )
            break

        all_events = get_events_without_weather()
        remaining = len(all_events)

        if all_events.empty:
            logger.info(f"All events enriched! Total enriched this run: {total_enriched}")
            break

        round_num += 1
        batch = all_events.head(batch_size)
        logger.info(f"[Round {round_num}] Enriching {len(batch)} of {remaining} remaining events...")

        enriched = 0
        for _, event in batch.iterrows():
            weather_data = get_weather_for_event(
                event["latitude"], event["longitude"], event["event_date"]
            )
            if weather_data:
                save_weather(event["id"], weather_data)
                enriched += 1
            time.sleep(0.1)

        total_enriched += enriched
        logger.info(f"[Round {round_num}] {enriched}/{len(batch)} enriched. {remaining - len(batch)} still pending.")

        if enriched == 0:
            logger.warning(
                "Stopping weather enrichment because this round saved 0 rows. "
                "This usually means the weather API is consistently failing or returning no usable data."
            )
            break

        if not run_until_done:
            break
