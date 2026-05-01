from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from backend.app.settings import Settings, get_settings


_ENGINE_CACHE: dict[str, Engine] = {}


def create_engine_for_settings(settings: Settings) -> Engine:
    settings.ensure_directories()
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection, connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.close()

    return engine


def get_engine(settings: Settings | None = None) -> Engine:
    resolved = settings or get_settings()
    key = resolved.database_url
    engine = _ENGINE_CACHE.get(key)
    if engine is None:
        engine = create_engine_for_settings(resolved)
        _ENGINE_CACHE[key] = engine
    return engine


def reset_engine_cache() -> None:
    for engine in _ENGINE_CACHE.values():
        engine.dispose()
    _ENGINE_CACHE.clear()


def session_for_settings(settings: Settings) -> Iterator[Session]:
    factory = sessionmaker(bind=get_engine(settings), autoflush=False, expire_on_commit=False)
    with factory() as session:
        yield session


def assert_database_ok(settings: Settings) -> None:
    with get_engine(settings).connect() as connection:
        connection.execute(text("SELECT 1"))
