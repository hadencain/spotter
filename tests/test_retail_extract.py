import json

import extractor


def test_prefilter_flags_retail():
    assert extractor.is_retail_candidate("Shooting at Lenox Square Mall food court")
    assert extractor.is_retail_candidate("Smash and grab at a Walmart store")


def test_prefilter_rejects_nonretail():
    assert not extractor.is_retail_candidate("Highway pileup snarls morning commute")


def _client(text):
    """Stub Anthropic client whose messages.create() returns `text` as the response body."""
    msg = type("Msg", (), {
        "content": [type("C", (), {"text": text})()],
        "usage": type("U", (), {"input_tokens": 10, "output_tokens": 10})(),
    })()
    client = type("Client", (), {})()
    client.messages = type("M", (), {"create": staticmethod(lambda **k: msg)})()
    return client


def test_entity_extraction_parses_full_payload():
    payload = {
        "city": "Columbus", "state": "OH", "incident_type": "robbery",
        "retail_score": 0.94, "retailer": "Nordstrom", "loss_value": "~$120k",
        "suspect_count": 15, "mo": "flash-mob grab", "arrested": 0,
    }
    out = extractor._llm_extract_entities("Flash-mob crew hits Nordstrom", "body", _client(json.dumps(payload)))
    assert out["retailer"] == "Nordstrom"
    assert out["state"] == "OH"
    assert 0.9 <= out["retail_score"] <= 1.0
    assert out["suspect_count"] == 15
    assert out["arrested"] == 0


def test_entity_extraction_safe_default_on_garbage():
    out = extractor._llm_extract_entities("x", "y", _client("not json at all"))
    assert out["retail_score"] == 0.0
    assert out["retailer"] == ""
    assert out["incident_type"] in extractor.VALID_TYPES
