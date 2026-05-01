from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from backend.app.db.engine import create_engine_for_settings
from backend.app.db.models import Base
from backend.app.settings import get_settings


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _settings():
    configured = config.attributes.get("settings")
    if configured is not None:
        return configured
    return get_settings()


def run_migrations_offline() -> None:
    settings = _settings()
    settings.ensure_directories()
    config.set_main_option("sqlalchemy.url", settings.database_url)
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    settings = _settings()
    config.set_main_option("sqlalchemy.url", settings.database_url)
    connectable = create_engine_for_settings(settings)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
