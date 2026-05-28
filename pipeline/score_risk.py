"""
Risk scoring module — Phase 4.

Computes a composite risk score (0-100) for each event using four components:

    1. Event type severity   (40 pts max)  — how destructive is this event class?
    2. Weather severity      (25 pts max)  — extreme heat / wind / precipitation
    3. Air quality impact    (20 pts max)  — PM2.5 levels at the event location
    4. Population exposure   (15 pts max)  — proxy via country population lookup

All components are normalised before combining so the final score always
sits in [0, 100].
"""
import logging
import math
import pandas as pd
from pipeline.database import get_events_without_risk_score, save_risk_scores

logger = logging.getLogger(__name__)

# 1. Event-type severity weights 
# Scale: 1 (minor) → 5 (catastrophic). Multiplied by 8 → max 40 pts.
TYPE_SEVERITY = {
    "Volcanoes":         5,
    "Severe Storms":     4,
    "Wildfires":         4,
    "Floods":            4,
    "Earthquakes":       4,
    "Landslides":        3,
    "Sea and Lake Ice":  2,
    "Dust and Haze":     2,
    "Snow":              2,
    "Manmade":           3,
    "Water Color":       1,
    "Temperature Extremes": 3,
}
_DEFAULT_SEVERITY = 2  # fallback for unknown types

#2. Population lookup (country ISO-2 → millions)
# Top ~60 countries by population; others fall back to a regional median.
# Source: UN 2023 estimates (rounded to nearest million).
COUNTRY_POP_M = {
    "IN": 1430, "CN": 1410, "US": 335,  "ID": 277,  "PK": 230,
    "BR": 215,  "NG": 220,  "BD": 170,  "RU": 144,  "ET": 126,
    "MX": 130,  "EG": 105,  "CD": 100,  "PH":  115, "VN":  98,
    "TH":  72,  "TR":  85,  "IR":  87,  "DE":  84,  "FR":  68,
    "GB":  68,  "TZ":  63,  "ZA":  60,  "KE":  55,  "MM":  54,
    "CO":  51,  "KR":  52,  "ES":  47,  "UG":  48,  "AR":  46,
    "UA":  44,  "DZ":  45,  "SD":  46,  "IQ":  42,  "AF":  40,
    "PL":  38,  "CA":  38,  "MZ":  33,  "GH":  32,  "PE":  33,
    "AU":  26,  "CI":  27,  "NP":  30,  "MG":  28,  "CM":  27,
    "VE":  29,  "NL":  17,  "CL":  19,  "RO":  19,  "MW":  20,
    "ZM":  19,  "SS":  11,  "CF":   5,  "JP": 125,  "IT":  60,
    "SN":  17,  "ML":  22,  "BF":  22,  "NE":  26,  "TD":  17,
    "AO":  35,  "MR":   4,  "LY":   7,  "TN":  12,  "MA":  37,
}
_DEFAULT_POP_M = 15  # fallback for unknown countries

# Rough lat/lon bounding boxes → country ISO-2 for geolocating without geocoder
# Used only as a last resort for events whose title doesn't carry a country hint.
# We use a simple point-in-bbox approach for the most common disaster countries.
_BBOX_COUNTRY = [
    # (lat_min, lat_max, lon_min, lon_max, iso2)
    (8,  37,   68,  97, "IN"),
    (18, 53,   73, 135, "CN"),
    (24, 49, -125, -66, "US"),
    (-11, 5,   95, 141, "ID"),
    (24, 37,   61,  77, "PK"),
    (-34, 5,  -73, -35, "BR"),
    (4,  14,    3,  15, "NG"),
    (20, 27,   88,  92, "BD"),
    (41, 82,   27, 180, "RU"),
    (3,  15,   33,  48, "ET"),
    (15, 33,  -117, -87, "MX"),
    (22, 32,   25,  37, "EG"),
    (-5, 5,    12,  31, "CD"),
    (4,  21,  115, 127, "PH"),
    (8,  23,  102, 110, "VN"),
    (5,  21,   98, 106, "TH"),
    (36, 42,   26,  45, "TR"),
    (25, 40,   44,  63, "IR"),
    (-22, -8, -75, -68, "PE"),
    (-56, -17, -73, -53, "AR"),
    (-44, -10, 113, 154, "AU"),
]

def _country_from_coords(lat: float, lon: float) -> str:
    """Best-effort country ISO-2 from a lat/lon point using bounding boxes."""
    for lat_min, lat_max, lon_min, lon_max, iso2 in _BBOX_COUNTRY:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return iso2
    return "XX"  # unknown

def _population_score(lat, lon) -> float:
    """Return 0-15 pts based on country population (log-scaled)."""
    iso2 = _country_from_coords(lat, lon)
    pop_m = COUNTRY_POP_M.get(iso2, _DEFAULT_POP_M)
    # log10(1M) = 6, log10(1.4B) ≈ 9.15  → normalise to [0,1] in that range
    score_norm = (math.log10(max(pop_m, 1)) - math.log10(1)) / (math.log10(1430) - math.log10(1))
    return round(min(score_norm, 1.0) * 15, 2)

def _weather_score(temp_max, windspeed_max, precipitation) -> float:
    """Return 0–25 pts based on weather severity."""
    pts = 0.0

    # Temperature: ≥45°C = max heat contribution (10 pts).
    # Values < -100 are API sentinel/error codes — treat as missing.
    # Cold temps don't add risk in this model (floor at 0).
    if pd.notna(temp_max) and float(temp_max) > -100:
        pts += min(max(0.0, float(temp_max)) / 45.0, 1.0) * 10

    # Wind: ≥120 km/h = max wind contribution (10 pts)
    if pd.notna(windspeed_max) and float(windspeed_max) >= 0:
        pts += min(float(windspeed_max) / 120.0, 1.0) * 10

    # Precipitation: ≥100 mm/day = max rain contribution (5 pts)
    if pd.notna(precipitation) and float(precipitation) >= 0:
        pts += min(float(precipitation) / 100.0, 1.0) * 5

    return round(min(pts, 25.0), 2)

def _aqi_score(pm25, station_name) -> float:
    """Return 0-20 pts based on PM2.5. No station → 0."""
    if pd.isna(pm25) or station_name == "NONE_FOUND" or pd.isna(station_name):
        return 0.0
    # WHO 24-hr limit = 15 µg/m³; hazardous ≥ 250 µg/m³
    return round(min(float(pm25) / 250.0, 1.0) * 20, 2)

def score_event(row: pd.Series) -> float:
    """Compute composite risk score (0–100) for a single event row."""
    # Component 1: type severity (0–40)
    severity = TYPE_SEVERITY.get(row.get("event_type", ""), _DEFAULT_SEVERITY)
    type_score = severity * 8  # max 5*8 = 40

    # Component 2: weather (0–25)
    weather = _weather_score(
        row.get("temperature_max"),
        row.get("windspeed_max"),
        row.get("precipitation"),
    )

    # Component 3: AQI (0–20)
    aqi = _aqi_score(row.get("pm25"), row.get("station_name"))

    # Component 4: population exposure (0–15)
    pop = _population_score(
        row.get("latitude", 0) or 0,
        row.get("longitude", 0) or 0,
    )

    total = type_score + weather + aqi + pop
    return round(max(0.0, min(total, 100.0)), 2)

def score_all_events(force: bool = False) -> int:
    """
    Score all unscored events (or all events if force=True).
    Returns the number of events scored.
    """
    if force:
        from pipeline.database import engine
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("UPDATE events SET risk_score = NULL"))
        logger.info("Cleared all existing risk scores (force mode).")

    df = get_events_without_risk_score()
    if df.empty:
        logger.info("All events already have risk scores.")
        return 0

    scores = {}
    for _, row in df.iterrows():
        scores[row["id"]] = score_event(row)

    save_risk_scores(scores)
    logger.info(f"Risk scoring complete — {len(scores)} events scored.")
    return len(scores)
