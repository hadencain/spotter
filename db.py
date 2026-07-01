import os
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "intel.db"


def _db_path() -> Path:
    """Resolve the DB path at call time so tests can override via SPOTTER_DB."""
    override = os.environ.get("SPOTTER_DB")
    return Path(override) if override else DB_PATH


def get_conn():
    conn = sqlite3.connect(_db_path())
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
        """)

        existing = {r[1] for r in conn.execute("PRAGMA table_info(incidents)")}

        # Create index for published_at only if column exists
        if "published_at" in existing:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_published ON incidents(published_at)")

        # Add new columns idempotently
        additions = {
            "retail_score":   "REAL DEFAULT 0",
            "retailer":       "TEXT",
            "loss_value":     "TEXT",
            "suspect_count":  "INTEGER",
            "mo":             "TEXT",
            "arrested":       "INTEGER",
            "event_key":      "TEXT",
            "geo_confidence": "TEXT",
        }
        for col, decl in additions.items():
            if col not in existing:
                try:
                    conn.execute(f"ALTER TABLE incidents ADD COLUMN {col} {decl}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        raise
        conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_retail ON incidents(retail_score)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_event  ON incidents(event_key)")
        conn.commit()


if __name__ == "__main__":
    init_db()
    print(f"database initialized at {DB_PATH}")
