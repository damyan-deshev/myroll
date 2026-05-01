from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_utc_z(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Naive datetimes are forbidden at API boundaries")
    utc_value = value.astimezone(UTC)
    return utc_value.replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def utc_now_z() -> str:
    return to_utc_z(utc_now())
