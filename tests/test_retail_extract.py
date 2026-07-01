import json

import pytest

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


def test_full_payload_asserts_all_fields():
    payload = {
        "city": "Columbus", "state": "OH", "incident_type": "robbery",
        "retail_score": 0.94, "retailer": "Nordstrom", "loss_value": "~$120k",
        "suspect_count": 15, "mo": "flash-mob grab", "arrested": 0,
    }
    out = extractor._llm_extract_entities("h", "b", _client(json.dumps(payload)))
    assert out == payload


def test_strips_markdown_code_fence():
    payload = {"city": "Austin", "state": "TX", "incident_type": "theft", "retail_score": 0.6,
               "retailer": "Target", "loss_value": "", "suspect_count": None, "mo": "", "arrested": None}
    fenced = "```json\n" + json.dumps(payload) + "\n```"
    out = extractor._llm_extract_entities("h", "b", _client(fenced))
    assert out["retailer"] == "Target" and out["state"] == "TX"


@pytest.mark.parametrize("body", ["42", "null", "[1, 2]", '"just a string"'])
def test_non_dict_json_returns_default(body):
    out = extractor._llm_extract_entities("h", "b", _client(body))
    assert out["retail_score"] == 0.0 and out["retailer"] == "" and out["incident_type"] == "general"


def test_state_full_name_normalized_to_abbrev():
    payload = {"city": "Cleveland", "state": "Ohio", "incident_type": "assault", "retail_score": 0.5,
               "retailer": "", "loss_value": "", "suspect_count": None, "mo": "", "arrested": None}
    out = extractor._llm_extract_entities("h", "b", _client(json.dumps(payload)))
    assert out["state"] == "OH"


def test_invalid_incident_type_falls_back_to_general():
    payload = {"city": "", "state": "", "incident_type": "kerfuffle", "retail_score": 0.3,
               "retailer": "", "loss_value": "", "suspect_count": None, "mo": "", "arrested": None}
    out = extractor._llm_extract_entities("h", "b", _client(json.dumps(payload)))
    assert out["incident_type"] == "general"


def test_retail_score_clamped_and_coerced():
    high = {"city": "", "state": "", "incident_type": "theft", "retail_score": 1.4,
            "retailer": "", "loss_value": "", "suspect_count": None, "mo": "", "arrested": None}
    assert extractor._llm_extract_entities("h", "b", _client(json.dumps(high)))["retail_score"] == 1.0
    bad = {"city": "", "state": "", "incident_type": "theft", "retail_score": "high",
           "retailer": "", "loss_value": "", "suspect_count": None, "mo": "", "arrested": None}
    assert extractor._llm_extract_entities("h", "b", _client(json.dumps(bad)))["retail_score"] == 0.0
