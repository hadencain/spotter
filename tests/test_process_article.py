import extractor


def _row(headline, text="", url="http://x/1"):
    return {"id": "raw1", "headline": headline, "raw_text": text, "source": "GNews",
            "source_url": url, "published_at": "2026-07-01T14:00:00+00:00"}


def test_non_candidate_gets_zero_retail_score(monkeypatch):
    monkeypatch.setattr(extractor, "is_retail_candidate", lambda t: False)
    inc = extractor.process_article(_row("Armed robbery at a bank in Dallas, TX"), llm_client=object())
    assert inc["retail_score"] == 0.0
    assert inc["event_key"]  # always set


def test_candidate_enriches_with_entities(monkeypatch):
    monkeypatch.setattr(extractor, "is_retail_candidate", lambda t: True)
    monkeypatch.setattr(extractor.enrich, "fetch_body", lambda url: "full body text")
    monkeypatch.setattr(extractor, "_llm_extract_entities", lambda h, b, c: {
        "city": "Columbus", "state": "OH", "incident_type": "robbery", "retail_score": 0.9,
        "retailer": "Nordstrom", "loss_value": "~$120k", "suspect_count": 15,
        "mo": "flash-mob grab", "arrested": 0,
    })
    inc = extractor.process_article(_row("Flash-mob hits Nordstrom"), llm_client=object())
    assert inc["retailer"] == "Nordstrom"
    assert inc["retail_score"] == 0.9
    assert inc["city"] == "Columbus" and inc["state"] == "OH"
    assert inc["location_raw"] == "Columbus, OH"
    assert inc["event_key"]
    assert inc["suspect_count"] == 15
    assert inc["mo"] == "flash-mob grab"
    assert inc["arrested"] == 0
    assert inc["loss_value"] == "~$120k"
    assert inc["incident_type"] == "robbery"
    assert inc["severity"] == extractor.SEVERITY_MAP["robbery"]


def test_partial_llm_entity_preserves_regex_location(monkeypatch):
    monkeypatch.setattr(extractor, "is_retail_candidate", lambda t: True)
    monkeypatch.setattr(extractor.enrich, "fetch_body", lambda url: "body")
    monkeypatch.setattr(extractor, "_llm_extract_entities", lambda h, b, c: {
        "city": "", "state": "OH", "incident_type": "robbery", "retail_score": 0.8,
        "retailer": "", "loss_value": "", "suspect_count": None, "mo": "", "arrested": None,
    })
    inc = extractor.process_article(_row("Robbery at store in Columbus, OH"), llm_client=object())
    assert inc["city"] == "Columbus"   # regex city preserved, not wiped by empty LLM city
    assert inc["state"] == "OH"
    assert inc["location_raw"] == "Columbus, OH"


def test_run_extraction_persists_new_columns(temp_db, monkeypatch):
    conn = temp_db.get_conn()
    conn.execute(
        "INSERT INTO raw_articles (id, source, source_url, headline, published_at, ingested_at, raw_text, processed) "
        "VALUES ('r1','GNews','http://x/1','Smash and grab at Nordstrom store',"
        "'2026-07-01T00:00:00+00:00','2026-07-01T00:00:00+00:00','body',0)"
    )
    conn.commit(); conn.close()
    monkeypatch.setattr(extractor, "is_retail_candidate", lambda t: True)
    monkeypatch.setattr(extractor.enrich, "fetch_body", lambda url: "body")
    monkeypatch.setattr(extractor, "_make_llm_client", lambda: object())
    monkeypatch.setattr(extractor, "_llm_extract_entities", lambda h, b, c: {
        "city": "Columbus", "state": "OH", "incident_type": "robbery", "retail_score": 0.9,
        "retailer": "Nordstrom", "loss_value": "~$120k", "suspect_count": 15,
        "mo": "smash-and-grab", "arrested": 0,
    })
    extractor.run_extraction(use_llm=True)
    conn = temp_db.get_conn()
    row = conn.execute(
        "SELECT retail_score, retailer, event_key, mo, suspect_count FROM incidents"
    ).fetchone()
    conn.close()
    assert row["retailer"] == "Nordstrom"
    assert row["retail_score"] == 0.9
    assert row["mo"] == "smash-and-grab"
    assert row["suspect_count"] == 15
    assert row["event_key"]
