import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PYTHON = str(Path(__file__).parent / "venv" / "Scripts" / "python.exe")
_PYTHON_FLAGS = ["-u"]  # unbuffered stdout so background logs appear immediately
HERE = Path(__file__).parent


def run(label: str, script: str, *args):
    print(f"\n[{_now()}] {label}")
    result = subprocess.run(
        [PYTHON, *_PYTHON_FLAGS, script, *args],
        cwd=HERE,
    )
    if result.returncode != 0:
        print(f"  !! {script} exited with code {result.returncode}")
    return result.returncode == 0


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


STATUS_FILE = HERE / "pipeline_status.json"


def _write_status(status: str, extra: dict = None):
    data = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
    if extra:
        data.update(extra)
    STATUS_FILE.write_text(json.dumps(data))


def main():
    started = datetime.now(timezone.utc).isoformat()
    _write_status("running", {"started_at": started})
    print(f"=== pipeline start {_now()} ===")

    run("collecting RSS feeds",   "collector.py")
    run("collecting Reddit",      "reddit_collector.py")

    # Drain extractor in passes until no unprocessed articles remain
    for pass_num in range(1, 10):
        print(f"\n[{_now()}] extracting (pass {pass_num})")
        result = subprocess.run(
            [PYTHON, *_PYTHON_FLAGS, "extractor.py", "--llm"],
            cwd=HERE,
            capture_output=False,
        )
        output = subprocess.run(
            [PYTHON, *_PYTHON_FLAGS, "-c",
             "from db import get_conn; c=get_conn(); "
             "print(c.execute('SELECT COUNT(*) FROM raw_articles WHERE processed=0').fetchone()[0])"],
            cwd=HERE,
            capture_output=True,
            text=True,
        ).stdout.strip()
        remaining = int(output) if output.isdigit() else 0
        print(f"  unprocessed remaining: {remaining}")
        if remaining == 0:
            break

    run("geocoding",              "geocoder.py")

    print(f"\n=== pipeline done {_now()} ===")

    # Print final stats (scratch helper is gitignored; skip if absent)
    if (HERE / "scratch" / "_scratch-stats.py").exists():
        subprocess.run(
            [PYTHON, *_PYTHON_FLAGS, "-c", "exec(open('scratch/_scratch-stats.py').read())"],
            cwd=HERE,
        )

    _write_status("done", {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat()})


if __name__ == "__main__":
    main()
