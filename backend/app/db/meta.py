from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


def get_schema_version(session: Session) -> str | None:
    try:
        return session.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
    except SQLAlchemyError:
        return None


def get_app_meta(session: Session, key: str) -> str | None:
    try:
        return session.execute(
            text("SELECT value FROM app_meta WHERE key = :key"),
            {"key": key},
        ).scalar_one_or_none()
    except SQLAlchemyError:
        return None
