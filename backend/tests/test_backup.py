from __future__ import annotations

import sqlite3

from backend.app.db.backup import backup_existing_database


def test_backup_skips_missing_and_empty_db(test_settings):
    assert backup_existing_database(test_settings, timestamp="20260427T014512Z") is None
    test_settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    test_settings.db_path.write_bytes(b"")
    assert backup_existing_database(test_settings, timestamp="20260427T014512Z") is None


def test_backup_copies_existing_non_empty_db(test_settings):
    test_settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    test_settings.db_path.write_bytes(b"sqlite bytes")
    backup_path = backup_existing_database(test_settings, timestamp="20260427T014512Z")
    assert backup_path is not None
    assert backup_path.name == "myroll.test.20260427T014512Z.pre-migration.sqlite3"
    assert backup_path.read_bytes() == b"sqlite bytes"


def test_backup_uses_sqlite_snapshot_for_valid_db(test_settings):
    test_settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(test_settings.db_path)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("CREATE TABLE demo (id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO demo (id) VALUES ('seeded')")
        connection.commit()
    finally:
        connection.close()

    backup_path = backup_existing_database(test_settings, timestamp="20260427T014512Z")
    assert backup_path is not None
    backup = sqlite3.connect(backup_path)
    try:
        value = backup.execute("SELECT id FROM demo").fetchone()[0]
    finally:
        backup.close()
    assert value == "seeded"
