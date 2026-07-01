import enrich


def test_returns_extracted_text(monkeypatch):
    captured = {}
    monkeypatch.setattr(enrich.trafilatura, "fetch_url", lambda url, **k: "<html>raw</html>")
    def fake_extract(html, **k):
        captured["html"] = html
        return "Clean article body."
    monkeypatch.setattr(enrich.trafilatura, "extract", fake_extract)
    assert enrich.fetch_body("http://example.com/a") == "Clean article body."
    assert captured["html"] == "<html>raw</html>"  # fetched html flows to extract, not the url


def test_returns_empty_on_fetch_failure(monkeypatch):
    monkeypatch.setattr(enrich.trafilatura, "fetch_url", lambda url, **k: None)
    assert enrich.fetch_body("http://example.com/dead") == ""


def test_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network")
    monkeypatch.setattr(enrich.trafilatura, "fetch_url", boom)
    assert enrich.fetch_body("http://example.com/x") == ""


def test_empty_url_returns_empty_without_fetch(monkeypatch):
    called = {"n": 0}
    def counting_fetch(url, **k):
        called["n"] += 1
        return "<html>x</html>"
    monkeypatch.setattr(enrich.trafilatura, "fetch_url", counting_fetch)
    assert enrich.fetch_body("") == ""
    assert called["n"] == 0  # empty url short-circuits before any network call


def test_extract_returns_none_yields_empty(monkeypatch):
    monkeypatch.setattr(enrich.trafilatura, "fetch_url", lambda url, **k: "<html>raw</html>")
    monkeypatch.setattr(enrich.trafilatura, "extract", lambda html, **k: None)
    assert enrich.fetch_body("http://example.com/a") == ""
