from __future__ import annotations

import pytest

from backend.app.db.engine import reset_engine_cache
from backend.app.db.migrate import upgrade_head
from backend.app.db.seed import seed_demo_data
from backend.app.settings import Settings


@pytest.fixture
def test_settings(tmp_path, monkeypatch) -> Settings:
    data_dir = tmp_path / "data"
    db_path = data_dir / "myroll.test.sqlite3"
    monkeypatch.setenv("MYROLL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("MYROLL_DB_PATH", str(db_path))
    monkeypatch.setenv("MYROLL_ASSET_DIR", str(data_dir / "assets"))
    monkeypatch.setenv("MYROLL_BACKUP_DIR", str(data_dir / "backups"))
    monkeypatch.setenv("MYROLL_EXPORT_DIR", str(data_dir / "exports"))
    monkeypatch.setenv("MYROLL_SEED_MODE", "dev")
    monkeypatch.setenv("MYROLL_HOST", "127.0.0.1")
    monkeypatch.setenv("MYROLL_PORT", "8000")
    reset_engine_cache()
    settings = Settings.from_env()
    yield settings
    reset_engine_cache()


@pytest.fixture
def migrated_settings(test_settings: Settings) -> Settings:
    upgrade_head(test_settings)
    return test_settings


@pytest.fixture
def seeded_settings(migrated_settings: Settings) -> Settings:
    seed_demo_data(migrated_settings)
    return migrated_settings
