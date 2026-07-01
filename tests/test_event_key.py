from event_key import make_event_key


def test_same_event_same_key():
    a = make_event_key("GA", "Atlanta", "shooting", "2026-07-01T14:22:00+00:00")
    b = make_event_key("ga", " atlanta ", "Shooting", "2026-07-01T09:00:00Z")
    assert a == b  # case, whitespace, and time-of-day all normalized away


def test_different_city_different_key():
    a = make_event_key("GA", "Atlanta", "shooting", "2026-07-01")
    b = make_event_key("GA", "Macon", "shooting", "2026-07-01")
    assert a != b


def test_handles_empty_components():
    k = make_event_key("", "", "general", "")
    assert isinstance(k, str) and len(k) == 40  # sha1 hex length


def test_none_components_normalize_like_empty():
    assert make_event_key(None, None, "general", None) == make_event_key("", "", "general", "")


def test_each_field_affects_key():
    base = make_event_key("GA", "Atlanta", "shooting", "2026-07-01")
    assert make_event_key("FL", "Atlanta", "shooting", "2026-07-01") != base  # state
    assert make_event_key("GA", "Atlanta", "robbery", "2026-07-01") != base   # incident_type
    assert make_event_key("GA", "Atlanta", "shooting", "2026-07-02") != base  # date


def test_delimiter_injection_no_collision():
    a = make_event_key("GA", "Atlanta|shooting", "reported", "2026-07-01")
    b = make_event_key("GA|Atlanta", "shooting", "reported", "2026-07-01")
    assert a != b


def test_empty_differs_from_populated():
    assert make_event_key("", "", "", "") != make_event_key("GA", "Atlanta", "shooting", "2026-07-01")
