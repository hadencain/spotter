import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the app at a throwaway SQLite file and initialize the schema."""
    db_file = tmp_path / "test_intel.db"
    monkeypatch.setenv("SPOTTER_DB", str(db_file))
    import db as db_module
    importlib.reload(db_module)
    db_module.init_db()
    return db_module
