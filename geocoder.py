import time
from datetime import datetime, timezone

import requests

from db import get_conn

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "MallIntelPlatform/0.1 (security-research-tool)"
RATE_LIMIT_SECONDS = 1.1  # Nominatim requires >= 1 req/sec


def _now():
    return datetime.now(timezone.utc).isoformat()


def _nominatim_lookup(location_raw: str) -> tuple[float, float] | tuple[None, None]:
    """Query Nominatim for a location string. Returns (lat, lng) or (None, None)."""
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": location_raw, "format": "json", "limit": 1, "countrycodes": "us"},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"  nominatim error for '{location_raw}': {e}")
    return None, None


def _cache_lookup(conn, location_raw: str) -> tuple[float, float] | tuple[None, None]:
    row = conn.execute(
        "SELECT lat, lng FROM geocode_cache WHERE location_raw = ?", (location_raw,)
    ).fetchone()
    if row:
        return row["lat"], row["lng"]
    return None, None


def _cache_store(conn, location_raw: str, lat, lng):
    conn.execute(
        "INSERT OR REPLACE INTO geocode_cache (location_raw, lat, lng, resolved_at) VALUES (?, ?, ?, ?)",
        (location_raw, lat, lng, _now()),
    )


def geocode_incidents(limit: int = 5000):
    conn = get_conn()

    rows = conn.execute(
        """SELECT id, location_raw FROM incidents
           WHERE lat IS NULL AND location_raw != '' AND location_raw IS NOT NULL
           LIMIT ?""",
        (limit,),
    ).fetchall()

    if not rows:
        print("no incidents need geocoding")
        return

    resolved = 0
    failed = 0
    cached = 0

    for row in rows:
        loc = row["location_raw"]

        # Check cache first
        lat, lng = _cache_lookup(conn, loc)
        if lat is not None:
            cached += 1
        else:
            lat, lng = _nominatim_lookup(loc)
            _cache_store(conn, loc, lat, lng)
            time.sleep(RATE_LIMIT_SECONDS)

        if lat is not None:
            conn.execute(
                "UPDATE incidents SET lat = ?, lng = ? WHERE id = ?",
                (lat, lng, row["id"]),
            )
            resolved += 1
        else:
            failed += 1

    conn.commit()
    conn.close()
    print(f"geocoding done — {resolved} resolved ({cached} from cache), {failed} failed")


if __name__ == "__main__":
    geocode_incidents()
