from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


RULE_PACK_DIR = Path(__file__).resolve().parent / "llm_review_rules"


@dataclass(frozen=True)
class PhraseRule:
    code: str
    severity: str
    phrase: str
    message: str
    languages: tuple[str, ...]
    rule_pack: str
    section: str


def _text(value: object, default: str = "") -> str:
    if isinstance(value, str):
        return value.strip()
    return default


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def load_phrase_rules(file_name: str, section: str, *, allowed_codes: set[str] | None = None) -> tuple[PhraseRule, ...]:
    try:
        payload = json.loads((RULE_PACK_DIR / file_name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    rules = payload.get(section)
    if not isinstance(rules, list):
        return ()
    loaded: list[PhraseRule] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        code = _text(rule.get("code"))
        if not code or (allowed_codes is not None and code not in allowed_codes):
            continue
        severity = _text(rule.get("severity"), "low") or "low"
        message = _text(rule.get("message"), "Review warning.") or "Review warning."
        languages = _strings(rule.get("languages"))
        for phrase in _strings(rule.get("phrases")):
            loaded.append(
                PhraseRule(
                    code=code,
                    severity=severity,
                    phrase=phrase,
                    message=message,
                    languages=languages,
                    rule_pack=file_name,
                    section=section,
                )
            )
    return tuple(loaded)


def normalize_phrase_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def phrase_match_span(value: str, phrase: str) -> tuple[int, int] | None:
    normalized_value = normalize_phrase_text(value)
    normalized_phrase = normalize_phrase_text(phrase.strip())
    if not normalized_phrase:
        return None
    start = normalized_value.find(normalized_phrase)
    if start < 0:
        return None
    return start, start + len(phrase)


def find_phrase_rule_matches(value: str, rules: Iterable[PhraseRule]) -> list[tuple[PhraseRule, int, int]]:
    matches: list[tuple[PhraseRule, int, int]] = []
    for rule in rules:
        span = phrase_match_span(value, rule.phrase)
        if span is not None:
            matches.append((rule, span[0], span[1]))
    return matches
