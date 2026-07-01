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
