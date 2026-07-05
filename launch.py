"""
Desktop launcher for Spotter.

Runs the Flask app as a single foreground process (no debug reloader), opens
the map in your browser, and serves until this console window is closed.
Closing the window terminates this process and frees port 5050 — nothing is
left running in the background.
"""
import threading
import time
import webbrowser

from app import app
from db import init_db

PORT = 5050
URL = f"http://127.0.0.1:{PORT}"


def _open_browser():
    time.sleep(1.2)  # give the server a moment to bind
    webbrowser.open(URL)


if __name__ == "__main__":
    init_db()
    threading.Thread(target=_open_browser, daemon=True).start()
    print("=" * 48)
    print("  Spotter is running at " + URL)
    print("  Close this window to stop the server.")
    print("=" * 48)
    # Single process, reloader off -> closing this window frees the port.
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
