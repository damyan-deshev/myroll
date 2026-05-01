from __future__ import annotations

import uuid


SEED_NAMESPACE = uuid.UUID("4e8b4788-e36b-5f3b-b569-80b1f238d7d7")


def deterministic_uuid(name: str) -> str:
    return str(uuid.uuid5(SEED_NAMESPACE, name))
