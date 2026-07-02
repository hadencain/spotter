import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from db import get_conn, init_db

_STATUS_FILE = Path(__file__).parent / "pipeline_status.json"

app = Flask(__name__)

RETAIL_THRESHOLD = 0.4

_DEDUP_CTE = """
WITH deduped AS (
    SELECT * FROM (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY event_key ORDER BY published_at DESC, id) rn
        FROM incidents WHERE event_key IS NOT NULL)
    WHERE rn = 1
    UNION ALL SELECT *, 1 rn FROM incidents WHERE event_key IS NULL)
"""


def _parse_since(since: str) -> str | None:
    if since == "all":
        return None
    units = {"h": "hours", "d": "days"}
    try:
        amount = int(since[:-1])
        unit = units.get(since[-1])
        if unit:
            cutoff = datetime.now(timezone.utc) - timedelta(**{unit: amount})
            return cutoff.isoformat()
    except Exception:
        pass
    return None


def _build_conditions(args, mapped_only=False):
    conditions = []
    params = []

    mo_param = args.get("mapped_only")
    if mo_param is not None:
        mapped_only = mo_param == "1"
    if mapped_only:
        conditions.append("lat IS NOT NULL")

    if args.get("retail") == "1":
        conditions.append("retail_score >= ?")
        params.append(RETAIL_THRESHOLD)

    since = args.get("since", "7d")
    cutoff = _parse_since(since)
    if cutoff:
        conditions.append("published_at >= ?")
        params.append(cutoff)

    state = args.get("state")
    if state:
        conditions.append("state = ?")
        params.append(state.upper())

    itype = args.get("type")
    if itype:
        conditions.append("incident_type = ?")
        params.append(itype)

    min_sev = int(args.get("severity", "1"))
    conditions.append("severity >= ?")
    params.append(min_sev)

    # explicit id list (comma-separated) — used by the patterns view to expand a cluster
    ids = args.get("ids")
    if ids:
        id_list = [s for s in ids.split(",") if s][:200]
        if id_list:
            conditions.append(f"id IN ({','.join(['?'] * len(id_list))})")
            params.extend(id_list)

    return conditions, params


def _serialize(r):
    return {
        "id": r["id"],
        "headline": r["headline"],
        "source": r["source"],
        "source_url": r["source_url"],
        "published_at": r["published_at"],
        "location_raw": r["location_raw"],
        "lat": r["lat"],
        "lng": r["lng"],
        "city": r["city"],
        "state": r["state"],
        "incident_type": r["incident_type"],
        "severity": r["severity"],
        "tags": json.loads(r["tags"] or "[]"),
        "retail_score": r["retail_score"],
        "retailer": r["retailer"],
        "loss_value": r["loss_value"],
        "suspect_count": r["suspect_count"],
        "mo": r["mo"],
        "arrested": r["arrested"],
        "geo_confidence": r["geo_confidence"],
        "event_key": r["event_key"],
        "n_sources": r["n_sources"] if "n_sources" in r.keys() else 1,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/incidents")
def incidents():
    conn = get_conn()
    conditions, params = _build_conditions(request.args, mapped_only=True)
    where = " AND ".join(conditions) if conditions else "1"
    rows = conn.execute(
        f"""
        WITH filtered AS (SELECT * FROM incidents WHERE {where}),
        grouped AS (
            SELECT *,
                   COUNT(*) OVER (PARTITION BY event_key) AS n_sources,
                   ROW_NUMBER() OVER (PARTITION BY event_key ORDER BY published_at DESC, id) AS rn
            FROM filtered WHERE event_key IS NOT NULL
            UNION ALL
            SELECT *, 1 AS n_sources, 1 AS rn FROM filtered WHERE event_key IS NULL
        )
        SELECT * FROM grouped WHERE rn = 1
        ORDER BY retail_score DESC, severity DESC, published_at DESC LIMIT 3000
        """,
        params,
    ).fetchall()
    conn.close()
    data = [_serialize(r) for r in rows]
    return jsonify({"count": len(data), "incidents": data})


_SORT_COLS = {
    "sev":      "severity",
    "type":     "incident_type",
    "headline": "headline",
    "location": "city",
    "date":     "published_at",
    "source":   "source",
}

@app.route("/api/reports")
def reports():
    conn = get_conn()
    conditions, params = _build_conditions(request.args, mapped_only=False)

    page = max(1, int(request.args.get("page", 1)))
    per_page = 100
    offset = (page - 1) * per_page

    sort_col = _SORT_COLS.get(request.args.get("sort", "date"), "published_at")
    sort_dir = "ASC" if request.args.get("order", "desc") == "asc" else "DESC"

    where = " AND ".join(conditions) if conditions else "1"
    total = conn.execute(
        f"WITH filtered AS (SELECT * FROM incidents WHERE {where}), "
        f"g AS (SELECT event_key, ROW_NUMBER() OVER (PARTITION BY event_key ORDER BY published_at DESC, id) rn "
        f"FROM filtered WHERE event_key IS NOT NULL UNION ALL "
        f"SELECT event_key, 1 FROM filtered WHERE event_key IS NULL) "
        f"SELECT COUNT(*) FROM g WHERE rn = 1", params).fetchone()[0]
    rows = conn.execute(
        f"""
        WITH filtered AS (SELECT * FROM incidents WHERE {where}),
        grouped AS (
            SELECT *,
                   COUNT(*) OVER (PARTITION BY event_key) AS n_sources,
                   ROW_NUMBER() OVER (PARTITION BY event_key ORDER BY published_at DESC, id) AS rn
            FROM filtered WHERE event_key IS NOT NULL
            UNION ALL
            SELECT *, 1 AS n_sources, 1 AS rn FROM filtered WHERE event_key IS NULL
        )
        SELECT * FROM grouped WHERE rn = 1
        ORDER BY {sort_col} {sort_dir} LIMIT ? OFFSET ?
        """,
        params + [per_page, offset],
    ).fetchall()
    conn.close()

    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "incidents": [_serialize(r) for r in rows],
    })


@app.route("/api/stats")
def stats():
    conn = get_conn()
    total = conn.execute(f"{_DEDUP_CTE} SELECT COUNT(*) FROM deduped").fetchone()[0]
    geocoded = conn.execute(f"{_DEDUP_CTE} SELECT COUNT(*) FROM deduped WHERE lat IS NOT NULL").fetchone()[0]
    retail_total = conn.execute(
        f"{_DEDUP_CTE} SELECT COUNT(*) FROM deduped WHERE retail_score >= ?", (RETAIL_THRESHOLD,)
    ).fetchone()[0]
    high_sev = conn.execute(
        f"{_DEDUP_CTE} SELECT COUNT(*) FROM deduped WHERE retail_score >= ? AND severity >= 4",
        (RETAIL_THRESHOLD,),
    ).fetchone()[0]
    by_type = conn.execute(
        f"{_DEDUP_CTE} SELECT incident_type, COUNT(*) as n FROM deduped GROUP BY incident_type ORDER BY n DESC"
    ).fetchall()
    conn.close()

    pipeline = {}
    if _STATUS_FILE.exists():
        try:
            pipeline = json.loads(_STATUS_FILE.read_text())
        except Exception:
            pass

    return jsonify({
        "total": total,
        "geocoded": geocoded,
        "retail_total": retail_total,
        "high_sev": high_sev,
        "by_type": {r["incident_type"]: r["n"] for r in by_type},
        "pipeline": pipeline,
    })


def _cluster(conn, where, params, field):
    rows = conn.execute(
        f"""
        WITH filtered AS (SELECT * FROM incidents WHERE {where}),
        deduped AS (
            SELECT * FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY event_key ORDER BY published_at DESC, id) rn
                FROM filtered WHERE event_key IS NOT NULL)
            WHERE rn = 1
            UNION ALL SELECT *, 1 rn FROM filtered WHERE event_key IS NULL)
        SELECT MIN({field}) AS key, COUNT(*) n,
               GROUP_CONCAT(DISTINCT state) states,
               GROUP_CONCAT(DISTINCT city) cities,
               MIN(published_at) first_seen, MAX(published_at) last_seen,
               GROUP_CONCAT(id) ids
        FROM deduped WHERE {field} IS NOT NULL AND TRIM({field}) != ''
        GROUP BY LOWER(TRIM({field})) HAVING COUNT(*) >= 2
        """,
        params,
    ).fetchall()
    return rows


@app.route("/api/patterns")
def patterns():
    conn = get_conn()
    conditions, params = _build_conditions(request.args, mapped_only=False)
    where = " AND ".join(conditions) if conditions else "1"
    clusters = []
    for kind, field in (("retailer", "retailer"), ("mo", "mo")):
        for r in _cluster(conn, where, params, field):
            clusters.append({
                "kind": kind, "key": r["key"], "count": r["n"],
                "states": (r["states"] or "").split(",") if r["states"] else [],
                "cities": (r["cities"] or "").split(",") if r["cities"] else [],
                "first_seen": r["first_seen"], "last_seen": r["last_seen"],
                "incident_ids": (r["ids"] or "").split(",") if r["ids"] else [],
            })
    conn.close()
    clusters.sort(key=lambda c: c["count"], reverse=True)
    return jsonify({"clusters": clusters})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5050)
