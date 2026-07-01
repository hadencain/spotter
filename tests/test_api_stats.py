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
