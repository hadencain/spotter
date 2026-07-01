import importlib

import pytest


@pytest.fixture
def client(temp_db):
    import app as app_module
    importlib.reload(app_module)
    return app_module.app.test_client()


def _insert(db, **kw):
    cols = ", ".join(kw)
    ph = ", ".join(f":{k}" for k in kw)
    conn = db.get_conn()
    conn.execute(f"INSERT INTO incidents ({cols}) VALUES ({ph})", kw)
    conn.commit()
    conn.close()


def test_stats_reports_retail_totals(client, temp_db):
    _insert(temp_db, id="r1", event_key="A", retail_score=0.9, severity=5, incident_type="robbery", tags="[]")
    _insert(temp_db, id="r2", event_key="B", retail_score=0.2, severity=5, incident_type="theft", tags="[]")
    data = client.get("/api/stats").get_json()
    assert data["retail_total"] == 1
    assert data["high_sev"] == 1


def test_stats_counts_are_deduped(client, temp_db):
    _insert(temp_db, id="e1", event_key="EV", retail_score=0.9, severity=5, incident_type="robbery",
            published_at="2026-07-01T00:00:00+00:00", tags="[]")
    _insert(temp_db, id="e2", event_key="EV", retail_score=0.9, severity=5, incident_type="robbery",
            published_at="2026-07-01T06:00:00+00:00", tags="[]")
    data = client.get("/api/stats").get_json()
    assert data["total"] == 1        # deduped: one event, not two rows
    assert data["retail_total"] == 1


def test_high_sev_requires_severity_threshold(client, temp_db):
    # retail but LOW severity -> counts in retail_total, NOT high_sev
    _insert(temp_db, id="hs1", event_key="A", retail_score=0.9, severity=2, incident_type="theft", tags="[]")
    _insert(temp_db, id="hs2", event_key="B", retail_score=0.9, severity=5, incident_type="robbery", tags="[]")
    data = client.get("/api/stats").get_json()
    assert data["retail_total"] == 2   # both are retail
    assert data["high_sev"] == 1       # only the severity>=4 one


def test_stats_counts_null_event_key_individually(client, temp_db):
    _insert(temp_db, id="n1", event_key=None, retail_score=0.9, severity=5, incident_type="robbery", tags="[]")
    _insert(temp_db, id="n2", event_key=None, retail_score=0.9, severity=5, incident_type="robbery", tags="[]")
    data = client.get("/api/stats").get_json()
    assert data["total"] == 2          # NULL event_key rows counted separately, never merged
    assert data["retail_total"] == 2


def test_by_type_is_deduped(client, temp_db):
    _insert(temp_db, id="t1", event_key="EV", retail_score=0.9, severity=5, incident_type="robbery",
            published_at="2026-07-01T00:00:00+00:00", tags="[]")
    _insert(temp_db, id="t2", event_key="EV", retail_score=0.9, severity=5, incident_type="robbery",
            published_at="2026-07-01T06:00:00+00:00", tags="[]")
    _insert(temp_db, id="t3", event_key="EV2", retail_score=0.9, severity=5, incident_type="theft",
            published_at="2026-07-02T00:00:00+00:00", tags="[]")
    data = client.get("/api/stats").get_json()
    assert data["by_type"].get("robbery") == 1   # EV's two outlets collapse to one event
    assert data["by_type"].get("theft") == 1
    assert data["total"] == 2


def test_geocoded_deduped_and_threshold_boundary(client, temp_db):
    _insert(temp_db, id="g1", event_key="A", retail_score=0.4, severity=5, incident_type="theft",
            lat=1.0, lng=2.0, tags="[]")
    _insert(temp_db, id="g2", event_key="B", retail_score=0.39, severity=5, incident_type="theft", tags="[]")
    data = client.get("/api/stats").get_json()
    assert data["geocoded"] == 1        # only g1 has lat
    assert data["retail_total"] == 1    # 0.4 >= threshold counts, 0.39 does not (boundary)
