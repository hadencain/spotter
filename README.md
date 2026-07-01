# Spotter

An experimental news-incident aggregator. It pulls public crime/safety reporting from
RSS feeds, Google News queries, and Reddit, uses an LLM to extract a structured incident
(location, type, severity) from each headline, geocodes it, and plots the results on a map.

The focus is retail / public-space incidents — mall and shopping-center crime, organized
retail crime, parking-lot incidents, and similar — but the source list is just a registry
you can edit.

## ⚠️ Caveats — read before trusting anything on the map

- **Extraction is lossy.** Locations are inferred from headlines by an LLM (Claude Haiku).
  It gets things wrong — sometimes parsing a headline fragment as a place. Treat the map as
  a rough situational-awareness sketch, **not an authoritative record**. Do not use it to
  make claims about specific businesses or locations.
- **Geocoding is approximate** and roughly 60% successful; many incidents have no point.
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
python run_pipeline.py   # collect -> extract (LLM) -> geocode -> stats
python app.py            # serve the map at http://127.0.0.1:5050
```

`run_pipeline.py` runs the full chain. The extractor drains unprocessed articles in passes;
geocoding uses OpenStreetMap Nominatim (rate-limited, no key). Without an API key the LLM
step is skipped and only keyword-based classification runs.

## Dependencies

The following runtime dependencies are pinned in `requirements.txt`:
- **feedparser** — RSS feed parsing
- **requests** — HTTP client
- **flask** — Web server for the map interface
- **anthropic** — LLM extraction via Claude
- **trafilatura** — Article body text extraction from HTML

Testing uses **pytest** (in `requirements-dev.txt` if applicable).

## Layout

| File | Role |
|------|------|
| `sources.py` | Feed registry — RSS, Google News queries, Reddit targets |
| `collector.py` / `reddit_collector.py` | Ingest raw articles |
| `enrich.py` | Article body fetching via trafilatura |
| `extractor.py` | LLM + keyword extraction into structured incidents |
| `geocoder.py` | Resolve locations via Nominatim (cached) |
| `db.py` | SQLite schema + connection |
| `app.py` | Flask map + reports API |
| `run_pipeline.py` | Orchestrates the full pass |

## License

No warranty. Provided as-is for research and situational-awareness experimentation.
