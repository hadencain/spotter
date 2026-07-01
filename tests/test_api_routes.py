import importlib
import pytest


@pytest.fixture
def client(temp_db):
    import app as app_module
    importlib.reload(app_module)
    app_module.app.config["TESTING"] = True
    return app_module, app_module.app.test_client()


def _insert(db, **kw):
    cols = ", ".join(kw); ph = ", ".join(f":{k}" for k in kw)
    conn = db.get_conn()
    conn.execute(f"INSERT INTO incidents ({cols}) VALUES ({ph})", kw)
    conn.commit(); conn.close()


def test_incidents_dedup_by_event_key(client, temp_db):
    for i in range(3):
        _insert(temp_db, id=f"a{i}", headline=f"outlet {i}", event_key="EK1", lat=1.0, lng=2.0,
                retail_score=0.9, severity=4, incident_type="robbery",
                published_at=f"2026-07-0{i+1}T00:00:00+00:00", tags="[]")
    _insert(temp_db, id="b0", headline="other", event_key="EK2", lat=1.0, lng=2.0,
            retail_score=0.5, severity=3, incident_type="theft", published_at="2026-07-01T00:00:00+00:00", tags="[]")
    _, c = client
    data = c.get("/api/incidents?since=all").get_json()
    assert data["count"] == 2  # EK1 collapsed to one + EK2
    ek1 = next(i for i in data["incidents"] if i["event_key"] == "EK1")
    assert ek1["n_sources"] == 3
    assert ek1["headline"] == "outlet 2"  # most recent representative


def test_incidents_retail_first_order(client, temp_db):
    _insert(temp_db, id="low", headline="low", event_key="L", lat=1.0, lng=2.0,
            retail_score=0.1, severity=5, incident_type="theft", published_at="2026-07-02T00:00:00+00:00", tags="[]")
    _insert(temp_db, id="high", headline="high", event_key="H", lat=1.0, lng=2.0,
            retail_score=0.95, severity=2, incident_type="robbery", published_at="2026-07-01T00:00:00+00:00", tags="[]")
    _, c = client
    data = c.get("/api/incidents?since=all").get_json()
    assert data["incidents"][0]["id"] == "high"  # retail_score wins over severity
