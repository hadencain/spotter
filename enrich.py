import trafilatura


def fetch_body(url: str) -> str:
    """Fetch and clean article body text. Returns '' on any failure. Never raises."""
    if not url:
        return ""
    try:
        html = trafilatura.fetch_url(url)
        if not html:
            return ""
        text = trafilatura.extract(html, include_comments=False, include_tables=False)
        return (text or "").strip()
    except Exception:
        return ""
