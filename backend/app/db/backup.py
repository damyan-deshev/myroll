from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from backend.app.settings import Settings, get_settings


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _backup_name(db_path: Path, timestamp: str) -> str:
    if db_path.name.endswith(".sqlite3"):
        base = db_path.name[: -len(".sqlite3")]
        ext = ".sqlite3"
    else:
        base = db_path.stem
        ext = db_path.suffix or ".sqlite3"
    return f"{base}.{timestamp}.pre-migration{ext}"


def backup_existing_database(
    settings: Settings | None = None,
    timestamp: str | None = None,
) -> Path | None:
    resolved = settings or get_settings()
    db_path = resolved.db_path
    if not db_path.exists() or db_path.stat().st_size == 0:
        return None
    resolved.backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = resolved.backup_dir / _backup_name(db_path, timestamp or _timestamp())
    try:
        source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        target = sqlite3.connect(backup_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
    except sqlite3.Error:
        shutil.copy2(db_path, backup_path)
    return backup_path


def main() -> None:
    backup_path = backup_existing_database()
    if backup_path is None:
        print("No existing non-empty DB; skipping pre-migration backup.")
    else:
        print(f"Created pre-migration backup: {backup_path}")


if __name__ == "__main__":
    main()
