from __future__ import annotations

import io
import json
import sqlite3
import tarfile
from dataclasses import replace
from pathlib import Path

import pytest

from backend.app.db.demo_seed import DEMO_PRIVATE_NAMES_META_KEY, seed_demo_profile
from backend.app.db.engine import get_engine
from backend.app.db.meta import get_app_meta
from backend.app.storage_export import (
    EXPORT_MANIFEST,
    StorageExportError,
    create_export_archive,
    restore_export_archive,
)


def _tar_names(path: Path) -> set[str]:
    with tarfile.open(path, "r:gz") as archive:
        return {member.name for member in archive.getmembers()}


def test_export_archive_contains_manifest_database_assets_and_excludes_tmp(migrated_settings):
    asset_file = migrated_settings.asset_dir / "demo" / "asset.txt"
    asset_file.parent.mkdir(parents=True, exist_ok=True)
    asset_file.write_text("asset bytes", encoding="utf-8")
    tmp_file = migrated_settings.asset_dir / ".tmp" / "partial.bin"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file.write_bytes(b"partial")

    artifact = create_export_archive(migrated_settings, timestamp="20260428T010203Z")

    assert artifact.archive_name == "myroll.20260428T010203Z.export.tar.gz"
    names = _tar_names(artifact.path)
    assert EXPORT_MANIFEST in names
    assert "db/myroll.sqlite3" in names
    assert "assets/demo/asset.txt" in names
    assert "assets/.tmp/partial.bin" not in names

    with tarfile.open(artifact.path, "r:gz") as archive:
        manifest_raw = archive.extractfile(EXPORT_MANIFEST)
        assert manifest_raw is not None
        manifest = json.loads(manifest_raw.read().decode("utf-8"))

    assert manifest["archive_name"] == artifact.archive_name
    assert manifest["database_path"] == "db/myroll.sqlite3"
    assert any(item["path"] == "assets/demo/asset.txt" and item["sha256"] for item in manifest["files"])


def test_restore_export_restores_db_and_assets_into_clean_target(migrated_settings, tmp_path):
    asset_file = migrated_settings.asset_dir / "demo" / "asset.txt"
    asset_file.parent.mkdir(parents=True, exist_ok=True)
    asset_file.write_text("restored asset", encoding="utf-8")
    artifact = create_export_archive(migrated_settings, timestamp="20260428T020304Z")

    target = tmp_path / "restored-data"
    restored = restore_export_archive(artifact.path, target)

    assert restored == target.resolve()
    assert (target / "myroll.dev.sqlite3").is_file()
    assert (target / "assets" / "demo" / "asset.txt").read_text(encoding="utf-8") == "restored asset"
    assert (target / "restored-export-manifest.json").is_file()

    connection = sqlite3.connect(target / "myroll.dev.sqlite3")
    try:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "20260504_0015"
    finally:
        connection.close()


def test_restore_export_refuses_non_empty_target_without_force(migrated_settings, tmp_path):
    artifact = create_export_archive(migrated_settings, timestamp="20260428T030405Z")
    target = tmp_path / "target"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(StorageExportError) as error:
        restore_export_archive(artifact.path, target)

    assert error.value.code == "target_not_empty"
    assert (target / "keep.txt").exists()


def test_restore_export_rejects_archive_path_traversal(tmp_path):
    archive_path = tmp_path / "bad.export.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo("../escape.txt")
        payload = b"escape"
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))

    with pytest.raises(StorageExportError) as error:
        restore_export_archive(archive_path, tmp_path / "target")

    assert error.value.code == "invalid_export_archive"
    assert not (tmp_path / "escape.txt").exists()


def test_demo_profile_seed_is_public_safe_and_does_not_run_ship_ambush_seed(migrated_settings):
    result = seed_demo_profile(migrated_settings)

    assert result.private_name_map_active is False
    with get_engine(migrated_settings).connect() as connection:
        campaigns = connection.exec_driver_sql("SELECT name FROM campaigns ORDER BY name").fetchall()
        assets = connection.exec_driver_sql("SELECT COUNT(*) FROM assets").scalar_one()
        widgets = connection.exec_driver_sql("SELECT kind FROM workspace_widgets WHERE kind = 'storage_demo'").fetchall()

    names = [row[0] for row in campaigns]
    assert "Chronicle of the Lantern Vale" in names
    assert "Demo Campaign: Ship Ambush" not in names
    assert assets >= 12
    assert widgets


def test_demo_profile_seed_applies_ignored_private_name_map(migrated_settings, tmp_path):
    private_map = tmp_path / "name-map.private.json"
    private_map.write_text(
        json.dumps(
            {
                "campaign.lantern_vale_chronicle": "Chronicle of the Witchlight",
                "entity.granny_scrap": "Skabatha Nightshade",
                "scene.crooked_loom_house": "Loomlurch",
            }
        ),
        encoding="utf-8",
    )
    private_settings = replace(migrated_settings, demo_name_map_path=private_map)

    result = seed_demo_profile(private_settings)

    assert result.private_name_map_active is True
    with get_engine(private_settings).connect() as connection:
        campaign_name = connection.exec_driver_sql("SELECT name FROM campaigns").fetchone()[0]
        entity_name = connection.exec_driver_sql(
            "SELECT name FROM entities WHERE id = ?",
            ("28c69045-6b76-5661-a642-e99c58adea0e",),
        ).fetchone()
        meta_value = get_app_meta(connection, DEMO_PRIVATE_NAMES_META_KEY)

    assert campaign_name == "Chronicle of the Witchlight"
    assert entity_name is None or entity_name[0] == "Skabatha Nightshade"
    assert meta_value == "true"


def test_committed_demo_files_do_not_contain_reserved_source_names():
    reserved = ("Witchlight", "Skabatha", "Zybilna", "Loomlurch", "Wizards", "Hasbro")
    paths = [
        Path("demo/assets/generated/lantern_vale_chronicle/manifest.json"),
        Path("demo/local/name-map.example.json"),
        Path("backend/app/db/demo_seed.py"),
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for term in reserved:
            assert term not in text
