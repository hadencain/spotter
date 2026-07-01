import app


def test_retail_flag_adds_threshold_condition():
    conds, params = app._build_conditions({"retail": "1", "since": "all"})
    assert any("retail_score >=" in c for c in conds)
    assert 0.4 in params
    assert app.RETAIL_THRESHOLD == 0.4


def test_mapped_only_query_param_can_enable():
    conds, _ = app._build_conditions({"mapped_only": "1", "since": "all"}, mapped_only=False)
    assert "lat IS NOT NULL" in conds


def test_mapped_only_query_param_can_disable():
    conds, _ = app._build_conditions({"mapped_only": "0", "since": "all"}, mapped_only=True)
    assert "lat IS NOT NULL" not in conds


def test_serialize_includes_new_fields():
    row = {k: None for k in (
        "id headline source source_url published_at location_raw lat lng city state "
        "incident_type severity tags retail_score retailer loss_value suspect_count mo "
        "arrested geo_confidence event_key").split()}
    row["tags"] = "[]"
    out = app._serialize(row)
    for key in ("retail_score", "retailer", "mo", "arrested", "geo_confidence", "n_sources"):
        assert key in out
    assert out["n_sources"] == 1


def test_serialize_maps_fields_and_uses_present_n_sources():
    row = {
        "id": "x", "headline": "H", "source": "S", "source_url": "U",
        "published_at": "2026-07-01", "location_raw": "Columbus, OH",
        "lat": 1.0, "lng": 2.0, "city": "Columbus", "state": "OH",
        "incident_type": "robbery", "severity": 3, "tags": "[]",
        "retail_score": 0.9, "retailer": "Nordstrom", "loss_value": "~$120k",
        "suspect_count": 15, "mo": "flash-mob grab", "arrested": 0,
        "geo_confidence": "point", "event_key": "EK1", "n_sources": 5,
    }
    out = app._serialize(row)
    assert out["retailer"] == "Nordstrom"
    assert out["mo"] == "flash-mob grab"
    assert out["loss_value"] == "~$120k"
    assert out["suspect_count"] == 15
    assert out["arrested"] == 0
    assert out["geo_confidence"] == "point"
    assert out["n_sources"] == 5
    assert out["city"] == "Columbus" and out["state"] == "OH"
