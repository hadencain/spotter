def test_get_conn_uses_spotter_db_env(temp_db, tmp_path):
    conn = temp_db.get_conn()
    # The connected file is the temp file, not the real intel.db
    (path,) = conn.execute("PRAGMA database_list").fetchone()[2:3]
    conn.close()
    assert str(tmp_path) in path
