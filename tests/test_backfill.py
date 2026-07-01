import extractor


def _seed(db, headline, url):
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO incidents (id, headline, source_url, published_at, incident_type, severity, retail_score) "
        "VALUES (?, ?, ?, ?, 'general', 1, 0)",
        ("i1", headline, url, "2026-07-01T00:00:00+00:00"),
    )
    conn.commit(); conn.close()


def test_backfill_populates_retail_fields(temp_db, monkeypatch):
    _seed(temp_db, "Smash and grab at Zales jewelry store", "http://x/1")
    monkeypatch.setattr(extractor, "_make_llm_client", lambda: object())
    monkeypatch.setattr(extractor, "is_retail_candidate", lambda t: True)
    monkeypatch.setattr(extractor.enrich, "fetch_body", lambda url: "body")
    monkeypatch.setattr(extractor, "_llm_extract_entities", lambda h, b, c: {
        "city": "Houston", "state": "TX", "incident_type": "robbery", "retail_score": 0.88,
        "retailer": "Zales", "loss_value": "~$85k", "suspect_count": 4, "mo": "smash-and-grab", "arrested": 0,
    })
    extractor.run_retail_backfill()
    conn = temp_db.get_conn()
    row = conn.execute("SELECT retail_score, retailer, event_key, state FROM incidents WHERE id='i1'").fetchone()
    conn.close()
    assert row["retailer"] == "Zales"
    assert row["retail_score"] == 0.88
    assert row["state"] == "TX"
    assert row["event_key"]


def test_backfill_converges_no_rebill(temp_db, monkeypatch):
    _seed(temp_db, "Smash and grab at Zales jewelry store", "http://x/1")
    calls = {"n": 0}
    monkeypatch.setattr(extractor, "_make_llm_client", lambda: object())
    monkeypatch.setattr(extractor, "is_retail_candidate", lambda t: True)
    monkeypatch.setattr(extractor.enrich, "fetch_body", lambda url: "body")
    def fake_entities(h, b, c):
        calls["n"] += 1
        return {"city": "Houston", "state": "TX", "incident_type": "robbery", "retail_score": 0.0,
                "retailer": "Zales", "loss_value": "", "suspect_count": None, "mo": "", "arrested": None}
    monkeypatch.setattr(extractor, "_llm_extract_entities", fake_entities)
    extractor.run_retail_backfill()
    extractor.run_retail_backfill()  # second run must not re-bill the already-processed row
    assert calls["n"] == 1
