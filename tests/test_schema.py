NEW_COLS = {
    "retail_score", "retailer", "loss_value", "suspect_count",
    "mo", "arrested", "event_key", "geo_confidence",
}


def _cols(db):
    conn = db.get_conn()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(incidents)")}
    conn.close()
    return cols


def test_new_columns_present(temp_db):
    assert NEW_COLS <= _cols(temp_db)


def test_migration_is_idempotent(temp_db):
    temp_db.init_db()  # second call must not raise
    assert NEW_COLS <= _cols(temp_db)


def test_migration_upgrades_old_shape_db(temp_db):
    conn = temp_db.get_conn()
    conn.executescript("DROP TABLE incidents; CREATE TABLE incidents (id TEXT PRIMARY KEY, headline TEXT);")
    conn.commit()
    conn.close()
    temp_db.init_db()  # should add the missing columns to the reduced table
    assert NEW_COLS <= _cols(temp_db)


def test_migration_preserves_existing_rows(temp_db):
    conn = temp_db.get_conn()
    conn.executescript("DROP TABLE incidents; CREATE TABLE incidents (id TEXT PRIMARY KEY, headline TEXT);")
    conn.execute("INSERT INTO incidents (id, headline) VALUES ('keep1', 'original headline')")
    conn.commit(); conn.close()
    temp_db.init_db()
    conn = temp_db.get_conn()
    row = conn.execute("SELECT headline FROM incidents WHERE id='keep1'").fetchone()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(incidents)")}
    conn.close()
    assert row is not None and row["headline"] == "original headline"
    assert "retail_score" in cols


def test_indexes_created(temp_db):
    conn = temp_db.get_conn()
    idx = {r["name"] for r in conn.execute("PRAGMA index_list(incidents)")}
    conn.close()
    assert {"idx_incidents_retail", "idx_incidents_event"} <= idx
