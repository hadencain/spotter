import extractor


def _row(headline, text="", url="http://x/1"):
    return {"id": "raw1", "headline": headline, "raw_text": text, "source": "GNews",
            "source_url": url, "published_at": "2026-07-01T14:00:00+00:00"}


def test_non_candidate_gets_zero_retail_score(monkeypatch):
    monkeypatch.setattr(extractor, "is_retail_candidate", lambda t: False)
    inc = extractor.process_article(_row("Highway pileup on I-20"), llm_client=object())
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
