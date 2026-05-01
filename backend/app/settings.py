from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from sqlalchemy.engine import URL


APP_NAME = "myroll"
APP_VERSION = "dev"


def _csv_setting(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    db_path: Path
    asset_dir: Path
    backup_dir: Path
    export_dir: Path
    seed_mode: str = "dev"
    demo_name_map_path: Path | None = None
    host: str = "127.0.0.1"
    port: int = 8000
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")
    allowed_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")
    app_name: str = APP_NAME
    app_version: str = APP_VERSION

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = env if env is not None else os.environ
        root = project_root()
        data_dir = Path(source.get("MYROLL_DATA_DIR", root / "data")).expanduser()
        db_path = Path(source.get("MYROLL_DB_PATH", data_dir / "myroll.dev.sqlite3")).expanduser()
        asset_dir = Path(source.get("MYROLL_ASSET_DIR", data_dir / "assets")).expanduser()
        backup_dir = Path(source.get("MYROLL_BACKUP_DIR", data_dir / "backups")).expanduser()
        export_dir = Path(source.get("MYROLL_EXPORT_DIR", data_dir / "exports")).expanduser()
        seed_mode = source.get("MYROLL_SEED_MODE", "dev").strip().lower() or "dev"
        demo_name_map_raw = source.get("MYROLL_DEMO_NAME_MAP_PATH")
        demo_name_map_path = Path(demo_name_map_raw).expanduser() if demo_name_map_raw else root / "demo" / "local" / "name-map.private.json"
        host = source.get("MYROLL_HOST", "127.0.0.1")
        port = int(source.get("MYROLL_PORT", "8000"))
        configured_hosts = _csv_setting(source.get("MYROLL_ALLOWED_HOSTS"))
        allowed_hosts = configured_hosts or tuple(dict.fromkeys(("127.0.0.1", "localhost", host)))
        configured_origins = _csv_setting(source.get("MYROLL_ALLOWED_ORIGINS"))
        allowed_origins = configured_origins or ("http://127.0.0.1:5173", "http://localhost:5173")
        return cls(
            project_root=root,
            data_dir=data_dir.resolve(),
            db_path=db_path.resolve(),
            asset_dir=asset_dir.resolve(),
            backup_dir=backup_dir.resolve(),
            export_dir=export_dir.resolve(),
            seed_mode=seed_mode,
            demo_name_map_path=demo_name_map_path.resolve(),
            host=host,
            port=port,
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        )

    @property
    def database_url(self) -> str:
        return URL.create("sqlite+pysqlite", database=str(self.db_path)).render_as_string(
            hide_password=False
        )

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.asset_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def short_db_path(self) -> str:
        try:
            return str(self.db_path.relative_to(self.project_root))
        except ValueError:
            return f".../{self.db_path.name}"

    def short_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.project_root))
        except ValueError:
            return f".../{path.name}"


def get_settings() -> Settings:
    return Settings.from_env()
