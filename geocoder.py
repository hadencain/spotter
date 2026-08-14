import time
from datetime import datetime, timezone

import requests

from db import get_conn
from user_agent import USER_AGENT

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
RATE_LIMIT_SECONDS = 1.1  # Nominatim requires >= 1 req/sec


def _now():
    return datetime.now(timezone.utc).isoformat()


def _nominatim_lookup(location_raw):
    """Query Nominatim for a location string. Returns (lat, lng) or (None, None). Rate-limited."""
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
    finally:
        time.sleep(RATE_LIMIT_SECONDS)
    return None, None


def _cache_store(conn, location_raw: str, lat, lng):
    conn.execute(
        "INSERT OR REPLACE INTO geocode_cache (location_raw, lat, lng, resolved_at) VALUES (?, ?, ?, ?)",
        (location_raw, lat, lng, _now()),
    )


def resolve_with_confidence(location_raw, city, state, lookup=_nominatim_lookup):
    """Try point -> city centroid -> state centroid. Returns (lat, lng, confidence)."""
    if location_raw and location_raw.strip():
        lat, lng = lookup(location_raw)
        if lat is not None:
            return lat, lng, "point"
    if city and state:
        lat, lng = lookup(f"{city}, {state}")
        if lat is not None:
            return lat, lng, "city"
    if state and state.strip():
        lat, lng = lookup(state)
        if lat is not None:
            return lat, lng, "state"
    return None, None, "none"


def geocode_incidents(limit: int = 5000):
    conn = get_conn()
    rows = conn.execute(
        """SELECT id, location_raw, city, state FROM incidents
           WHERE lat IS NULL AND (location_raw != '' OR state != '')
           LIMIT ?""",
        (limit,),
    ).fetchall()

    if not rows:
        print("no incidents need geocoding")
        conn.close()
        return

    def cached_lookup(q):
        if not q or not q.strip():
            return None, None
        cached = conn.execute(
            "SELECT lat, lng FROM geocode_cache WHERE location_raw = ?", (q,)
        ).fetchone()
        if cached is not None:
            return cached["lat"], cached["lng"]
        lat, lng = _nominatim_lookup(q)
        _cache_store(conn, q, lat, lng)
        return lat, lng

    resolved = 0
    failed = 0
    for row in rows:
        lat, lng, conf = resolve_with_confidence(
            row["location_raw"], row["city"], row["state"], lookup=cached_lookup
        )
        conn.execute(
            "UPDATE incidents SET lat = ?, lng = ?, geo_confidence = ? WHERE id = ?",
            (lat, lng, conf, row["id"]),
        )
        if lat is not None:
            resolved += 1
        else:
            failed += 1

    conn.commit()
    conn.close()
    print(f"geocoding done — {resolved} resolved, {failed} failed")


if __name__ == "__main__":
    geocode_incidents()
