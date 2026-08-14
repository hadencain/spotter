"""Outbound HTTP identity for every request Spotter makes.

Nominatim's usage policy requires a User-Agent that identifies the application
and gives operators a way to reach whoever is running it; Reddit and most feed
hosts ask for the same. The default points at the project rather than a person.

If you run your own instance — especially at any volume — set
SPOTTER_USER_AGENT so your traffic lands on your own identity. Every clone
sharing one string means one clone's abuse gets all of them rate-limited.
"""

import os

DEFAULT_USER_AGENT = "spotter/0.1 (+https://github.com/hadencain/spotter)"

USER_AGENT = os.environ.get("SPOTTER_USER_AGENT", "").strip() or DEFAULT_USER_AGENT
