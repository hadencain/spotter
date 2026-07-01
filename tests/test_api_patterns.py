import importlib
import pytest


@pytest.fixture
def client(temp_db):
    import app as app_module
    importlib.reload(app_module)
    return app_module, app_module.app.test_client()


def _insert(db, **kw):
    cols = ", ".join(kw); ph = ", ".join(f":{k}" for k in kw)
    conn = db.get_conn()
    conn.execute(f"INSERT INTO incidents ({cols}) VALUES ({ph})", kw)
    conn.commit(); conn.close()


def test_patterns_group_by_retailer(client, temp_db):
    for i, st in enumerate(["OH", "TX"]):
        _insert(temp_db, id=f"n{i}", headline=f"h{i}", event_key=f"E{i}", retailer="Nordstrom",
                mo="flash-mob grab", state=st, city="City", retail_score=0.9, incident_type="robbery",
                severity=3, published_at=f"2026-07-0{i+1}T00:00:00+00:00", tags="[]")
    _, c = client
    data = c.get("/api/patterns?since=all").get_json()
    retailer_clusters = [cl for cl in data["clusters"] if cl["kind"] == "retailer"]
    assert retailer_clusters and retailer_clusters[0]["key"] == "Nordstrom"
    assert retailer_clusters[0]["count"] == 2
    assert set(retailer_clusters[0]["states"]) == {"OH", "TX"}


def test_patterns_omit_singletons(client, temp_db):
    _insert(temp_db, id="s1", headline="h", event_key="E9", retailer="Solo Store", mo="",
            state="CA", city="LA", retail_score=0.9, incident_type="theft",
            severity=3, published_at="2026-07-01T00:00:00+00:00", tags="[]")
    _, c = client
    data = c.get("/api/patterns?since=all").get_json()
    assert all(cl["key"] != "Solo Store" for cl in data["clusters"])


def test_patterns_mo_cluster(client, temp_db):
    for i, st in enumerate(["OH", "TX"]):
        _insert(temp_db, id=f"m{i}", headline=f"h{i}", event_key=f"M{i}", retailer="",
                mo="flash-mob grab", state=st, city="City", retail_score=0.9, severity=3,
                incident_type="robbery", published_at=f"2026-07-0{i+1}T00:00:00+00:00", tags="[]")
    _, c = client
    data = c.get("/api/patterns?since=all").get_json()
    mo_clusters = [cl for cl in data["clusters"] if cl["kind"] == "mo"]
    assert mo_clusters and mo_clusters[0]["key"] == "flash-mob grab"
    assert mo_clusters[0]["count"] == 2
    assert set(mo_clusters[0]["states"]) == {"OH", "TX"}


def test_patterns_dedup_counts_events_not_rows(client, temp_db):
    _insert(temp_db, id="d1", headline="outlet a", event_key="EV1", retailer="Nordstrom", mo="",
            state="OH", city="Columbus", retail_score=0.9, severity=3, incident_type="robbery",
            published_at="2026-07-01T00:00:00+00:00", tags="[]")
    _insert(temp_db, id="d2", headline="outlet b", event_key="EV1", retailer="Nordstrom", mo="",
            state="OH", city="Columbus", retail_score=0.9, severity=3, incident_type="robbery",
            published_at="2026-07-01T06:00:00+00:00", tags="[]")
    _insert(temp_db, id="d3", headline="second event", event_key="EV2", retailer="Nordstrom", mo="",
            state="TX", city="Dallas", retail_score=0.9, severity=3, incident_type="robbery",
            published_at="2026-07-02T00:00:00+00:00", tags="[]")
    _, c = client
    data = c.get("/api/patterns?since=all").get_json()
    r = [cl for cl in data["clusters"] if cl["kind"] == "retailer" and cl["key"] == "Nordstrom"]
    assert r and r[0]["count"] == 2  # 2 distinct EVENTS (EV1's two outlets collapse), not 3 rows


def test_patterns_case_insensitive_grouping(client, temp_db):
    for i, (ret, st) in enumerate([("Target", "OH"), ("target", "TX")]):
        _insert(temp_db, id=f"t{i}", headline=f"h{i}", event_key=f"T{i}", retailer=ret, mo="",
                state=st, city="City", retail_score=0.9, severity=3, incident_type="theft",
                published_at=f"2026-07-0{i+1}T00:00:00+00:00", tags="[]")
    _, c = client
    data = c.get("/api/patterns?since=all").get_json()
    tgt = [cl for cl in data["clusters"] if cl["kind"] == "retailer" and cl["key"].lower() == "target"]
    assert len(tgt) == 1 and tgt[0]["count"] == 2  # "Target"/"target" merged into one cluster


def test_patterns_incident_ids_returned(client, temp_db):
    for i, st in enumerate(["OH", "TX"]):
        _insert(temp_db, id=f"z{i}", headline=f"h{i}", event_key=f"Z{i}", retailer="Zales", mo="",
                state=st, city="City", retail_score=0.9, severity=3, incident_type="robbery",
                published_at=f"2026-07-0{i+1}T00:00:00+00:00", tags="[]")
    _, c = client
    data = c.get("/api/patterns?since=all").get_json()
    z = next(cl for cl in data["clusters"] if cl["key"] == "Zales")
    assert set(z["incident_ids"]) == {"z0", "z1"}
