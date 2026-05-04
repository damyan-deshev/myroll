from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import CampaignMemoryEntry, Entity, SessionRecap
from backend.app.review_rule_packs import find_phrase_rule_matches, load_phrase_rules


SENSITIVITY_REASONS = {"spoiler", "gm_only_motive", "unrevealed_clue", "future_plan", "private_note", "other"}


PUBLIC_SAFETY_WARNING_RULES = load_phrase_rules("public_safety.json", "publicSafetyWarnings")


def canonical_public_content(title: str | None, body_markdown: str) -> str:
    title_text = unicodedata.normalize("NFC", (title or "").strip()).replace("\r\n", "\n").replace("\r", "\n")
    body_text = unicodedata.normalize("NFC", body_markdown.strip()).replace("\r\n", "\n").replace("\r", "\n")
    return f"{title_text}\n---MYROLL-PUBLIC-BODY---\n{body_text}"


def public_content_hash(title: str | None, body_markdown: str) -> str:
    return hashlib.sha256(canonical_public_content(title, body_markdown).encode("utf-8")).hexdigest()


def _excerpt(value: str, start: int, end: int, radius: int = 32) -> str:
    left = max(0, start - radius)
    right = min(len(value), end + radius)
    return value[left:right].strip()


def private_reference_terms(db: Session, campaign_id: str) -> list[str]:
    terms: list[str] = []
    entities = db.scalars(select(Entity).where(Entity.campaign_id == campaign_id, Entity.visibility != "public_known"))
    for entity in entities:
        for value in (entity.name, entity.display_name):
            if value and len(value.strip()) >= 3:
                terms.append(value.strip())
    recaps = db.scalars(select(SessionRecap).where(SessionRecap.campaign_id == campaign_id, SessionRecap.public_safe.is_(False)))
    for recap in recaps:
        if recap.title and len(recap.title.strip()) >= 3:
            terms.append(recap.title.strip())
    memories = db.scalars(select(CampaignMemoryEntry).where(CampaignMemoryEntry.campaign_id == campaign_id, CampaignMemoryEntry.public_safe.is_(False)))
    for memory in memories:
        if memory.title and len(memory.title.strip()) >= 3:
            terms.append(memory.title.strip())
    return sorted(set(terms), key=str.casefold)


def scan_public_safety_text(
    *,
    title: str | None,
    body_markdown: str,
    private_terms: Iterable[str] = (),
) -> tuple[list[dict[str, str]], str]:
    text = canonical_public_content(title, body_markdown)
    warnings: list[dict[str, str]] = []
    seen_phrase_codes: set[str] = set()
    for rule, start, end in find_phrase_rule_matches(text, PUBLIC_SAFETY_WARNING_RULES):
        if rule.code in seen_phrase_codes:
            continue
        seen_phrase_codes.add(rule.code)
        warnings.append(
            {
                "code": rule.code,
                "severity": rule.severity,
                "message": rule.message,
                "matched_text": _excerpt(text, start, end),
                "rule_pack": rule.rule_pack,
                "matched_phrase": rule.phrase,
            }
        )
    lowered = text.casefold()
    for term in private_terms:
        normalized = term.strip()
        if not normalized:
            continue
        index = lowered.find(normalized.casefold())
        if index >= 0:
            warnings.append(
                {
                    "code": "private_reference",
                    "severity": "high",
                    "message": "Matches a private-only campaign reference.",
                    "matched_text": _excerpt(text, index, index + len(normalized)),
                }
            )
    return warnings, public_content_hash(title, body_markdown)


def warning_ack_required(warnings: list[dict[str, str]]) -> bool:
    severities = [str(warning.get("severity") or "") for warning in warnings]
    return any(severity in {"high", "medium"} for severity in severities) or severities.count("low") >= 3


def warnings_for_storage(warnings: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "code": str(warning.get("code") or "unknown_warning"),
            "severity": str(warning.get("severity") or "low"),
            "message": str(warning.get("message") or "Public-safety warning."),
        }
        for warning in warnings
    ]


def sanitize_public_markdown(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\((?:https?://|mailto:)[^)]+\)", r"\1", text, flags=re.IGNORECASE)
    lines: list[str] = []
    for raw_line in text.split("\n"):
        line = re.sub(r"^\s{0,3}#{1,6}\s+", "", raw_line)
        lines.append(line.rstrip())
    return "\n".join(lines).strip()
