import geocoder


def test_point_confidence_when_full_hits():
    def lookup(q):
        return (33.84, -84.37) if "Lenox" in q else (None, None)
    lat, lng, conf = geocoder.resolve_with_confidence("Lenox Square, Atlanta, GA", "Atlanta", "GA", lookup=lookup)
    assert conf == "point" and lat == 33.84


def test_city_confidence_falls_back_to_city_state():
    def lookup(q):
        return (33.75, -84.39) if q == "Atlanta, GA" else (None, None)
    lat, lng, conf = geocoder.resolve_with_confidence("Some Vague Place, Atlanta, GA", "Atlanta", "GA", lookup=lookup)
    assert conf == "city"


def test_state_confidence_when_only_state_resolves():
    def lookup(q):
        return (32.6, -83.4) if q == "GA" else (None, None)
    lat, lng, conf = geocoder.resolve_with_confidence("Atlanta, GA", "", "GA", lookup=lookup)
    assert conf == "state"


def test_none_when_nothing_resolves():
    lat, lng, conf = geocoder.resolve_with_confidence("", "", "", lookup=lambda q: (None, None))
    assert conf == "none" and lat is None
