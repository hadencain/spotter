import importlib


def _reload(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("SPOTTER_USER_AGENT", raising=False)
    else:
        monkeypatch.setenv("SPOTTER_USER_AGENT", value)
    import user_agent
    return importlib.reload(user_agent)


def test_default_identifies_the_project(monkeypatch):
    mod = _reload(monkeypatch, None)
    assert mod.USER_AGENT == mod.DEFAULT_USER_AGENT
    assert "spotter" in mod.USER_AGENT
    assert "http" in mod.USER_AGENT  # contact URL, per Nominatim's usage policy


def test_env_override_wins(monkeypatch):
    mod = _reload(monkeypatch, "myinstance/2.0 (+https://example.org)")
    assert mod.USER_AGENT == "myinstance/2.0 (+https://example.org)"


def test_blank_env_falls_back_to_default(monkeypatch):
    mod = _reload(monkeypatch, "   ")
    assert mod.USER_AGENT == mod.DEFAULT_USER_AGENT


def test_collectors_and_geocoder_share_one_identity(monkeypatch):
    mod = _reload(monkeypatch, None)
    import geocoder
    import reddit_collector
    import collector
    assert geocoder.USER_AGENT == mod.USER_AGENT
    assert reddit_collector.USER_AGENT == mod.USER_AGENT
    assert collector.USER_AGENT == mod.USER_AGENT
