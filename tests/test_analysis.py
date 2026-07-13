"""Offline tests for the temporal-spatial analysis layer. No network, no key."""
import importlib
from datetime import datetime, timedelta, timezone

import pytest

import analysis
from analysis import (
    CAVEAT, bearing_deg, cardinal, cell_of, haversine_km, is_hour_reliable,
    mo_match, mo_similarity, mo_tokens, solar_hour, trend_label, _parse_dt,
)

NOW = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)


def _iso(days_ago, hour=14, minute=37):
    return (NOW - timedelta(days=days_ago)).replace(hour=hour, minute=minute, second=0).isoformat()


def _insert(db, **kw):
    kw.setdefault("tags", "[]")
    cols = ", ".join(kw); ph = ", ".join(f":{k}" for k in kw)
    conn = db.get_conn()
    conn.execute(f"INSERT INTO incidents ({cols}) VALUES ({ph})", kw)
    conn.commit(); conn.close()


def _point(db, id, lat, lng, days_ago=2, **kw):
    kw.setdefault("severity", 3)
    kw.setdefault("incident_type", "theft")
    kw.setdefault("published_at", _iso(days_ago))
    _insert(db, id=id, lat=lat, lng=lng, geo_confidence="point", **kw)


# ── pure functions ───────────────────────────────────────────────────────────

def test_haversine_la_to_sf():
    assert abs(haversine_km(34.0522, -118.2437, 37.7749, -122.4194) - 559) < 10


def test_bearing_and_cardinal():
    assert cardinal(bearing_deg(34.0, -118.0, 36.0, -118.0)) == "N"
    assert cardinal(bearing_deg(34.0, -118.0, 34.0, -116.0)) == "E"


@pytest.mark.parametrize("cur,prev,label", [
    (3, 0, "emerging"), (2, 0, "new"), (3, 2, "rising"),
    (2, 3, "cooling"), (2, 2, "stable"), (3, 3, "stable"),
])
def test_trend_labels(cur, prev, label):
    assert trend_label(cur, prev) == label


def test_mo_matching():
    a = mo_tokens("smash-and-grab, multiple suspects")
    b = mo_tokens("smash and grab crew")
    assert mo_match(a, b)                                     # extra descriptors tolerated
    assert not mo_match(a, mo_tokens("shoplifting concealment"))
    assert not mo_match(a, frozenset())
    assert mo_match(mo_tokens("shoplifting"), mo_tokens("shoplifting"))  # identical 1-token MO
    assert not mo_match(mo_tokens("armed robbery"), mo_tokens("armed suspects fled"))  # 1 shared ≠ link
    assert mo_similarity(a, b) == pytest.approx(2 / 3)


def test_hour_reliable_detection():
    assert not is_hour_reliable(_parse_dt("2026-07-01T07:00:00+00:00"))  # date-only artifact
    assert is_hour_reliable(_parse_dt("2026-07-01T07:13:22+00:00"))
    assert not is_hour_reliable(None)


def test_solar_hour_shift():
    dt = _parse_dt("2026-07-01T20:00:00+00:00")
    assert solar_hour(dt, -120.0) == 12  # UTC-8-ish longitude → local noon


def test_cell_binning_stable_at_borders():
    assert cell_of(34.049999, -118.0) == cell_of(34.045, -118.0)
    assert cell_of(34.050001, -118.0) != cell_of(34.049999, -118.0)


# ── seeded-DB behavior ───────────────────────────────────────────────────────

def test_hotspot_ranks_dense_cell_first(temp_db):
    for i in range(5):  # five points inside one ~5km cell
        _point(temp_db, f"hot{i}", 34.011 + i * 0.001, -118.211, days_ago=i + 1)
    _point(temp_db, "lone", 40.7, -74.0)
    conn = temp_db.get_conn()
    res = analysis.hotspots(conn, since="30d", now=NOW)
    conn.close()
    assert res["caveat"] == CAVEAT
    assert len(res["cells"]) == 1  # lone point never makes a cell (count < 2)
    top = res["cells"][0]
    assert top["count"] == 5
    assert abs(top["lat"] - 34.011) < 0.05


def test_hotspot_excludes_centroid_and_dedups(temp_db):
    _point(temp_db, "p1", 34.011, -118.211, event_key="EK1")
    _point(temp_db, "p2", 34.012, -118.212, event_key="EK1")  # same event, twice reported
    _point(temp_db, "p3", 34.013, -118.213, event_key="EK2")
    _insert(temp_db, id="centroid", lat=34.012, lng=-118.212, geo_confidence="state",
            severity=3, incident_type="theft", published_at=_iso(1))
    _insert(temp_db, id="legacy", lat=34.012, lng=-118.212, geo_confidence=None,
            severity=3, incident_type="theft", published_at=_iso(1))
    conn = temp_db.get_conn()
    res = analysis.hotspots(conn, since="30d", now=NOW)
    conn.close()
    assert res["cells"][0]["count"] == 2  # EK1 once + EK2; centroid/legacy excluded


def test_hotspot_trend_null_for_all_window(temp_db):
    _point(temp_db, "a", 34.011, -118.211)
    _point(temp_db, "b", 34.012, -118.212)
    conn = temp_db.get_conn()
    res = analysis.hotspots(conn, since="all", now=NOW)
    conn.close()
    assert res["cells"][0]["trend"] is None


def test_heatmap_points_and_slices(temp_db):
    _point(temp_db, "a", 34.011, -118.211, days_ago=1)
    _point(temp_db, "b", 34.012, -118.212, days_ago=9)  # different ISO week
    conn = temp_db.get_conn()
    res = analysis.heatmap(conn, since="30d", now=NOW)
    conn.close()
    assert len(res["points"]) == 2
    assert len(res["slices"]) == 2
    assert all(len(p) == 3 for p in res["points"])


def test_temporal_suppresses_hours_below_threshold(temp_db):
    for i in range(10):
        _point(temp_db, f"r{i}", 34.0 + i * 0.001, -118.2, days_ago=i % 7,
               published_at=_iso(i % 7, hour=19, minute=41))
    conn = temp_db.get_conn()
    res = analysis.temporal(conn, since="30d")
    conn.close()
    assert res["hour_reliable_n"] == 10
    assert res["hours_suppressed"] is True
    assert sum(res["dow"]) == 10


def test_temporal_date_only_rows_count_dow_not_hours(temp_db):
    _point(temp_db, "dateonly", 34.0, -118.2, published_at=_iso(1, hour=7, minute=0))
    conn = temp_db.get_conn()
    res = analysis.temporal(conn, since="30d")
    conn.close()
    assert sum(res["dow"]) == 1
    assert res["hour_reliable_n"] == 0


def test_tracks_reconstructs_marching_crew(temp_db):
    stops = [  # LA → Santa Barbara → San Luis Obispo → Santa Cruz, 2 days apart
        (34.0522, -118.2437, "Los Angeles"), (34.4208, -119.6982, "Santa Barbara"),
        (35.2828, -120.6596, "San Luis Obispo"), (36.9741, -122.0308, "Santa Cruz"),
    ]
    for i, (lat, lng, city) in enumerate(stops):
        _point(temp_db, f"t{i}", lat, lng, days_ago=(len(stops) - i) * 2,
               city=city, state="CA", mo="smash and grab, masked crew")
    conn = temp_db.get_conn()
    res = analysis.tracks(conn, since="60d")
    conn.close()
    assert res["caveat"] == CAVEAT
    assert len(res["tracks"]) == 1
    t = res["tracks"][0]
    assert t["n_stops"] == 4
    assert [s["id"] for s in t["stops"]] == ["t0", "t1", "t2", "t3"]
    assert t["kind"] == "mo"
    assert t["total_km"] > 400
    assert t["stops"][1]["km_from_prev"] > 100


def test_tracks_respects_hop_limits(temp_db):
    _point(temp_db, "a", 34.0, -118.2, days_ago=20, mo="smash and grab")
    _point(temp_db, "b", 34.1, -118.3, days_ago=1, mo="smash and grab")   # 19-day gap
    _point(temp_db, "c", 47.6, -122.3, days_ago=2, mo="smash and grab")   # >400 km away
    conn = temp_db.get_conn()
    res = analysis.tracks(conn, since="60d")
    conn.close()
    assert res["tracks"] == []


def test_tracks_retailer_link_beats_mo(temp_db):
    for i in range(3):
        _point(temp_db, f"r{i}", 34.0 + i * 0.2, -118.2, days_ago=6 - i * 2,
               retailer="Ulta Beauty", city=f"City{i}", state="CA")
    conn = temp_db.get_conn()
    res = analysis.tracks(conn, since="60d")
    conn.close()
    assert len(res["tracks"]) == 1
    assert res["tracks"][0]["kind"] == "retailer"
    assert res["tracks"][0]["signature"] == "Ulta Beauty"


def test_corridors_compose_and_rank(temp_db):
    for i in range(5):
        _point(temp_db, f"hot{i}", 34.011 + i * 0.001, -118.211, days_ago=i + 1,
               city="Los Angeles", state="CA")
    for i in range(3):
        _point(temp_db, f"trk{i}", 36.0 + i * 0.2, -115.1, days_ago=6 - i * 2,
               retailer="Target", city=f"NV City {i}", state="NV")
    conn = temp_db.get_conn()
    res = analysis.corridors(conn, since="30d", now=NOW)
    conn.close()
    assert res["caveat"] == CAVEAT
    kinds = {e["kind"] for e in res["corridors"]}
    assert "hotspot" in kinds and "track" in kinds
    assert [e["rank"] for e in res["corridors"]] == list(range(1, len(res["corridors"]) + 1))
    hotspot = next(e for e in res["corridors"] if e["kind"] == "hotspot")
    assert hotspot["timing"]["scope"] == "cell"  # 5 members → cell-local profile


def test_narrative_none_without_key(monkeypatch):
    monkeypatch.setattr(analysis, "AppConfig", None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    text, err = analysis.build_narrative({"corridors": []})
    assert text is None
    assert err == "no API key"


# ── API routes ───────────────────────────────────────────────────────────────

@pytest.fixture
def client(temp_db):
    import app as app_module
    importlib.reload(app_module)
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_analysis_routes_empty_db(client):
    for route in ("hotspots", "heatmap", "temporal", "tracks", "corridors"):
        res = client.get(f"/api/analysis/{route}?since=30d")
        assert res.status_code == 200
        assert res.get_json()["caveat"] == CAVEAT


def test_analysis_hotspots_route_filters(client, temp_db):
    _point(temp_db, "a", 34.011, -118.211, incident_type="robbery", retail_score=0.9)
    _point(temp_db, "b", 34.012, -118.212, incident_type="robbery", retail_score=0.9)
    _point(temp_db, "c", 34.013, -118.213, incident_type="theft", retail_score=0.0)
    data = client.get("/api/analysis/hotspots?since=30d&retail=1&type=robbery").get_json()
    assert data["cells"][0]["count"] == 2


def test_corridors_route_narrative_without_key(client, temp_db, monkeypatch):
    monkeypatch.setattr(analysis, "AppConfig", None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    data = client.get("/api/analysis/corridors?since=30d&narrative=1").get_json()
    assert data["narrative"] is None
    assert data["narrative_error"] == "no API key"
