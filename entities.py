"""
Query-time retailer entity resolution.

Pipeline per string: normalize -> alias map -> type-gated fuzzy clustering.
Guardrails (see docs/superpowers/specs/2026-07-01-entity-chain-pages-design.md):
  1. ALIASES catches brand aliases fuzzy can't (no shared tokens).
  2. A venue (mall/plaza/...) never merges with a chain, whatever the score.
Pure functions, no DB, no Flask.
"""
import re
from collections import Counter
from functools import lru_cache

from rapidfuzz import fuzz

FUZZ_THRESHOLD = 90

_VENUE_WORDS = {
    "mall", "malls", "plaza", "plazas", "center", "centers",
    "centre", "centres", "galleria", "gallerias", "shopping",
}

_PUNCT_RE = re.compile(r"[^\w\s&']")
# trailing store numbers: "store 45" (any digits) or a bare 3-6 digit suffix
# ("Forever 21" keeps its 2-digit brand number)
_STORE_NUM_RE = re.compile(r"\b(?:store\s+\d{1,6}|\d{3,6})$")


def normalize(s) -> str:
    s = "" if s is None else str(s)
    s = s.casefold().strip()
    s = _PUNCT_RE.sub(" ", s)
    s = " ".join(s.split())
    stripped = _STORE_NUM_RE.sub("", s).strip()
    return stripped if stripped else s  # never strip a name down to nothing ("Store 24")


def classify(s: str) -> str:
    """'venue' for physical places (malls etc.), 'chain' for brands."""
    return "venue" if _VENUE_WORDS & set(normalize(s).split()) else "chain"
