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
