import app


def test_retail_flag_adds_threshold_condition():
    conds, params = app._build_conditions({"retail": "1", "since": "all"})
    assert any("retail_score >=" in c for c in conds)
    assert app.RETAIL_THRESHOLD in params


def test_mapped_only_query_param_overrides():
    conds, _ = app._build_conditions({"mapped_only": "1", "since": "all"}, mapped_only=False)
    assert "lat IS NOT NULL" in conds


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
