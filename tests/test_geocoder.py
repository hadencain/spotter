import geocoder


def test_point_confidence_when_full_hits():
    def lookup(q):
        return (33.84, -84.37) if "Lenox" in q else (None, None)
    lat, lng, conf = geocoder.resolve_with_confidence("Lenox Square, Atlanta, GA", "Atlanta", "GA", lookup=lookup)
    assert conf == "point" and lat == 33.84


def test_city_confidence_falls_back_to_city_state():
    def lookup(q):
        return (33.75, -84.39) if q == "Atlanta, GA" else (None, None)
    lat, lng, conf = geocoder.resolve_with_confidence("Some Vague Place, Atlanta, GA", "Atlanta", "GA", lookup=lookup)
    assert conf == "city"
    assert (lat, lng) == (33.75, -84.39)


def test_state_confidence_when_only_state_resolves():
    def lookup(q):
        return (32.6, -83.4) if q == "GA" else (None, None)
    lat, lng, conf = geocoder.resolve_with_confidence("Atlanta, GA", "", "GA", lookup=lookup)
    assert conf == "state"
    assert (lat, lng) == (32.6, -83.4)


def test_none_when_nothing_resolves():
    lat, lng, conf = geocoder.resolve_with_confidence("", "", "", lookup=lambda q: (None, None))
    assert conf == "none" and lat is None


def test_geocode_incidents_writes_confidence_and_caches(temp_db, monkeypatch):
    conn = temp_db.get_conn()
    for i in range(2):
        conn.execute(
            "INSERT INTO incidents (id, headline, location_raw, city, state, incident_type, severity, tags) "
            "VALUES (?, 'h', 'Atlanta, GA', 'Atlanta', 'GA', 'robbery', 3, '[]')",
            (f"i{i}",),
        )
    conn.commit(); conn.close()
    calls = {"n": 0}
    def fake_nominatim(q):
        calls["n"] += 1
        return (33.75, -84.39) if q == "Atlanta, GA" else (None, None)
    monkeypatch.setattr(geocoder, "_nominatim_lookup", fake_nominatim)
    geocoder.geocode_incidents()
    conn = temp_db.get_conn()
    rows = conn.execute("SELECT lat, lng, geo_confidence FROM incidents ORDER BY id").fetchall()
    conn.close()
    assert all(r["geo_confidence"] == "point" and r["lat"] == 33.75 for r in rows)
    assert calls["n"] == 1  # identical second location served from geocode_cache, not re-queried
