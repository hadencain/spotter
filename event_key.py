import hashlib


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def make_event_key(state: str, city: str, incident_type: str, published_at: str) -> str:
    """Stable key grouping duplicate reports of one real-world event."""
    day = (published_at or "")[:10]
    basis = "|".join([_norm(state), _norm(city), _norm(incident_type), day])
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()
