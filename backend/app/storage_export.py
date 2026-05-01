from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from backend.app.db.backup import backup_existing_database
from backend.app.settings import Settings, get_settings


EXPORT_MANIFEST = "myroll-export.json"
DB_ARCHIVE_PATH = "db/myroll.sqlite3"
EXPORT_SUFFIX = ".export.tar.gz"


class StorageExportError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True)
class StorageArtifact:
    archive_name: str
    path: Path
    byte_size: int
    created_at: str


def timestamp_for_filename() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def iso_from_timestamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def directory_size(path: Path, *, exclude_tmp: bool = False) -> int:
    if not path.exists():
        return 0
    total = 0
    for child in path.rglob("*"):
        if exclude_tmp and ".tmp" in child.parts:
            continue
        if child.is_file():
            total += child.stat().st_size
    return total


def latest_file(path: Path, pattern: str) -> Path | None:
    if not path.exists():
        return None
    files = [candidate for candidate in path.glob(pattern) if candidate.is_file()]
    return max(files, key=lambda item: item.stat().st_mtime) if files else None


def profile_hint(settings: Settings) -> str:
    try:
        relative = settings.data_dir.relative_to(settings.project_root)
        if relative.parts[:2] == ("data", "demo"):
            return "demo"
    except ValueError:
        pass
    return "dev"


def backup_database(settings: Settings | None = None) -> Path | None:
    return backup_existing_database(settings or get_settings())


def _sqlite_snapshot(settings: Settings, out_path: Path) -> None:
    if not settings.db_path.exists() or settings.db_path.stat().st_size == 0:
        raise StorageExportError(404, "database_not_found", "Database file does not exist")
    try:
        source = sqlite3.connect(f"file:{settings.db_path}?mode=ro", uri=True)
        target = sqlite3.connect(out_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
    except sqlite3.Error as exc:
        raise StorageExportError(500, "database_backup_failed", "Database snapshot failed") from exc


def _tar_add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mtime = int(datetime.now(UTC).timestamp())
    archive.addfile(info, io.BytesIO(payload))


def _iter_asset_files(asset_dir: Path) -> list[Path]:
    if not asset_dir.exists():
        return []
    return sorted(
        path
        for path in asset_dir.rglob("*")
        if path.is_file() and ".tmp" not in path.relative_to(asset_dir).parts
    )


def create_export_archive(settings: Settings | None = None, *, timestamp: str | None = None) -> StorageArtifact:
    resolved = settings or get_settings()
    resolved.ensure_directories()
    stamp = timestamp or timestamp_for_filename()
    archive_name = f"myroll.{stamp}{EXPORT_SUFFIX}"
    final_path = resolved.export_dir / archive_name
    if final_path.exists():
        raise StorageExportError(409, "export_exists", "Export archive already exists")

    with tempfile.TemporaryDirectory(prefix="myroll-export-", dir=resolved.export_dir) as tmp_raw:
        tmp_dir = Path(tmp_raw)
        db_snapshot = tmp_dir / "myroll.sqlite3"
        _sqlite_snapshot(resolved, db_snapshot)
        tmp_archive = tmp_dir / f"{archive_name}.tmp"
        files: list[dict[str, Any]] = []

        with tarfile.open(tmp_archive, "w:gz") as archive:
            db_bytes = db_snapshot.stat().st_size
            archive.add(db_snapshot, arcname=DB_ARCHIVE_PATH)
            files.append(
                {
                    "path": DB_ARCHIVE_PATH,
                    "kind": "database",
                    "byte_size": db_bytes,
                    "sha256": sha256_file(db_snapshot),
                }
            )

            for asset_path in _iter_asset_files(resolved.asset_dir):
                relative = asset_path.relative_to(resolved.asset_dir).as_posix()
                archive_path = f"assets/{relative}"
                archive.add(asset_path, arcname=archive_path)
                files.append(
                    {
                        "path": archive_path,
                        "kind": "asset",
                        "byte_size": asset_path.stat().st_size,
                        "sha256": sha256_file(asset_path),
                    }
                )

            manifest = {
                "app": resolved.app_name,
                "version": resolved.app_version,
                "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "archive_name": archive_name,
                "format_version": 1,
                "database_path": DB_ARCHIVE_PATH,
                "asset_root": "assets",
                "files": files,
            }
            _tar_add_bytes(archive, EXPORT_MANIFEST, json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))

        os.replace(tmp_archive, final_path)

    return StorageArtifact(
        archive_name=archive_name,
        path=final_path,
        byte_size=final_path.stat().st_size,
        created_at=iso_from_timestamp(final_path),
    )


def _validate_archive_member(member: tarfile.TarInfo) -> PurePosixPath:
    name = member.name
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not name or name.startswith("./"):
        raise StorageExportError(400, "invalid_export_archive", "Export archive contains an unsafe path")
    if not (member.isfile() or member.isdir()):
        raise StorageExportError(400, "invalid_export_archive", "Export archive contains unsupported entries")
    if member.isfile() and name not in {EXPORT_MANIFEST, DB_ARCHIVE_PATH} and not name.startswith("assets/"):
        raise StorageExportError(400, "invalid_export_archive", "Export archive contains unexpected files")
    return path


def restore_export_archive(archive_path: Path, target_data_dir: Path, *, force: bool = False) -> Path:
    source = archive_path.expanduser().resolve()
    target = target_data_dir.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise StorageExportError(404, "export_not_found", "Export archive not found")
    if target.exists() and any(target.iterdir()):
        if not force:
            raise StorageExportError(409, "target_not_empty", "Target data directory is not empty")
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    asset_root = target / "assets"
    asset_root.mkdir(parents=True, exist_ok=True)

    with tarfile.open(source, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            _validate_archive_member(member)
        try:
            archive.getmember(DB_ARCHIVE_PATH)
        except KeyError:
            raise StorageExportError(400, "invalid_export_archive", "Export archive is missing the database")
        for member in members:
            if member.isdir():
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                raise StorageExportError(400, "invalid_export_archive", "Export archive contains unreadable files")
            if member.name == DB_ARCHIVE_PATH:
                destination = target / "myroll.dev.sqlite3"
            elif member.name == EXPORT_MANIFEST:
                destination = target / "restored-export-manifest.json"
            else:
                destination = target / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix=".restore-", dir=destination.parent, delete=False) as temp:
                temp_path = Path(temp.name)
                shutil.copyfileobj(extracted, temp)
            os.replace(temp_path, destination)
    return target
