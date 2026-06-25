import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "intel.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS raw_articles (
                id          TEXT PRIMARY KEY,
                source      TEXT NOT NULL,
                source_url  TEXT NOT NULL UNIQUE,
                headline    TEXT,
                published_at TEXT,
                ingested_at TEXT NOT NULL,
                raw_text    TEXT,
                processed   INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS incidents (
                id            TEXT PRIMARY KEY,
                headline      TEXT,
                source        TEXT,
                source_url    TEXT,
                published_at  TEXT,
                ingested_at   TEXT,
                raw_text      TEXT,
                location_raw  TEXT,
                lat           REAL,
                lng           REAL,
                city          TEXT,
                state         TEXT,
                incident_type TEXT,
                severity      INTEGER,
                tags          TEXT,
                reviewed      INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS geocode_cache (
                location_raw TEXT PRIMARY KEY,
                lat          REAL,
                lng          REAL,
                resolved_at  TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_raw_processed ON raw_articles(processed);
            CREATE INDEX IF NOT EXISTS idx_incidents_published ON incidents(published_at);
        """)


if __name__ == "__main__":
    init_db()
    print(f"database initialized at {DB_PATH}")
