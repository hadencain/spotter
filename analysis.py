"""
Temporal-spatial pattern analysis over the incident store.

Read-only: queries incidents, computes in Python, never writes. Never imports
extractor/collector/enrich/geocoder. All numbers are deterministic; the LLM
(build_narrative) only rephrases already-computed corridor JSON.

Data hygiene (see docs/superpowers/specs/2026-07-12-analysis-layer-design.md):
  - Spatial analyses use geo_confidence='point' rows only. Centroid fallbacks
    and legacy NULL-confidence rows would fabricate hotspots at centroids.
  - published_at is a publish-time proxy, and ~half the stamps are date-only
    (MM:SS == 00:00). Hour-of-day stats use only "hour-reliable" stamps,
    shifted to approximate local (solar) time by longitude.
  - Everything runs over event_key-deduped rows, matching /api/incidents.
"""
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
try:
    from config import AppConfig  # src/shared/config
except Exception:
    AppConfig = None

from entities import normalize as normalize_entity

CAVEAT = (
    "Extraction and geocoding are lossy; timestamps are publish times, not incident "
    "times. These are directional leads for allocating patrol attention — never "
    "claims about specific businesses or people."
)

RETAIL_THRESHOLD = 0.4     # mirrors app.RETAIL_THRESHOLD (app imports us, not vice versa)
GRID = 0.05                # degrees; ~5.5 km north-south
MIN_CELL_COUNT = 2
MAX_CELLS = 40
HOP_MAX_DAYS = 14
HOP_MAX_KM = 400.0
MIN_CHAIN = 3
MO_OVERLAP = 0.6
HOUR_MIN_N = 30            # below this, hour-of-day claims are suppressed
CORRIDOR_NEAR_KM = 50.0

_DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_BLOCKS = ["00–03", "03–06", "06–09", "09–12", "12–15", "15–18", "18–21", "21–24"]
_CARDINALS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


# ── loading ──────────────────────────────────────────────────────────────────

def _parse_since(since: str):
    """'7d'/'24h' → (cutoff datetime, window days). 'all'/junk → (None, None)."""
    if not since or since == "all":
        return None, None
    units = {"h": 1 / 24, "d": 1}
    try:
        amount = int(since[:-1])
        per = units.get(since[-1])
        if per and amount > 0:
            days = amount * per
            return datetime.now(timezone.utc) - timedelta(days=days), days
    except (ValueError, TypeError):
        pass
    return None, None


def _parse_dt(iso: str):
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_events(conn, cutoff=None, retail=False, itype=None, point_only=False):
    """Deduped incidents (one row per event_key), as dicts with parsed 'dt'."""
    conditions, params = ["1"], []
    if cutoff is not None:
        conditions.append("published_at >= ?")
        params.append(cutoff.isoformat())
    if retail:
        conditions.append("retail_score >= ?")
        params.append(RETAIL_THRESHOLD)
    if itype:
        conditions.append("incident_type = ?")
        params.append(itype)
    if point_only:
        conditions.append("geo_confidence = 'point' AND lat IS NOT NULL")
    where = " AND ".join(conditions)
    rows = conn.execute(
        f"""
        WITH filtered AS (SELECT * FROM incidents WHERE {where}),
        grouped AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY event_key ORDER BY published_at DESC, id) rn
            FROM filtered WHERE event_key IS NOT NULL
            UNION ALL SELECT *, 1 rn FROM filtered WHERE event_key IS NULL)
        SELECT * FROM grouped WHERE rn = 1
        """,
        params,
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["dt"] = _parse_dt(d.get("published_at"))
        out.append(d)
    return out


# ── geometry ─────────────────────────────────────────────────────────────────

def haversine_km(lat1, lng1, lat2, lng2):
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = rlat2 - rlat1
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def bearing_deg(lat1, lng1, lat2, lng2):
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlng = math.radians(lng2 - lng1)
    x = math.sin(dlng) * math.cos(rlat2)
    y = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlng)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def cardinal(deg):
    return _CARDINALS[int((deg + 22.5) // 45) % 8]


def cell_of(lat, lng):
    return (math.floor(lat / GRID), math.floor(lng / GRID))


def cell_center(cell):
    return round((cell[0] + 0.5) * GRID, 5), round((cell[1] + 0.5) * GRID, 5)


# ── weights & labels ─────────────────────────────────────────────────────────

def _half_life(window_days):
    if not window_days:
        return 30.0
    return min(30.0, max(7.0, window_days / 4))


def incident_weight(row, now, half_life_days):
    sev = (row.get("severity") or 3) / 3.0
    dt = row.get("dt")
    if dt is None:
        return sev * 0.5  # undated: still counts, but never dominates
    age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
    return sev * 0.5 ** (age_days / half_life_days)


def _place_label(rows):
    places = Counter()
    for r in rows:
        if r.get("city") and r.get("state"):
            places[f"{r['city']}, {r['state']}"] += 1
        elif r.get("city") or r.get("state"):
            places[r.get("city") or r.get("state")] += 1
        elif r.get("location_raw"):
            places[str(r["location_raw"])[:40]] += 1
    return places.most_common(1)[0][0] if places else "unlabeled area"


def _top_categories(rows, n=3):
    return [t for t, _ in Counter(r.get("incident_type") or "unknown" for r in rows).most_common(n)]


# ── hotspots ─────────────────────────────────────────────────────────────────

_NEIGHBORS = [(di, dj) for di in (-1, 0, 1) for dj in (-1, 0, 1) if (di, dj) != (0, 0)]


def trend_label(cur, prev):
    """Window-over-window raw-count trend for one cell."""
    if prev == 0:
        return "emerging" if cur >= 3 else "new"
    ratio = cur / prev
    if ratio >= 1.5:
        return "rising"
    if ratio <= 0.67:
        return "cooling"
    return "stable"


def hotspots(conn, since="30d", retail=False, itype=None, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff, window_days = _parse_since(since)
    trending = cutoff is not None
    load_cutoff = (cutoff - timedelta(days=window_days)) if trending else None
    rows = load_events(conn, cutoff=load_cutoff, retail=retail, itype=itype, point_only=True)

    cur = [r for r in rows if not trending or (r["dt"] and r["dt"] >= cutoff)]
    prev = [r for r in rows if trending and r["dt"] and r["dt"] < cutoff]

    hl = _half_life(window_days)
    weight, members, prev_counts = defaultdict(float), defaultdict(list), Counter()
    for r in cur:
        c = cell_of(r["lat"], r["lng"])
        weight[c] += incident_weight(r, now, hl)
        members[c].append(r)
    for r in prev:
        prev_counts[cell_of(r["lat"], r["lng"])] += 1

    cells = []
    for c, rs in members.items():
        if len(rs) < MIN_CELL_COUNT:
            continue
        score = weight[c] + 0.5 * sum(weight.get((c[0] + di, c[1] + dj), 0.0) for di, dj in _NEIGHBORS)
        lat, lng = cell_center(c)
        cells.append({
            "lat": lat, "lng": lng,
            "count": len(rs),
            "score": round(score, 3),
            "trend": trend_label(len(rs), prev_counts[c]) if trending else None,
            "categories": _top_categories(rs),
            "label": _place_label(rs),
            "incident_ids": [r["id"] for r in rs][:50],
        })
    cells.sort(key=lambda c: c["score"], reverse=True)
    return {
        "cells": cells[:MAX_CELLS],
        "window": {"since": since, "days": window_days, "point_incidents": len(cur)},
        "caveat": CAVEAT,
    }


# ── heatmap payload ──────────────────────────────────────────────────────────

def heatmap(conn, since="30d", retail=False, itype=None, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff, window_days = _parse_since(since)
    rows = load_events(conn, cutoff=cutoff, retail=retail, itype=itype, point_only=True)
    hl = _half_life(window_days)

    points, weeks = [], defaultdict(list)
    for r in rows:
        pt = [round(r["lat"], 5), round(r["lng"], 5), round(incident_weight(r, now, hl), 3)]
        points.append(pt)
        if r["dt"]:
            monday = (r["dt"] - timedelta(days=r["dt"].weekday())).date().isoformat()
            weeks[monday].append(pt)
    slices = [{"start": k, "points": v} for k, v in sorted(weeks.items())]
    return {"points": points, "slices": slices, "caveat": CAVEAT}


# ── temporal clustering ──────────────────────────────────────────────────────

def is_hour_reliable(dt):
    """Date-only stamps land on MM:SS == 00:00; real publish times almost never do."""
    return dt is not None and not (dt.minute == 0 and dt.second == 0)


def solar_hour(dt, lng):
    """Approximate local hour by longitude (15°/h). Good enough for 3h blocks."""
    return (dt.hour + round(lng / 15.0)) % 24


def temporal(conn, since="30d", retail=False, itype=None):
    cutoff, _ = _parse_since(since)
    rows = load_events(conn, cutoff=cutoff, retail=retail, itype=itype)

    dow = [0] * 7
    matrix = [[0] * 8 for _ in range(7)]
    reliable_n = 0
    for r in rows:
        dt = r["dt"]
        if dt is None:
            continue
        dow[dt.weekday()] += 1
        # hour blocks need a reliable stamp AND coordinates for the solar shift
        if is_hour_reliable(dt) and r.get("lat") is not None and r.get("lng") is not None:
            reliable_n += 1
            matrix[dt.weekday()][solar_hour(dt, r["lng"]) // 3] += 1

    total = sum(sum(row) for row in matrix)
    flat = sorted(
        ((matrix[d][b], d, b) for d in range(7) for b in range(8)),
        reverse=True,
    )
    top_windows = [
        {"dow": _DOW[d], "block": _BLOCKS[b], "count": n}
        for n, d, b in flat[:3] if n > 0
    ]
    return {
        "matrix": matrix,
        "dow": dow,
        "dow_labels": _DOW,
        "blocks": _BLOCKS,
        "top_windows": top_windows,
        "concentration": round(sum(n for n, _, _ in flat[:3]) / total, 3) if total else None,
        "hour_reliable_n": reliable_n,
        "hours_suppressed": reliable_n < HOUR_MIN_N,
        "basis": "publish-time proxy; hours are approximate local (solar) time",
        "caveat": CAVEAT,
    }


# ── sequence / co-occurrence linking → tracks ────────────────────────────────

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MO_STOPWORDS = {"the", "and", "with", "for", "from", "into"}


def mo_tokens(mo):
    if not mo:
        return frozenset()
    return frozenset(t for t in _TOKEN_RE.findall(str(mo).casefold())
                     if len(t) > 2 and t not in _MO_STOPWORDS)


def mo_similarity(a, b):
    """Overlap coefficient — Jaccard punishes extra descriptors in one report."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def mo_match(a, b):
    """Similar MO: ≥2 shared meaningful tokens (or identical single-token MOs)."""
    shared = len(a & b) if a and b else 0
    if shared >= 2:
        return mo_similarity(a, b) >= MO_OVERLAP
    return shared == 1 and a == b  # e.g. "shoplifting" == "shoplifting"


def _link_strength(a, b):
    """2 = same retailer (strong), 1 = similar MO (weak), 0 = no link."""
    if a["_ret"] and a["_ret"] == b["_ret"]:
        return 2
    if mo_match(a["_mo"], b["_mo"]):
        return 1
    return 0


def tracks(conn, since="60d", retail=False, now=None):
    cutoff, _ = _parse_since(since)
    rows = load_events(conn, cutoff=cutoff, retail=retail, point_only=True)

    cands = []
    for r in rows:
        if r["dt"] is None:
            continue
        r["_ret"] = normalize_entity(r["retailer"]) if (r.get("retailer") or "").strip() else ""
        r["_mo"] = mo_tokens(r.get("mo"))
        if r["_ret"] or r["_mo"]:
            cands.append(r)
    cands.sort(key=lambda r: (r["dt"], r["id"]))

    # greedy time-ordered chaining: each incident gets at most one successor and
    # one predecessor, so chains are paths (a route), never trees
    pred, has_succ = {}, set()
    for j, b in enumerate(cands):
        best = None
        for i in range(j - 1, -1, -1):
            a = cands[i]
            days = (b["dt"] - a["dt"]).total_seconds() / 86400.0
            if days > HOP_MAX_DAYS:
                break
            if a["id"] in has_succ:
                continue
            strength = _link_strength(a, b)
            if not strength:
                continue
            km = haversine_km(a["lat"], a["lng"], b["lat"], b["lng"])
            if km > HOP_MAX_KM:
                continue
            key = (strength, -(days + km / 100.0))
            if best is None or key > best[0]:
                best = (key, i)
        if best is not None:
            i = best[1]
            pred[b["id"]] = cands[i]
            has_succ.add(cands[i]["id"])

    by_id = {r["id"]: r for r in cands}
    chains = []
    heads = {r["id"] for r in cands if r["id"] in pred and r["id"] not in has_succ}
    for tail_id in heads:
        chain, cur = [], by_id[tail_id]
        while cur is not None:
            chain.append(cur)
            cur = pred.get(cur["id"])
        chain.reverse()
        if len(chain) >= MIN_CHAIN:
            chains.append(chain)

    out = []
    for chain in chains:
        strengths = [_link_strength(chain[k], chain[k + 1]) for k in range(len(chain) - 1)]
        kind = ("retailer" if all(s == 2 for s in strengths)
                else "mo" if all(s == 1 for s in strengths) else "mixed")
        stops, total_km = [], 0.0
        for k, r in enumerate(chain):
            stop = {
                "id": r["id"], "headline": r.get("headline"),
                "city": r.get("city"), "state": r.get("state"),
                "lat": r["lat"], "lng": r["lng"],
                "date": (r.get("published_at") or "")[:10],
            }
            if k > 0:
                p = chain[k - 1]
                km = haversine_km(p["lat"], p["lng"], r["lat"], r["lng"])
                total_km += km
                stop["km_from_prev"] = round(km, 1)
                stop["days_from_prev"] = round((r["dt"] - p["dt"]).total_seconds() / 86400.0, 1)
                stop["heading_from_prev"] = cardinal(bearing_deg(p["lat"], p["lng"], r["lat"], r["lng"])) if km > 1 else None
            stops.append(stop)
        rets = Counter(r["retailer"] for r in chain if (r.get("retailer") or "").strip())
        signature = (rets.most_common(1)[0][0] if kind == "retailer" and rets
                     else " / ".join(sorted(chain[0]["_mo"] | chain[-1]["_mo"]))[:60] or "shared pattern")
        # heuristic lead score, not a probability: more stops and an explicit
        # retailer match beat MO word overlap
        confidence = min(0.95, round(0.3 + 0.1 * len(chain) + (0.15 if kind == "retailer" else 0.0), 2))
        out.append({
            "signature": signature, "kind": kind, "confidence": confidence,
            "stops": stops, "n_stops": len(stops),
            "total_km": round(total_km, 1),
            "span_days": round((chain[-1]["dt"] - chain[0]["dt"]).total_seconds() / 86400.0, 1),
        })
    out.sort(key=lambda t: (t["confidence"], t["n_stops"]), reverse=True)
    return {"tracks": out, "caveat": CAVEAT}


# ── corridors report ─────────────────────────────────────────────────────────

_TREND_MULT = {"emerging": 1.3, "new": 1.3, "rising": 1.2, "stable": 1.0, "cooling": 0.8, None: 1.0}


def corridors(conn, since="30d", retail=False, now=None):
    now = now or datetime.now(timezone.utc)
    hs = hotspots(conn, since=since, retail=retail, now=now)
    tr = tracks(conn, since=since, retail=retail, now=now)
    temp = temporal(conn, since=since, retail=retail)

    # id → parsed dt, for cell-local day-of-week profiles
    cutoff, _ = _parse_since(since)
    dt_by_id = {r["id"]: r["dt"] for r in load_events(conn, cutoff=cutoff, retail=retail, point_only=True)}

    entries = []
    used_tracks = set()
    for cell in hs["cells"][:12]:
        near = []
        for idx, t in enumerate(tr["tracks"]):
            if any(haversine_km(cell["lat"], cell["lng"], s["lat"], s["lng"]) <= CORRIDOR_NEAR_KM
                   for s in t["stops"]):
                near.append(t)
                used_tracks.add(idx)
        # cell-local temporal profile only when the cell has enough of its own signal
        member_dts = [dt_by_id[i] for i in cell["incident_ids"] if dt_by_id.get(i)]
        if len(member_dts) >= 5:
            dow_counts = Counter(dt.weekday() for dt in member_dts)
            timing = {"scope": "cell",
                      "top_dow": [_DOW[d] for d, _ in dow_counts.most_common(2)],
                      "hours_suppressed": True}
        else:
            timing = {"scope": "global", "top_windows": temp["top_windows"],
                      "hours_suppressed": temp["hours_suppressed"]}
        entries.append({
            "kind": "hotspot",
            "label": cell["label"],
            "score": round(cell["score"] * _TREND_MULT.get(cell["trend"], 1.0), 3),
            "evidence": {
                "count": cell["count"], "trend": cell["trend"],
                "categories": cell["categories"], "cell_score": cell["score"],
            },
            "timing": timing,
            "tracks": near,
            "lat": cell["lat"], "lng": cell["lng"],
            "incident_ids": cell["incident_ids"],
        })

    for idx, t in enumerate(tr["tracks"]):
        if idx in used_tracks:
            continue
        route = " → ".join(dict.fromkeys(
            f"{s['city']}, {s['state']}" if s.get("city") and s.get("state")
            else (s.get("city") or s.get("state") or "?") for s in t["stops"]))
        entries.append({
            "kind": "track",
            "label": f"{t['signature']}: {route}",
            "score": round(t["confidence"] * t["n_stops"], 3),
            "evidence": {"n_stops": t["n_stops"], "total_km": t["total_km"],
                         "span_days": t["span_days"], "link": t["kind"]},
            "timing": {"scope": "track", "top_windows": [], "hours_suppressed": True},
            "tracks": [t],
        })

    entries.sort(key=lambda e: e["score"], reverse=True)
    for rank, e in enumerate(entries, 1):
        e["rank"] = rank
    return {"corridors": entries, "temporal": temp,
            "window": hs["window"], "caveat": CAVEAT}


# ── optional LLM narrative (copywriter, not analyst) ─────────────────────────

_NARRATIVE_SYSTEM = (
    "You summarize a precomputed retail-crime corridor report for asset-protection "
    "patrols. Use ONLY the numbers and places given — never invent, extrapolate, or "
    "aggregate new figures. Never make claims about specific businesses being "
    "responsible or about identified people. Frame everything as directional leads. "
    "End with this exact caveat: " + CAVEAT
)


def build_narrative(corridor_payload, max_entries=6):
    """Optional ≤200-word brief over corridors(). Returns (text|None, error|None)."""
    key = None
    if AppConfig is not None:
        try:
            key = AppConfig("ship").get_secret("anthropic_api_key")
        except Exception:
            key = None
    key = key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None, "no API key"
    try:
        import anthropic
        import json as _json
        slim = [{k: e[k] for k in ("rank", "kind", "label", "evidence", "timing") if k in e}
                for e in corridor_payload["corridors"][:max_entries]]
        msg = anthropic.Anthropic(api_key=key).messages.create(
            model="claude-haiku-4-5", max_tokens=400,
            system=_NARRATIVE_SYSTEM,
            messages=[{"role": "user", "content":
                       "Write a patrol brief (max 200 words) from this corridor data:\n"
                       + _json.dumps(slim, ensure_ascii=False)}],
        )
        return msg.content[0].text.strip(), None
    except Exception as e:
        return None, str(e)
