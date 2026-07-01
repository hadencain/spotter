import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from db import get_conn

# In-workspace this pulls the shared AppConfig; standalone clones fall back to
# the ANTHROPIC_API_KEY environment variable (see _make_llm_client).
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
    from config import AppConfig
except ImportError:
    AppConfig = None

# ---------------------------------------------------------------------------
# Classification tables
# ---------------------------------------------------------------------------

_RAW_KEYWORDS = {
    "shooting":    [r"shoot\w*", r"\bshot\b", r"gunfire", r"gunshot", r"firearm", r"gun violence", r"shooter"],
    "stabbing":    [r"\bstab\w*", r"\bknifed\b", r"\bslashed\b"],
    "bombing":     [r"\bbomb\b", r"\bbombing\b", r"explosion", r"explosive", r"detonate", r"\bblast\b"],
    "robbery":     [r"\brobb\w+", r"armed robbery", r"hold.?up", r"carjack\w*"],
    "theft":       [r"\btheft\b", r"\bstolen\b", r"shoplift\w*", r"\blarceny\b", r"\bburglary\b"],
    "assault":     [r"\bassault\w*", r"\bbrawl\w*"],
    "threat":      [r"\bthreat\w*", r"bomb threat", r"terroris\w*", r"\bevacuat\w*", r"\blockdown\b"],
    "arrest":      [r"\barrest\w*", r"\bapprehend\w*", r"\bin custody\b", r"\bwarrant\b"],
    "pursuit":     [r"\bflee\w*", r"\bfleeing\b", r"\bpursuit\b", r"\bhigh.?speed chase\b"],
    "homicide":    [r"\bmurder\w*", r"\bhomicide\b", r"\bkilled\b", r"\bfatally\b", r"\bslain\b"],
    "missing":     [r"\bmissing\b", r"\babduct\w*", r"\bkidnap\w*", r"amber alert"],
    "suspicious":  [r"\bsuspicious\b", r"suspect package", r"unattended bag", r"\bhazmat\b"],
}

INCIDENT_PATTERNS = {
    itype: [re.compile(p, re.IGNORECASE) for p in patterns]
    for itype, patterns in _RAW_KEYWORDS.items()
}

VALID_TYPES = set(_RAW_KEYWORDS.keys()) | {"general"}

def _is_english(text: str) -> bool:
    if not text:
        return True
    non_ascii = sum(1 for c in text if ord(c) > 127)
    return (non_ascii / len(text)) < 0.15

SEVERITY_MAP = {
    "bombing":  5,
    "homicide": 5,
    "shooting": 4,
    "stabbing": 4,
    "threat":   4,
    "missing":  3,
    "assault":  3,
    "robbery":  3,
    "pursuit":  2,
    "theft":    2,
    "arrest":   2,
    "suspicious": 1,
}

US_STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}

STATE_ABBREVS = {v: k for k, v in US_STATES.items()}

_ABBREVS_PIPE = "|".join(US_STATES.values())
_NAMES_PIPE   = "|".join(sorted(US_STATES.keys(), key=len, reverse=True))

_CITY_STATE_RE = re.compile(
    r"\b([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){0,3}),\s*(?:" + _ABBREVS_PIPE + r")\b"
)
_DATELINE_RE = re.compile(
    r"^([A-Z][A-Z ]{1,25}?)\s*(?:\([^)]+\))?\s*[—–-]",
)
_IN_CITY_RE = re.compile(
    r"\b(?:in|at|near|outside)\s+([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){0,2})"
    r"(?:\s+(?:mall|center|plaza|square|police|hospital|school))?[,.\s]",
    re.IGNORECASE,
)
_STATE_NAME_RE = re.compile(r"\b(" + _NAMES_PIPE + r")\b")

RETAIL_KEYWORDS = [
    "mall", "shopping center", "shopping centre", "plaza", "outlet",
    "strip mall", "retail", "store", "department store", "walmart",
    "target", "costco", "kroger", "macy", "nordstrom",
]

COST_TRACKER_PATH = Path(__file__).parent / "cost_tracker.json"

# Haiku 4.5 pricing per token
_INPUT_COST_PER_TOKEN  = 1.00 / 1_000_000
_OUTPUT_COST_PER_TOKEN = 5.00 / 1_000_000

_session_input_tokens  = 0
_session_output_tokens = 0


def _accrue(usage) -> None:
    global _session_input_tokens, _session_output_tokens
    _session_input_tokens  += getattr(usage, "input_tokens",  0)
    _session_output_tokens += getattr(usage, "output_tokens", 0)


def _write_cost_tracker() -> None:
    total_cost = (
        _session_input_tokens  * _INPUT_COST_PER_TOKEN +
        _session_output_tokens * _OUTPUT_COST_PER_TOKEN
    )
    payload = {
        "run_at":        datetime.now(timezone.utc).isoformat(),
        "model":         "claude-haiku-4-5",
        "input_tokens":  _session_input_tokens,
        "output_tokens": _session_output_tokens,
        "total_cost":    round(total_cost, 6),
    }
    COST_TRACKER_PATH.write_text(json.dumps(payload, indent=2))


_LLM_SYSTEM = (
    "You are a news classifier for a security intelligence platform. "
    "Extract location and incident type from news articles. "
    "Respond with JSON only — no explanation, no markdown."
)

_LLM_PROMPT = """Extract the US city, state abbreviation, and incident type from this article.

Return exactly this JSON:
{{"city": "City Name", "state": "XX", "incident_type": "TYPE"}}

incident_type must be one of: shooting, stabbing, bombing, robbery, theft, assault, threat, arrest, pursuit, homicide, missing, suspicious, general

Rules:
- state must be a 2-letter US abbreviation (CA, TX, FL, etc.)
- If no clear US city found, use "" for city
- If no clear US state found, use "" for state
- Pick the most specific incident_type that fits

Article:
{snippet}"""


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

def _make_llm_client() -> anthropic.Anthropic | None:
    key = AppConfig("ship").get_secret("anthropic_api_key") if AppConfig else None
    key = key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("warning: no Anthropic API key (set ANTHROPIC_API_KEY) — LLM extraction disabled")
        return None
    return anthropic.Anthropic(api_key=key)


def _llm_extract(headline: str, text: str, client: anthropic.Anthropic) -> tuple[str, str, str, str]:
    """Call LLM for location + type. Returns (location_raw, city, state, incident_type)."""
    snippet = f"{headline}\n{(text or '')[:400]}"
    prompt = _LLM_PROMPT.format(snippet=snippet)
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=80,
            system=_LLM_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        _accrue(msg.usage)
        raw = msg.content[0].text.strip()
        # Strip markdown fences if model adds them
        raw = re.sub(r"```(?:json)?\n?", "", raw).strip("`").strip()
        data = json.loads(raw)
        city  = (data.get("city") or "").strip()
        state = (data.get("state") or "").strip().upper()
        itype = (data.get("incident_type") or "general").strip().lower()

        # Validate state
        if state and state not in STATE_ABBREVS:
            state = US_STATES.get(state.title(), "")

        # Validate incident type
        if itype not in VALID_TYPES:
            itype = "general"

        location_raw = f"{city}, {state}" if city and state else (state or city or "")
        return location_raw, city, state, itype
    except Exception:
        return "", "", "", "general"


# ---------------------------------------------------------------------------
# Extraction logic
# ---------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc).isoformat()


def classify_incident(text: str) -> tuple[str, int]:
    for itype, patterns in INCIDENT_PATTERNS.items():
        if any(p.search(text) for p in patterns):
            return itype, SEVERITY_MAP.get(itype, 1)
    return "general", 1


def extract_location(text: str) -> tuple[str, str, str]:
    m = _CITY_STATE_RE.search(text)
    if m:
        city = m.group(1).strip().title()
        raw = m.group(0).strip()
        abbrev = re.search(_ABBREVS_PIPE, raw).group(0)
        return f"{city}, {abbrev}", city, abbrev

    m = _DATELINE_RE.match(text.strip())
    if m:
        city_raw = m.group(1).strip().title()
        state_m = _STATE_NAME_RE.search(text[:120])
        if state_m:
            state_name = state_m.group(1)
            abbrev = US_STATES[state_name]
            return f"{city_raw}, {abbrev}", city_raw, abbrev

    state_m = _STATE_NAME_RE.search(text)
    if state_m:
        state_name = state_m.group(1)
        abbrev = US_STATES[state_name]
        city_m = _IN_CITY_RE.search(text)
        city = city_m.group(1).strip().title() if city_m else ""
        return f"{city}, {abbrev}" if city else state_name, city, abbrev

    return "", "", ""


def is_retail_relevant(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in RETAIL_KEYWORDS)


def extract_tags(text: str, incident_type: str) -> list[str]:
    tags = [incident_type]
    if is_retail_relevant(text):
        tags.append("retail")
    if "mall" in text.lower():
        tags.append("mall")
    return tags


def is_retail_candidate(text: str) -> bool:
    return is_retail_relevant(text)


_ENTITY_SYSTEM = (
    "You are a retail-crime intelligence classifier. "
    "Extract structured incident data. Respond with JSON only — no markdown, no prose."
)

_ENTITY_PROMPT = """From this article extract retail/public-space incident intel.

Return exactly this JSON:
{{"city":"","state":"","incident_type":"","retail_score":0.0,"retailer":"","loss_value":"","suspect_count":null,"mo":"","arrested":null}}

Rules:
- state: 2-letter US abbreviation, or "" if unknown.
- incident_type: one of shooting, stabbing, bombing, robbery, theft, assault, threat, arrest, pursuit, homicide, missing, suspicious, general.
- retail_score: 0.0-1.0, how strongly this is a retail / mall / shopping-center / store / parking-lot incident.
- retailer: named store/chain/mall, else "".
- loss_value: reported dollar loss as short text (e.g. "~$120k"), else "".
- suspect_count: integer count if stated, else null.
- mo: short modus operandi (e.g. "smash-and-grab", "flash-mob grab"), else "".
- arrested: 1 if any arrest made, 0 if suspects at large, null if unknown.

Article:
{snippet}"""


def _coerce_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _llm_extract_entities(headline: str, body: str, client) -> dict:
    default = {"city": "", "state": "", "incident_type": "general", "retail_score": 0.0,
              "retailer": "", "loss_value": "", "suspect_count": None, "mo": "", "arrested": None}
    snippet = f"{headline}\n{(body or '')[:4000]}"
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5", max_tokens=200,
            system=_ENTITY_SYSTEM,
            messages=[{"role": "user", "content": _ENTITY_PROMPT.format(snippet=snippet)}],
        )
        _accrue(msg.usage)
        raw = msg.content[0].text.strip()
        raw = re.sub(r"```(?:json)?\n?", "", raw).strip("`").strip()
        data = json.loads(raw)
        if not isinstance(data, dict):
            return default
    except Exception:
        return default

    state = (data.get("state") or "").strip().upper()
    if state and state not in STATE_ABBREVS:
        state = US_STATES.get(state.title(), "")
    itype = (data.get("incident_type") or "general").strip().lower()
    if itype not in VALID_TYPES:
        itype = "general"
    try:
        score = max(0.0, min(1.0, float(data.get("retail_score", 0.0))))
    except (TypeError, ValueError):
        score = 0.0
    return {
        "city": (data.get("city") or "").strip(),
        "state": state,
        "incident_type": itype,
        "retail_score": score,
        "retailer": (data.get("retailer") or "").strip(),
        "loss_value": (data.get("loss_value") or "").strip(),
        "suspect_count": _coerce_int(data.get("suspect_count")),
        "mo": (data.get("mo") or "").strip(),
        "arrested": _coerce_int(data.get("arrested")),
    }


def process_article(row, llm_client=None) -> dict | None:
    text = f"{row['headline'] or ''} {row['raw_text'] or ''}"
    if not text.strip():
        return None
    if not _is_english(text):
        return None

    incident_type, severity = classify_incident(text)
    location_raw, city, state = extract_location(text)

    # LLM fallback: fire when location is missing OR type is generic
    if llm_client and (not location_raw or incident_type == "general"):
        llm_loc, llm_city, llm_state, llm_type = _llm_extract(
            row["headline"] or "", row["raw_text"] or "", llm_client
        )
        if not location_raw and llm_loc:
            location_raw, city, state = llm_loc, llm_city, llm_state
        if incident_type == "general" and llm_type != "general":
            incident_type = llm_type
            severity = SEVERITY_MAP.get(incident_type, 1)

    tags = extract_tags(text, incident_type)

    return {
        "id": str(uuid.uuid4()),
        "headline": row["headline"],
        "source": row["source"],
        "source_url": row["source_url"],
        "published_at": row["published_at"],
        "ingested_at": _now(),
        "raw_text": row["raw_text"],
        "location_raw": location_raw,
        "lat": None,
        "lng": None,
        "city": city,
        "state": state,
        "incident_type": incident_type,
        "severity": severity,
        "tags": json.dumps(tags),
        "reviewed": 0,
    }


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

def run_extraction(limit: int = 500, use_llm: bool = False):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM raw_articles WHERE processed = 0 LIMIT ?", (limit,)
    ).fetchall()

    if not rows:
        print("no unprocessed articles")
        return

    llm_client = _make_llm_client() if use_llm else None
    if use_llm and llm_client:
        print("  LLM extraction enabled (claude-haiku-4-5)")

    inserted = 0
    skipped = 0
    llm_calls = 0

    for row in rows:
        incident = process_article(row, llm_client)
        if incident:
            if llm_client and incident.get("city"):
                llm_calls += 1
            try:
                conn.execute(
                    """INSERT INTO incidents
                       (id, headline, source, source_url, published_at, ingested_at,
                        raw_text, location_raw, lat, lng, city, state,
                        incident_type, severity, tags, reviewed)
                       VALUES
                       (:id, :headline, :source, :source_url, :published_at, :ingested_at,
                        :raw_text, :location_raw, :lat, :lng, :city, :state,
                        :incident_type, :severity, :tags, :reviewed)""",
                    incident,
                )
                inserted += 1
            except Exception as e:
                print(f"  insert failed for {row['source_url']}: {e}")
                skipped += 1
        else:
            skipped += 1

        conn.execute(
            "UPDATE raw_articles SET processed = 1 WHERE id = ?", (row["id"],)
        )

    conn.commit()
    conn.close()
    print(f"extraction done — {inserted} incidents created, {skipped} skipped")
    if llm_client:
        print(f"  LLM calls made: {llm_calls}")
        _write_cost_tracker()
        total = _session_input_tokens * _INPUT_COST_PER_TOKEN + _session_output_tokens * _OUTPUT_COST_PER_TOKEN
        print(f"  tokens: {_session_input_tokens}in / {_session_output_tokens}out  cost: ${total:.4f}")


def run_llm_backfill(batch_size: int = 50):
    """Fill location + improve incident_type on existing incidents with empty location."""
    client = _make_llm_client()
    if not client:
        return

    conn = get_conn()
    rows = conn.execute(
        """SELECT id, headline, raw_text, incident_type
           FROM incidents
           WHERE (city IS NULL OR city = '')
           ORDER BY published_at DESC"""
    ).fetchall()

    if not rows:
        print("no incidents missing location")
        conn.close()
        return

    print(f"backfilling {len(rows)} incidents with LLM location extraction...")
    updated = 0
    improved_type = 0

    for i, row in enumerate(rows):
        llm_loc, city, state, llm_type = _llm_extract(
            row["headline"] or "", row["raw_text"] or "", client
        )

        if city or state or llm_type != "general":
            location_raw = f"{city}, {state}" if city and state else (state or city or "")
            new_type = row["incident_type"]
            new_sev = SEVERITY_MAP.get(new_type, 1)

            if row["incident_type"] == "general" and llm_type != "general":
                new_type = llm_type
                new_sev = SEVERITY_MAP.get(new_type, 1)
                improved_type += 1

            conn.execute(
                """UPDATE incidents
                   SET location_raw = ?, city = ?, state = ?,
                       incident_type = ?, severity = ?
                   WHERE id = ?""",
                (location_raw, city, state, new_type, new_sev, row["id"]),
            )
            updated += 1

        if (i + 1) % batch_size == 0:
            conn.commit()
            print(f"  {i + 1}/{len(rows)} processed, {updated} updated...")
            time.sleep(0.5)  # brief pause between batches

    conn.commit()
    conn.close()
    print(f"backfill done — {updated}/{len(rows)} incidents updated, {improved_type} types improved")
    print("run geocoder.py next to map the newly located incidents")
    _write_cost_tracker()
    total = _session_input_tokens * _INPUT_COST_PER_TOKEN + _session_output_tokens * _OUTPUT_COST_PER_TOKEN
    print(f"  tokens: {_session_input_tokens}in / {_session_output_tokens}out  cost: ${total:.4f}")


if __name__ == "__main__":
    use_llm = "--llm" in sys.argv
    backfill = "--backfill" in sys.argv

    if backfill:
        run_llm_backfill()
    else:
        run_extraction(use_llm=use_llm)
