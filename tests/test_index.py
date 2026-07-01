def test_index_renders():
    import app
    r = app.app.test_client().get("/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    # assert on ACTUAL elements, not substrings that also appear in CSS/<title>
    assert '<div class="brand">SPOTTER</div>' in body      # wordmark element
    assert 'data-cat="shooting"' in body                   # category toggle elements
    assert 'data-cat="theft"' in body
    assert 'id="ticker"' in body                           # ticker element (not the CSS comment)
    assert 'id="map"' in body                              # leaflet map container
    assert 'data-v="patterns"' in body                     # patterns tab present
    assert "/api/incidents" in body                        # map is wired to the incidents API
    assert "/api/stats" in body                            # stats bar wired
    assert 'id="view-patterns"' in body                     # patterns view container present
