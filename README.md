# Spotter

An experimental news-incident aggregator, retail-first. It pulls public crime/safety
reporting from RSS feeds, Google News queries, and Reddit, uses an LLM to extract a
structured incident (location, type, severity, and retail entities) from each article,
geocodes it, and plots the results on a map.

The focus is retail / public-space incidents — mall and shopping-center crime, organized
retail crime, parking-lot incidents, and similar. Every incident is scored for retail
relevance (`retail_score`), and the UI defaults to a **Retail** view (with an **All**
toggle) ranked retail-first. The source list is just a registry you can edit.

## ⚠️ Caveats — read before trusting anything on the map

- **Extraction is lossy.** Location and category are inferred by an LLM (Claude Haiku)
  from headlines and, for retail candidates, the fetched article body. It gets things
  wrong — sometimes parsing a headline fragment as a place. Treat the map as a rough
  situational-awareness sketch, **not an authoritative record**. Do not use it to make
  claims about specific businesses or locations.
- **Entity fields are LLM-derived leads, not verified facts.** `retailer`, `loss_value`,
  `suspect_count`, `mo`, and `arrested` are pulled from public reporting by the LLM and can
  be wrong, incomplete, or mis-attributed. Treat them as **investigative leads to check
  against the source article, not accusations or confirmed facts.** `suspect_count` is a
  count only, never treat it as identifying information.
- **Geocoding is approximate** and lands in one of four confidence tiers — see
  `geo_confidence` below. Roughly 60% of incidents resolve to a precise point; the rest
  fall back to a city or state centroid (dashed pin) or stay ungeocoded (visible in
  Reports, absent from the map).
- All data is derived from already-public sources, but aggregation is its own artifact.
  Be thoughtful about republishing the resulting database.

## What's here / not here

The code is published; the **data is not**. `intel.db` (the SQLite store of extracted
incidents) is gitignored, along with the venv and local run state. Clone this and you get a
clean, empty tool — run the pipeline to populate your own database.

## Setup

```bash
python -m venv venv
venv/Scripts/activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt

# LLM extraction needs an Anthropic API key:
export ANTHROPIC_API_KEY=sk-ant-...
```

## Run

```bash
python run_pipeline.py   # collect -> extract (LLM, retail-scored) -> geocode -> stats
python app.py            # serve the map at http://127.0.0.1:5050
```

`run_pipeline.py` runs the full chain. The collector ingests raw articles; the extractor
prefilters retail candidates by keyword, fetches full article bodies for those candidates
(`enrich.py`, via `trafilatura`), and runs the LLM only on that subset to extract location,
`retail_score`, and entity fields — bounded cost, focused on the data that matters.
Non-candidates still get the cheap keyword/regex path (`retail_score=0`). The extractor
drains unprocessed articles in passes; geocoding uses OpenStreetMap Nominatim
(rate-limited, no key). Without an API key the LLM step is skipped and only keyword-based
classification runs.

### One-time backfill for an existing database

The retail-scoring/entity/dedup fields above were added in a schema migration. New
articles get them automatically as they run through the normal pipeline. To enrich
incidents that are **already** in your database from before this refresh, run the backfill
once:

```bash
venv/Scripts/python extractor.py --retail-backfill
```

This reprocesses existing retail-candidate incidents to populate `retail_score`,
`retailer`, `loss_value`, `suspect_count`, `mo`, `arrested`, and `event_key` without
touching rows that are already enriched or deleting anything.

## Incident fields

Beyond the original `headline` / `location` / `incident_type` / `severity` fields, each
incident carries:

| Field | Type | Meaning |
|---|---|---|
| `retail_score` | 0–1 float | Confidence the incident is retail/public-space relevant. The Retail view filters on `retail_score >= 0.4` (server-side constant, not user-adjustable). |
| `retailer` | text | Named store/chain/venue, if reported. |
| `loss_value` | text | Estimated dollar loss as reported (free text, e.g. `"~$120k"`; often null). |
| `suspect_count` | int | Approx. number of suspects involved; a count, not PII. |
| `mo` | text | Modus operandi as reported (e.g. "flash-mob grab", "smash-and-grab"). |
| `arrested` | int/null | `1` = arrest(s) made, `0` = at large, `null` = unknown. |
| `geo_confidence` | text | `point` (geocoded to the reported address), `city` (city centroid fallback), `state` (state centroid fallback), or `none` (not geocoded — no map pin, still visible in Reports). Map pins are solid for `point`, dashed for `city`/`state` fallbacks. |
| `event_key` | text | Deterministic dedup key (state/city/type/date) grouping multiple outlets' reports of the same real-world event. |

All entity fields (`retailer`, `loss_value`, `suspect_count`, `mo`, `arrested`) are
populated only for retail candidates that clear the LLM extraction step; other incidents
carry `retail_score=0` and null entity fields.

## Event de-duplication

Multiple outlets often cover the same incident. Rather than showing N duplicate rows,
`/api/incidents`, `/api/reports`, and `/api/patterns` group rows by `event_key` and surface
one representative row per real-world event, with an `n_sources` count showing how many
outlets reported it. Nothing is deleted — the underlying duplicate rows stay in the
database; only the API/UI views collapse them.

## Views

- **Map** — pins colored by category, solid/dashed per `geo_confidence`, retail-first
  ordering (`retail_score DESC, severity DESC, published_at DESC`), Retail/All toggle,
  category strip filter, duration window select.
- **Reports** — sortable intel table: score, category, headline (+ source count),
  retailer/MO, estimated loss, location, arrest status.
- **Patterns** (`/api/patterns`) — clusters incidents by `retailer` and by `mo` across the
  current filter window (min. 2 occurrences per cluster), each cluster reporting
  `{key, kind, count, states, cities, first_seen, last_seen, incident_ids}`. This is the
  ORC-intelligence payoff: it surfaces repeat retailers being hit and repeat MOs/crews
  moving across locations.
- **Ticker** — bottom sliding banner of recent reports (`/api/reports?since=24h`).

## Dependencies

The following runtime dependencies are pinned in `requirements.txt`:
- **feedparser** — RSS feed parsing
- **requests** — HTTP client
- **flask** — Web server for the map interface
- **anthropic** — LLM extraction via Claude
- **trafilatura** — Article body text extraction from HTML (used for retail candidates)

`requirements-dev.txt` adds **pytest**, used to run the offline test suite
(`venv/Scripts/python -m pytest -q`).

## Layout

| File | Role |
|------|------|
| `sources.py` | Feed registry — RSS, Google News queries, Reddit targets |
| `collector.py` / `reddit_collector.py` | Ingest raw articles |
| `enrich.py` | Article body fetching via trafilatura |
| `extractor.py` | Retail prefilter + LLM/keyword extraction into structured incidents, `--retail-backfill` for existing DBs |
| `geocoder.py` | Resolve locations via Nominatim with confidence tiers (cached) |
| `db.py` | SQLite schema + connection |
| `app.py` | Flask map + reports + patterns API |
| `run_pipeline.py` | Orchestrates the full pass |

## License

No warranty. Provided as-is for research and situational-awareness experimentation.
