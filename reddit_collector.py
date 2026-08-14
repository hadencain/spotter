import hashlib
import time
import urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from db import get_conn, init_db
from user_agent import USER_AGENT

# ---------------------------------------------------------------------------
# Source definitions
# ---------------------------------------------------------------------------

_SUBREDDITS = [
    "LossPrevention",
    "SecurityGuard",
    "retailhell",
    "TalesFromRetail",
    "walmartfights",
    "CrimeScene",
    "Missing411",
    "CCW",
    "HomeDefense",
]

_SEARCH_QUERIES = [
    "mall shooting",
    "mall stabbing",
    "mall robbery",
    "mall fight",
    "mall lockdown",
    "shopping center shooting",
    "smash and grab",
    "organized retail crime",
    "loss prevention shooting",
    "shoplifting arrest",
    "parking lot shooting",
    "carjacking mall",
    "active shooter store",
    "bomb threat mall",
    "amber alert",
    "retail worker attacked",
    "teen mob store",
]


def _subreddit_url(sub: str) -> str:
    return f"https://www.reddit.com/r/{sub}/new.rss"


def _search_url(query: str) -> str:
    q = urllib.parse.quote_plus(query)
    return f"https://www.reddit.com/search.rss?q={q}&sort=new&t=week"


# ---------------------------------------------------------------------------
# Ingest helpers
# ---------------------------------------------------------------------------

def _normalize_date(date_str: str) -> str:
    if not date_str:
        return datetime.now(timezone.utc).isoformat()
    try:
        return datetime.fromisoformat(date_str).isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    return datetime.now(timezone.utc).isoformat()


def _article_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _insert(conn, source: str, url: str, headline: str, published_at: str, text: str) -> bool:
    article_id = _article_id(url)
    try:
        conn.execute(
            """INSERT INTO raw_articles
               (id, source, source_url, headline, published_at, ingested_at, raw_text)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (article_id, source, url, headline, published_at, _now(), text[:600]),
        )
        conn.commit()
        return True
    except Exception:
        return False  # duplicate


def _collect_feed(conn, name: str, url: str) -> int:
    try:
        feed = feedparser.parse(url, agent=USER_AGENT)
        added = 0
        for entry in feed.entries:
            link = entry.get("link", "")
            title = entry.get("title", "")
            published = _normalize_date(entry.get("published", ""))
            summary = entry.get("summary", "")
            if link and _insert(conn, name, link, title, published, summary):
                added += 1
        print(f"  {name}: {len(feed.entries)} entries, {added} new")
        return added
    except Exception as e:
        print(f"  {name} failed: {e}")
        return 0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_once():
    init_db()
    conn = get_conn()
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] collecting reddit...")

    total = 0

    for sub in _SUBREDDITS:
        total += _collect_feed(conn, f"Reddit: r/{sub}", _subreddit_url(sub))
        time.sleep(1.2)

    for query in _SEARCH_QUERIES:
        total += _collect_feed(conn, f"Reddit search: {query}", _search_url(query))
        time.sleep(1.2)

    print(f"  done — {total} new reddit posts ingested")
    conn.close()


if __name__ == "__main__":
    run_once()
