import hashlib
import socket
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

socket.setdefaulttimeout(10)  # don't hang forever on slow/dead feeds

from db import get_conn, init_db
from sources import RSS_FEEDS


def _article_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_date(date_str: str) -> str:
    """Normalize any date string to ISO 8601 UTC for consistent SQLite comparisons."""
    if not date_str:
        return ""
    try:
        return datetime.fromisoformat(date_str).isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    return date_str


def _insert_raw(conn, source: str, url: str, headline: str, published_at: str, text: str):
    article_id = _article_id(url)
    try:
        conn.execute(
            """INSERT INTO raw_articles
               (id, source, source_url, headline, published_at, ingested_at, raw_text)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (article_id, source, url, headline, published_at, _now(), text),
        )
        conn.commit()
        return True
    except Exception:
        return False  # duplicate URL — already have it


def collect_rss(conn):
    new_count = 0
    for feed_cfg in RSS_FEEDS:
        name = feed_cfg["name"]
        try:
            feed = feedparser.parse(feed_cfg["url"])
            for entry in feed.entries:
                url = entry.get("link", "")
                headline = entry.get("title", "")
                published_at = _normalize_date(entry.get("published", ""))
                summary = entry.get("summary", "")
                if url and _insert_raw(conn, name, url, headline, published_at, summary):
                    new_count += 1
            print(f"  {name}: {len(feed.entries)} entries")
        except Exception as e:
            print(f"  {name} failed: {e}")
        time.sleep(0.5)
    return new_count


def run_once():
    init_db()
    conn = get_conn()
    print(f"[{_now()}] collecting...")
    new = collect_rss(conn)
    print(f"  done — {new} new articles ingested")
    conn.close()


def run_loop(interval_seconds: int = 300):
    print(f"feed collector running — polling every {interval_seconds}s")
    while True:
        run_once()
        time.sleep(interval_seconds)


if __name__ == "__main__":
    import sys
    if "--loop" in sys.argv:
        run_loop()
    else:
        run_once()
