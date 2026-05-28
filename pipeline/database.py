#the database needs to do 3 things 
#1: events: Store the cleaned EONET data (od. title, event_type, lat, lon, date, status)
#2: Weather: Stores weather data linked to events by the id 
#3: Air quality: Stores AQI data linked to events by the id. 
import logging
import pandas as pd 
from sqlalchemy import create_engine, text 
from pipeline.config import DATABASE_URL, DATA_DIR 

logger = logging.getLogger(__name__)
# Database Engine 
DATA_DIR.mkdir(parents=True, exist_ok=True)
engine = create_engine(DATABASE_URL, echo=False)
# using raw SQL to create tables
EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    id        TEXT PRIMARY KEY,
    title           TEXT,
    event_type      TEXT,
    event_date      TIMESTAMP,
    latitude        REAL,
    longitude       REAL,
    status          TEXT,
    closed          TEXT,
    geometry_count  INTEGER,
    link            TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
)
"""
WEATHER_TABLE = """
CREATE TABLE IF NOT EXISTS weather (
    event_id    TEXT PRIMARY KEY,
    temperature_max REAL,
    temperature_min REAL,
    precipitation   REAL,
    windspeed_max REAL,
    humidity       REAL,
    fetched_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(event_id) REFERENCES events(id)
)
"""
AQI_TABLE = """
CREATE TABLE IF NOT EXISTS air_quality (
    event_id    TEXT PRIMARY KEY,
    pm25       REAL,
    pm10       REAL,
    o3         REAL,
    no2        REAL,
    so2        REAL,
    station_name TEXT,
    fetched_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(event_id) REFERENCES events(id)
)
"""
def init_db():

    logger.info("Initialize the database tables")
    with engine.begin() as conn:
        conn.execute(text(EVENTS_TABLE))
        conn.execute(text(WEATHER_TABLE))
        conn.execute(text(AQI_TABLE))
        # Migration: add risk_score if it doesn't exist yet
        try:
            conn.execute(text("ALTER TABLE events ADD COLUMN risk_score REAL"))
            logger.info("Migration: added risk_score column to events table.")
        except Exception:
            pass  # Column already exists — safe to ignore
    logger.info("Database tables is ready.")   

#functions
def upsert_events(df): 
    #handles hourly updates of events, if the event already exists, update the record, otherwise insert a new record.
    if df.empty:
        logger.warning("No events data to upsert.")
        return 0, 0 
    inserted = 0
    updated = 0
    
    # Getting existing event ids from the database
    existing_ids = get_existing_event_ids()
    with engine.begin() as conn:
        for _, row in df.iterrows():
            if row ["id"] in existing_ids: 
                #Event exist, update the record
                conn.execute(
                    text(
                        """
                        UPDATE events
                        SET status = :status, 
                            latitude = :latitude,
                            longitude = :longitude, 
                            closed = :closed,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = :id
                        """), 
                        { 
                        "id":       row["id"],
                        "status":    row.get("status"),
                        "latitude":  row["latitude"],
                        "longitude": row["longitude"],
                        "closed":    row.get("closed"),
                    },
                )
                updated += 1
            else:
                #Event does not exist, insert a new record
                conn.execute(
                    text("""
                        INSERT INTO events (id, title, event_type, event_date,
                            latitude, longitude, status, geometry_count,
                            closed, link)
                        VALUES (:id, :title, :event_type, :event_date,
                            :latitude, :longitude, :status, :geometry_count,
                            :closed, :link)
                    """),
                    {
                        "id":             row["id"],
                        "title":          row.get("title"),
                        "event_type":     row.get("event_type"),
                        "event_date":     str(row.get("event_date")),
                        "latitude":       row["latitude"],
                        "longitude":      row["longitude"],
                        "status":         row.get("status"),
                        "geometry_count": row.get("geometry_count"),
                        "closed":         row.get("closed"),
                        "link":           row.get("link"),
                    },
                )
                inserted += 1

    logger.info(f"Upsert complete — {inserted} inserted, {updated} updated")
    return inserted, updated

def get_existing_event_ids(): 
    with engine.connect() as conn: 
        result = conn.execute(text("SELECT id FROM events"))
        return {row[0] for row in result} 

def get_events_without_weather():
    query = """
            SELECT e.id, e.latitude, e.longitude, e.event_date, e.event_type
            FROM events e
            LEFT JOIN weather w ON e.id = w.event_id
            WHERE w.event_id IS NULL
            ORDER BY e.event_date ASC
            """
    with engine.connect() as conn:
        df = pd.read_sql_query(text(query), conn)
    logger.info(f"Found {len(df)} events without weather data.")
    return df 

def get_events_without_aqi(north_america_only=False):
    bbox_filter = ""
    if north_america_only:
        bbox_filter = """
            AND e.latitude  BETWEEN 15.0 AND 72.0
            AND e.longitude BETWEEN -168.0 AND -52.0
        """
    query = f"""
            SELECT e.id, e.latitude, e.longitude, e.event_date, e.event_type
            FROM events e
            LEFT JOIN air_quality a ON e.id = a.event_id
            WHERE a.event_id IS NULL
            {bbox_filter}
            """
    with engine.connect() as conn:
        df = pd.read_sql_query(text(query), conn)
    region = "North America" if north_america_only else "global"
    logger.info(f"Found {len(df)} events without AQI data ({region}).")
    return df

def save_weather(event_id, weather_data): 
    with engine.begin() as conn: 
        conn.execute(
            text("DELETE FROM weather WHERE event_id = :event_id"), {"event_id": event_id}
)
        conn.execute(
            text("""
                INSERT INTO weather (event_id, temperature_max, temperature_min,
                     precipitation, windspeed_max, humidity)
                VALUES (:event_id, :temperature_max, :temperature_min,
                    :precipitation, :windspeed_max, :humidity)
            """),
            {"event_id": event_id, **weather_data},
        )
def save_aqi(event_id, aqi_data):
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM air_quality WHERE event_id = :event_id"),
            {"event_id": event_id}
        ) 
        conn.execute(
            text("""
                INSERT INTO air_quality (event_id, pm25, pm10, no2, so2, o3,
                    station_name)
                VALUES (:event_id, :pm25, :pm10, :no2, :so2, :o3,
                    :station_name)
            """),
            {"event_id": event_id, **aqi_data},
        ) 
def get_events_without_risk_score():
    """Return events that haven't been scored yet."""
    query = """
        SELECT e.id, e.event_type, e.latitude, e.longitude, e.event_date,
               w.temperature_max, w.windspeed_max, w.precipitation,
               a.pm25, a.station_name
        FROM events e
        LEFT JOIN weather w ON e.id = w.event_id
        LEFT JOIN air_quality a ON e.id = a.event_id
        WHERE e.risk_score IS NULL
    """
    with engine.connect() as conn:
        df = pd.read_sql_query(text(query), conn)
    logger.info(f"Found {len(df)} events without risk scores.")
    return df

def save_risk_scores(scores: dict):
    """
    Bulk-save risk scores.
    scores: {event_id: score_float}
    """
    with engine.begin() as conn:
        for event_id, score in scores.items():
            conn.execute(
                text("UPDATE events SET risk_score = :score WHERE id = :id"),
                {"score": score, "id": event_id},
            )
    logger.info(f"Saved {len(scores)} risk scores.")

def get_all_events():
    #Return a DataFrame of all events in the database. 
    with engine.connect() as conn:
        df = pd.read_sql_query(text("SELECT * FROM events"), conn)
    return df
def enriched_events(): 
    #the master query
    query = """
            SELECT
                e.id, e.title, e.event_type, e.event_date,
                e.latitude, e.longitude, e.status, e.closed,
                e.geometry_count, e.link, e.created_at, e.updated_at,
                e.risk_score,
                w.temperature_max,
                w.temperature_min,
                w.precipitation,
                w.windspeed_max,
                w.humidity,
                a.pm25,
                a.pm10,
                a.no2,
                a.so2,
                a.o3,
                a.station_name
            FROM events e 
            LEFT JOIN weather w ON e.id = w.event_id
            LEFT JOIN air_quality a ON e.id = a.event_id
            """
    with engine.connect() as conn:
        df = pd.read_sql_query(text(query), conn)
    logger.info(f"Retrieved {len(df)} enriched events.")
    return df
