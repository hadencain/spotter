import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from db import get_conn, init_db

_STATUS_FILE = Path(__file__).parent / "pipeline_status.json"

app = Flask(__name__)

RETAIL_THRESHOLD = 0.4


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
        f"SELECT * FROM incidents WHERE {where} ORDER BY published_at DESC LIMIT 3000",
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
    total = conn.execute(f"SELECT COUNT(*) FROM incidents WHERE {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM incidents WHERE {where} ORDER BY {sort_col} {sort_dir} LIMIT ? OFFSET ?",
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
    total = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    geocoded = conn.execute("SELECT COUNT(*) FROM incidents WHERE lat IS NOT NULL").fetchone()[0]
    by_type = conn.execute(
        "SELECT incident_type, COUNT(*) as n FROM incidents GROUP BY incident_type ORDER BY n DESC"
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
        "by_type": {r["incident_type"]: r["n"] for r in by_type},
        "pipeline": pipeline,
    })


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5050)
