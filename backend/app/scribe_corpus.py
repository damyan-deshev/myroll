from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import bindparam, delete, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.app.db.models import (
    CampaignMemoryEntry,
    Entity,
    EntityAlias,
    PartyTrackerConfig,
    PartyTrackerMember,
    PlanningMarker,
    ProposalOption,
    ProposalSet,
    PublicSnippet,
    Scene,
    ScribeCorpusCard,
    SessionRecap,
    SessionTranscriptEvent,
    Note,
)
from backend.app.time import utc_now_z


RECALL_MODES = {"canon", "canon_plus_reviewed", "played_evidence", "planning", "public_safe", "debug_history"}
TRACE_VISIBILITIES = {"safe", "gm_private", "none"}
DEFAULT_LIMIT = 8
MAX_LIMIT = 25
MAX_QUERY_CHARS = 500
MAX_ALIAS_EXPANSIONS = 12
MAX_FTS_CANDIDATES = 80
MAX_TRACE_NODES = 50
MAX_TRACE_EDGES = 100
MAX_EXCERPT_CHARS = 500


@dataclass(frozen=True)
class CorpusCardDraft:
    source_kind: str
    source_id: str
    source_revision: str
    card_variant: str
    lane: str
    visibility: str
    review_status: str
    source_status: str
    claim_role: str
    title: str
    excerpt: str
    searchable_text: str
    session_id: str | None = None
    scene_id: str | None = None
    happened_at: str | None = None
    entity_refs: list[str] | None = None
    alias_refs: list[str] | None = None
    provenance: dict[str, object] | None = None


class CorpusUnavailableError(RuntimeError):
    pass


class RecallPolicyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def normalize_recall_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _source_hash(value: dict[str, object]) -> str:
    return hashlib.sha256(_json_dump(value).encode("utf-8")).hexdigest()


def _card_id(campaign_id: str, draft: CorpusCardDraft) -> str:
    key = (
        f"myroll:scribe-corpus-card:{campaign_id}:{draft.source_kind}:"
        f"{draft.source_id}:{draft.source_revision}:{draft.card_variant}"
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _clip(value: str, limit: int = MAX_EXCERPT_CHARS) -> str:
    clean = value.strip()
    return clean[:limit] + ("..." if len(clean) > limit else "")


def _card_hash_input(draft: CorpusCardDraft) -> dict[str, object]:
    return {
        "sourceKind": draft.source_kind,
        "sourceId": draft.source_id,
        "sourceRevision": draft.source_revision,
        "cardVariant": draft.card_variant,
        "lane": draft.lane,
        "visibility": draft.visibility,
        "reviewStatus": draft.review_status,
        "sourceStatus": draft.source_status,
        "claimRole": draft.claim_role,
        "title": draft.title,
        "excerpt": draft.excerpt,
        "searchableText": draft.searchable_text,
        "sessionId": draft.session_id,
        "sceneId": draft.scene_id,
        "happenedAt": draft.happened_at,
        "entityRefs": sorted(draft.entity_refs or []),
        "aliasRefs": sorted(draft.alias_refs or []),
        "provenance": draft.provenance or {},
    }


def _marker_is_active(marker: PlanningMarker, now: str) -> bool:
    if marker.status != "active":
        return False
    return marker.expires_at is None or marker.expires_at > now


def _party_entity_ids(db: Session, campaign_id: str) -> set[str]:
    config = db.scalar(select(PartyTrackerConfig).where(PartyTrackerConfig.campaign_id == campaign_id))
    if config is None:
        return set()
    return set(
        db.scalars(
            select(PartyTrackerMember.entity_id).where(
                PartyTrackerMember.campaign_id == campaign_id,
                PartyTrackerMember.config_id == config.id,
            )
        )
    )


def _public_entity_status(entity: Entity, party_entity_ids: set[str]) -> str:
    if entity.id in party_entity_ids:
        return "party_member"
    if entity.visibility == "public_known":
        return "public_known"
    return "private_prep"


def _transcript_projection(events: list[SessionTranscriptEvent]) -> list[SessionTranscriptEvent]:
    corrections = {event.corrects_event_id: event for event in events if event.corrects_event_id}
    projected: list[SessionTranscriptEvent] = []
    for event in events:
        if event.corrects_event_id:
            continue
        projected.append(corrections.get(event.id, event))
    return projected


def compile_campaign_cards(db: Session, campaign_id: str) -> list[CorpusCardDraft]:
    now = utc_now_z()
    cards: list[CorpusCardDraft] = []

    for entry in db.scalars(select(CampaignMemoryEntry).where(CampaignMemoryEntry.campaign_id == campaign_id)):
        visibility = "public_safe" if entry.public_safe else "gm_private"
        cards.append(
            CorpusCardDraft(
                source_kind="campaign_memory_entry",
                source_id=entry.id,
                source_revision=entry.updated_at,
                card_variant="default",
                lane="canon",
                visibility=visibility,
                review_status="accepted",
                source_status="accepted",
                claim_role="canon_claim",
                title=entry.title,
                excerpt=_clip(entry.body),
                searchable_text=f"{entry.title}\n{entry.body}",
                session_id=entry.session_id,
                provenance={
                    "evidenceRefKind": "campaign_memory_entry",
                    "evidenceRefId": entry.id,
                    "sourceCandidateId": entry.source_candidate_id,
                    "sourcePlanningMarkerId": entry.source_planning_marker_id,
                    "sourceProposalOptionId": entry.source_proposal_option_id,
                },
            )
        )

    for recap in db.scalars(select(SessionRecap).where(SessionRecap.campaign_id == campaign_id)):
        visibility = "public_safe" if recap.public_safe else "gm_private"
        cards.append(
            CorpusCardDraft(
                source_kind="session_recap",
                source_id=recap.id,
                source_revision=recap.updated_at,
                card_variant="default",
                lane="reviewed",
                visibility=visibility,
                review_status="reviewed",
                source_status="reviewed",
                claim_role="reviewed_summary",
                title=recap.title,
                excerpt=_clip(recap.body_markdown),
                searchable_text=f"{recap.title}\n{recap.body_markdown}",
                session_id=recap.session_id,
                provenance={"evidenceRefKind": "session_recap", "evidenceRefId": recap.id},
            )
        )

    transcript_events = list(
        db.scalars(
            select(SessionTranscriptEvent)
            .where(SessionTranscriptEvent.campaign_id == campaign_id)
            .order_by(SessionTranscriptEvent.session_id, SessionTranscriptEvent.order_index, SessionTranscriptEvent.created_at)
        )
    )
    for event in _transcript_projection(transcript_events):
        cards.append(
            CorpusCardDraft(
                source_kind="session_transcript_event",
                source_id=event.id,
                source_revision=event.updated_at,
                card_variant="default",
                lane="played_evidence",
                visibility="gm_private",
                review_status="raw",
                source_status="correction" if event.event_type == "correction" else "captured",
                claim_role="source_evidence",
                title=f"Live capture #{event.order_index + 1}",
                excerpt=_clip(event.body),
                searchable_text=event.body,
                session_id=event.session_id,
                scene_id=event.scene_id,
                happened_at=event.created_at,
                provenance={
                    "evidenceRefKind": "session_transcript_event",
                    "evidenceRefId": event.id,
                    "correctsEventId": event.corrects_event_id,
                    "orderIndex": event.order_index,
                },
            )
        )

    for note in db.scalars(select(Note).where(Note.campaign_id == campaign_id)):
        cards.append(
            CorpusCardDraft(
                source_kind="note",
                source_id=note.id,
                source_revision=note.updated_at,
                card_variant="default",
                lane="gm_note",
                visibility="gm_private",
                review_status="raw",
                source_status=note.recall_status,
                claim_role="source_evidence",
                title=note.title,
                excerpt=_clip(note.private_body),
                searchable_text=f"{note.title}\n{note.private_body}",
                session_id=note.session_id,
                scene_id=note.scene_id,
                provenance={"evidenceRefKind": "note", "evidenceRefId": note.id, "recallStatus": note.recall_status},
            )
        )

    for marker in db.scalars(select(PlanningMarker).where(PlanningMarker.campaign_id == campaign_id)):
        status = "active" if _marker_is_active(marker, now) else marker.status
        cards.append(
            CorpusCardDraft(
                source_kind="planning_marker",
                source_id=marker.id,
                source_revision=marker.updated_at,
                card_variant="default",
                lane="planning",
                visibility="gm_private",
                review_status="planning_only",
                source_status=status,
                claim_role="planning_intent",
                title=marker.title,
                excerpt=_clip(marker.marker_text),
                searchable_text=f"{marker.title}\n{marker.marker_text}",
                session_id=marker.session_id,
                scene_id=marker.scene_id,
                provenance={
                    "evidenceRefKind": "planning_marker",
                    "evidenceRefId": marker.id,
                    "sourceProposalOptionId": marker.source_proposal_option_id,
                    "canonMemoryEntryId": marker.canon_memory_entry_id,
                },
            )
        )

    for snippet in db.scalars(select(PublicSnippet).where(PublicSnippet.campaign_id == campaign_id)):
        shown = snippet.last_published_at is not None
        cards.append(
            CorpusCardDraft(
                source_kind="public_snippet",
                source_id=snippet.id,
                source_revision=snippet.updated_at,
                card_variant="public_projection",
                lane="public",
                visibility="player_display" if shown else "public_safe",
                review_status="public_artifact",
                source_status="shown_on_player_display" if shown else "not_shown",
                claim_role="public_artifact",
                title=snippet.title or "Untitled public snippet",
                excerpt=_clip(snippet.body),
                searchable_text=f"{snippet.title or ''}\n{snippet.body}",
                provenance={
                    "evidenceRefKind": "public_snippet",
                    "evidenceRefId": snippet.id,
                    "shownOnPlayerDisplay": shown,
                    "creationSource": snippet.creation_source,
                },
            )
        )

    party_entity_ids = _party_entity_ids(db, campaign_id)
    for entity in db.scalars(select(Entity).where(Entity.campaign_id == campaign_id)):
        source_status = _public_entity_status(entity, party_entity_ids)
        if source_status == "private_prep":
            visibility = "gm_private"
            lane = "debug_history"
            review_status = "debug_only"
        else:
            visibility = "public_safe"
            lane = "canon"
            review_status = "accepted"
        display_name = entity.display_name or entity.name
        cards.append(
            CorpusCardDraft(
                source_kind="entity",
                source_id=entity.id,
                source_revision=entity.updated_at,
                card_variant="entity_shell",
                lane=lane,
                visibility=visibility,
                review_status=review_status,
                source_status=source_status,
                claim_role="entity_shell",
                title=display_name,
                excerpt=f"{display_name} ({entity.kind})",
                searchable_text=f"{display_name}\n{entity.name}\n{entity.kind}",
                entity_refs=[entity.id],
                provenance={"evidenceRefKind": "entity", "evidenceRefId": entity.id, "entityShell": True},
            )
        )

    for option in db.scalars(
        select(ProposalOption)
        .join(ProposalSet, ProposalSet.id == ProposalOption.proposal_set_id)
        .where(ProposalSet.campaign_id == campaign_id)
    ):
        cards.append(
            CorpusCardDraft(
                source_kind="proposal_option",
                source_id=option.id,
                source_revision=option.updated_at,
                card_variant="debug_metadata",
                lane="debug_history",
                visibility="gm_private",
                review_status="debug_only",
                source_status=option.status,
                claim_role="debug_metadata",
                title=option.title,
                excerpt=f"Proposal option metadata only. Status: {option.status}.",
                searchable_text=f"{option.title}\n{option.status}\n{option.stable_option_key}",
                provenance={"evidenceRefKind": "proposal_option", "evidenceRefId": option.id, "metadataOnly": True},
            )
        )

    return cards


def rebuild_campaign_corpus(db: Session, campaign_id: str) -> int:
    now = utc_now_z()
    drafts = compile_campaign_cards(db, campaign_id)
    db.execute(text("DELETE FROM scribe_corpus_cards_fts WHERE campaign_id = :campaign_id"), {"campaign_id": campaign_id})
    db.execute(delete(ScribeCorpusCard).where(ScribeCorpusCard.campaign_id == campaign_id))
    for draft in drafts:
        card_id = _card_id(campaign_id, draft)
        source_hash = _source_hash(_card_hash_input(draft))
        card = ScribeCorpusCard(
            id=card_id,
            campaign_id=campaign_id,
            source_kind=draft.source_kind,
            source_id=draft.source_id,
            source_revision=draft.source_revision,
            card_variant=draft.card_variant,
            source_hash=source_hash,
            lane=draft.lane,
            visibility=draft.visibility,
            review_status=draft.review_status,
            source_status=draft.source_status,
            claim_role=draft.claim_role,
            session_id=draft.session_id,
            scene_id=draft.scene_id,
            happened_at=draft.happened_at,
            title=draft.title[:240],
            excerpt=draft.excerpt[:MAX_EXCERPT_CHARS],
            searchable_text=draft.searchable_text,
            entity_refs_json=_json_dump(draft.entity_refs or []),
            alias_refs_json=_json_dump(draft.alias_refs or []),
            provenance_json=_json_dump(draft.provenance or {}),
            created_at=now,
            updated_at=now,
        )
        db.add(card)
        db.flush()
        db.execute(
            text(
                """
                INSERT INTO scribe_corpus_cards_fts(card_id, campaign_id, title, excerpt, searchable_text)
                VALUES (:card_id, :campaign_id, :title, :excerpt, :searchable_text)
                """
            ),
            {
                "card_id": card.id,
                "campaign_id": campaign_id,
                "title": card.title,
                "excerpt": card.excerpt,
                "searchable_text": card.searchable_text,
            },
        )
    db.flush()
    return len(drafts)


def _query_tokens(value: str) -> list[str]:
    normalized = normalize_recall_text(value)
    return [token for token in re.findall(r"[\w]+", normalized, flags=re.UNICODE) if len(token) >= 2]


def _fts_term(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _fts_query(tokens: list[str], joiner: str) -> str:
    return f" {joiner} ".join(_fts_term(token) for token in tokens)


def _load_alias_expansions(db: Session, campaign_id: str, query: str) -> tuple[list[str], list[dict[str, object]]]:
    normalized_query = normalize_recall_text(query)
    expansions: list[str] = []
    matches: list[dict[str, object]] = []
    aliases = list(db.scalars(select(EntityAlias).where(EntityAlias.campaign_id == campaign_id)))
    for alias in aliases:
        normalized_alias = normalize_recall_text(alias.normalized_alias or alias.alias_text)
        if not normalized_alias:
            continue
        if normalized_alias in normalized_query or normalized_query in normalized_alias:
            matches.append(
                {
                    "aliasId": alias.id,
                    "aliasText": alias.alias_text,
                    "entityId": alias.entity_id,
                    "matchStrategy": "exact_alias",
                }
            )
            expansions.extend(_query_tokens(alias.alias_text))
            if alias.entity_id:
                entity = db.get(Entity, alias.entity_id)
                if entity is not None:
                    expansions.extend(_query_tokens(entity.name))
                    if entity.display_name:
                        expansions.extend(_query_tokens(entity.display_name))
        if len(expansions) >= MAX_ALIAS_EXPANSIONS:
            break
    deduped: list[str] = []
    for token in expansions:
        if token not in deduped:
            deduped.append(token)
    return deduped[:MAX_ALIAS_EXPANSIONS], matches[:MAX_ALIAS_EXPANSIONS]


def _eligible_cards(cards: list[ScribeCorpusCard], mode: str) -> list[ScribeCorpusCard]:
    if mode == "debug_history":
        return cards
    eligible: list[ScribeCorpusCard] = []
    for card in cards:
        if mode == "canon":
            if card.lane == "canon":
                eligible.append(card)
        elif mode == "canon_plus_reviewed":
            if card.lane in {"canon", "reviewed"}:
                eligible.append(card)
        elif mode == "played_evidence":
            if card.lane in {"canon", "reviewed", "played_evidence"}:
                eligible.append(card)
            elif card.lane == "gm_note" and card.source_status == "scoped_recall_eligible":
                eligible.append(card)
        elif mode == "planning":
            if card.lane in {"canon", "reviewed"}:
                eligible.append(card)
            elif card.lane == "planning" and card.source_status == "active":
                eligible.append(card)
        elif mode == "public_safe":
            if card.visibility in {"public_safe", "player_display"} and card.lane in {"canon", "reviewed", "public"}:
                eligible.append(card)
    return eligible


def _source_authority(card: ScribeCorpusCard, mode: str) -> int:
    if card.claim_role == "canon_claim":
        return 100
    if card.claim_role == "entity_shell":
        return 70 if mode in {"canon", "canon_plus_reviewed"} else 55
    if card.claim_role == "reviewed_summary":
        return 65
    if card.claim_role == "source_evidence":
        return 45
    if card.claim_role == "public_artifact":
        return 50
    if card.claim_role == "planning_intent":
        return 30
    return 5


def _card_to_hit(card: ScribeCorpusCard, *, score: float, match_strategy: str, matched_terms: list[str]) -> dict[str, object]:
    return {
        "card_id": card.id,
        "source_kind": card.source_kind,
        "source_id": card.source_id,
        "source_revision": card.source_revision,
        "source_hash": card.source_hash,
        "card_variant": card.card_variant,
        "title": card.title,
        "excerpt": card.excerpt[:MAX_EXCERPT_CHARS],
        "lane": card.lane,
        "visibility": card.visibility,
        "review_status": card.review_status,
        "source_status": card.source_status,
        "claim_role": card.claim_role,
        "score": round(score, 4),
        "match": {"strategy": match_strategy, "matched_terms": matched_terms},
        "admissibility": "included",
    }


def _fts_hits(
    db: Session,
    *,
    campaign_id: str,
    eligible_ids: list[str],
    fts_query: str,
    max_candidates: int,
) -> dict[str, float]:
    if not eligible_ids or not fts_query:
        return {}
    statement = text(
        """
        SELECT c.id AS card_id, bm25(scribe_corpus_cards_fts) AS bm25_score
        FROM scribe_corpus_cards_fts
        JOIN scribe_corpus_cards AS c ON c.id = scribe_corpus_cards_fts.card_id
        WHERE scribe_corpus_cards_fts MATCH :fts_query
          AND c.campaign_id = :campaign_id
          AND c.id IN :eligible_ids
        ORDER BY bm25_score
        LIMIT :max_candidates
        """
    ).bindparams(bindparam("eligible_ids", expanding=True))
    try:
        rows = db.execute(
            statement,
            {
                "fts_query": fts_query,
                "campaign_id": campaign_id,
                "eligible_ids": eligible_ids,
                "max_candidates": max_candidates,
            },
        ).mappings()
    except OperationalError as exc:
        raise CorpusUnavailableError("SQLite FTS5 recall index is unavailable") from exc
    return {str(row["card_id"]): float(row["bm25_score"] or 0.0) for row in rows}


def _coverage(mode: str, hits: list[dict[str, object]], *, truncated: bool) -> str:
    if not hits:
        return "none"
    if len(hits) == 1:
        role = str(hits[0].get("claim_role") or "")
        if role in {"entity_shell", "source_evidence", "planning_intent"}:
            return "weak"
    has_strong = any(str(hit.get("claim_role")) in {"canon_claim", "reviewed_summary"} for hit in hits)
    if has_strong and not truncated:
        return "sufficient"
    return "partial" if len(hits) > 1 else "weak"


def _trace_edges(nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    edges: list[dict[str, object]] = []
    for index, left in enumerate(nodes):
        for right in nodes[index + 1 :]:
            if len(edges) >= MAX_TRACE_EDGES:
                return edges
            reasons: list[str] = []
            if left.get("source_id") == right.get("source_id"):
                reasons.append("source_lineage")
            if left.get("lane") == right.get("lane"):
                reasons.append("same_lane")
            left_terms = set(str(term) for term in (left.get("match") or {}).get("matched_terms", []))
            right_terms = set(str(term) for term in (right.get("match") or {}).get("matched_terms", []))
            if left_terms & right_terms:
                reasons.append("query_term_overlap")
            for reason in reasons:
                if len(edges) >= MAX_TRACE_EDGES:
                    break
                edges.append(
                    {
                        "id": f"{left['card_id']}:{right['card_id']}:{reason}",
                        "fromNodeId": left["card_id"],
                        "toNodeId": right["card_id"],
                        "kind": reason,
                        "confidence": "deterministic",
                    }
                )
    return edges


def _policy(mode: str) -> dict[str, object]:
    if mode == "canon":
        return {
            "includedLanes": ["canon"],
            "excludedLanes": ["reviewed", "played_evidence", "gm_note", "planning", "public", "debug_history"],
            "description": "Accepted canon memory plus eligible entity shells only.",
        }
    if mode == "canon_plus_reviewed":
        return {"includedLanes": ["canon", "reviewed"], "excludedLanes": ["planning", "gm_note", "debug_history"]}
    if mode == "played_evidence":
        return {"includedLanes": ["canon", "reviewed", "played_evidence", "gm_note:scoped_recall_eligible"], "excludedLanes": ["planning", "debug_history"]}
    if mode == "planning":
        return {"includedLanes": ["canon", "reviewed", "planning:active"], "excludedLanes": ["debug_history"]}
    if mode == "public_safe":
        return {"includedVisibility": ["public_safe", "player_display"], "excludedVisibility": ["gm_private"]}
    return {"includedLanes": ["all"], "trace": "gm_private_debug_history"}


def recall_campaign_corpus(
    db: Session,
    *,
    campaign_id: str,
    query: str,
    mode: str = "canon",
    limit: int = DEFAULT_LIMIT,
    trace_visibility: str = "safe",
) -> dict[str, object]:
    if mode not in RECALL_MODES:
        raise RecallPolicyError("invalid_recall_mode", "Recall mode is invalid")
    if trace_visibility not in TRACE_VISIBILITIES:
        raise RecallPolicyError("invalid_trace_visibility", "Trace visibility is invalid")
    if mode == "debug_history" and trace_visibility != "gm_private":
        raise RecallPolicyError("debug_history_requires_gm_private_trace", "debug_history requires GM-private diagnostics")
    trimmed_query = query.strip()[:MAX_QUERY_CHARS]
    limit = min(max(int(limit or DEFAULT_LIMIT), 1), MAX_LIMIT)
    cards = list(db.scalars(select(ScribeCorpusCard).where(ScribeCorpusCard.campaign_id == campaign_id)))
    eligible_cards = _eligible_cards(cards, mode)
    excluded_counts: dict[str, int] = {}
    eligible_ids = {card.id for card in eligible_cards}
    for card in cards:
        if card.id not in eligible_ids:
            key = card.lane if mode != "public_safe" else card.visibility
            excluded_counts[key] = excluded_counts.get(key, 0) + 1

    original_tokens = _query_tokens(trimmed_query)
    alias_tokens, alias_matches = _load_alias_expansions(db, campaign_id, trimmed_query)
    expanded_terms = list(dict.fromkeys([*original_tokens, *alias_tokens]))[:MAX_ALIAS_EXPANSIONS + len(original_tokens)]
    if not original_tokens:
        return {
            "query": trimmed_query,
            "expanded_terms": expanded_terms,
            "hits": [],
            "policy": _policy(mode),
            "summary": {
                "returned": 0,
                "matched": 0,
                "totalEligibleHits": 0,
                "eligibleCards": len(eligible_cards),
                "truncated": False,
                "excludedByPolicy": excluded_counts,
            },
            "evidenceCoverage": "none",
            "trace": {"nodes": [], "edges": [], "groups": [], "aliasMatches": alias_matches} if trace_visibility != "none" else None,
            "assembly": [],
        }

    eligible_id_list = [card.id for card in eligible_cards]
    card_by_id = {card.id: card for card in eligible_cards}
    and_ids = _fts_hits(
        db,
        campaign_id=campaign_id,
        eligible_ids=eligible_id_list,
        fts_query=_fts_query(original_tokens, "AND"),
        max_candidates=MAX_FTS_CANDIDATES,
    )
    match_strategy = "fts_and"
    candidate_scores = and_ids
    if not candidate_scores:
        or_tokens = list(dict.fromkeys([*original_tokens, *alias_tokens]))
        candidate_scores = _fts_hits(
            db,
            campaign_id=campaign_id,
            eligible_ids=eligible_id_list,
            fts_query=_fts_query(or_tokens, "OR"),
            max_candidates=MAX_FTS_CANDIDATES,
        )
        match_strategy = "fts_or_fallback" if candidate_scores else "fts_and"

    hits: list[dict[str, object]] = []
    for card_id, bm25_score in candidate_scores.items():
        card = card_by_id.get(card_id)
        if card is None:
            continue
        text_for_match = normalize_recall_text(f"{card.title} {card.searchable_text}")
        matched_terms = [term for term in expanded_terms if term in text_for_match][:MAX_ALIAS_EXPANSIONS]
        alias_boost = 20 if any(match.get("entityId") and str(match.get("entityId")) in (card.entity_refs_json or "") for match in alias_matches) else 0
        score = _source_authority(card, mode) + alias_boost + max(0.0, -bm25_score)
        hits.append(_card_to_hit(card, score=score, match_strategy=match_strategy, matched_terms=matched_terms))
    hits.sort(key=lambda item: (-float(item["score"]), str(item["title"])))
    returned_hits = hits[:limit]
    truncated = len(hits) > len(returned_hits)
    coverage = _coverage(mode, returned_hits, truncated=truncated)
    nodes = returned_hits[:MAX_TRACE_NODES]
    trace = None
    if trace_visibility != "none":
        trace = {
            "nodes": nodes,
            "edges": _trace_edges(nodes),
            "groups": [{"key": key, "count": sum(1 for item in nodes if item.get("lane") == key)} for key in sorted({str(item.get("lane")) for item in nodes})],
            "aliasMatches": alias_matches,
            "excludedByPolicy": excluded_counts,
            "traceVisibility": trace_visibility,
        }
    return {
        "query": trimmed_query,
        "expanded_terms": expanded_terms,
        "hits": returned_hits,
        "policy": _policy(mode),
        "summary": {
            "returned": len(returned_hits),
            "matched": len(hits),
            "totalEligibleHits": len(hits),
            "eligibleCards": len(eligible_cards),
            "truncated": truncated,
            "excludedByPolicy": excluded_counts,
            "matchStrategy": match_strategy,
        },
        "evidenceCoverage": coverage,
        "trace": trace,
        "assembly": [
            {
                "cardId": hit["card_id"],
                "sourceKind": hit["source_kind"],
                "sourceId": hit["source_id"],
                "lane": hit["lane"],
                "claimRole": hit["claim_role"],
                "title": hit["title"],
                "excerpt": hit["excerpt"],
                "admissibility": "included",
            }
            for hit in returned_hits
        ],
    }
