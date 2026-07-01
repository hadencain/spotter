import enrich


def test_returns_extracted_text(monkeypatch):
    monkeypatch.setattr(enrich.trafilatura, "fetch_url", lambda url, **k: "<html>raw</html>")
    monkeypatch.setattr(enrich.trafilatura, "extract", lambda html, **k: "Clean article body.")
    assert enrich.fetch_body("http://example.com/a") == "Clean article body."


def test_returns_empty_on_fetch_failure(monkeypatch):
    monkeypatch.setattr(enrich.trafilatura, "fetch_url", lambda url, **k: None)
    assert enrich.fetch_body("http://example.com/dead") == ""


def test_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network")
    monkeypatch.setattr(enrich.trafilatura, "fetch_url", boom)
    assert enrich.fetch_body("http://example.com/x") == ""
