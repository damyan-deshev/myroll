from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from backend.app.settings import Settings, get_settings


def alembic_config(settings: Settings | None = None) -> Config:
    resolved = settings or get_settings()
    resolved.ensure_directories()
    config_path = resolved.project_root / "alembic.ini"
    config = Config(str(config_path))
    config.set_main_option("script_location", str(resolved.project_root / "backend" / "alembic"))
    config.set_main_option("sqlalchemy.url", resolved.database_url)
    config.attributes["settings"] = resolved
    return config


def upgrade_head(settings: Settings | None = None) -> None:
    command.upgrade(alembic_config(settings), "head")


def main(argv: list[str] | None = None) -> None:
    args = argv or sys.argv[1:]
    if args not in (["upgrade"], ["upgrade", "head"]):
        raise SystemExit("Usage: python -m backend.app.db.migrate upgrade [head]")
    upgrade_head()


if __name__ == "__main__":
    main()
