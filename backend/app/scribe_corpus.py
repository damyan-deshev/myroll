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
    Campaign,
    CampaignMemoryEntry,
    Session as CampaignSession,
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
CONTEXT_BUNDLE_VERSION = "llm5b_corpus_context_v1"


CONTEXT_ROLE_CAPS: dict[str, dict[str, int]] = {
    "session.build_recap": {
        "played_evidence": 80,
        "gm_note": 12,
        "canon_claim": 12,
        "reviewed_summary": 4,
        "planning_intent": 12,
    },
    "scene.branch_directions": {
        "scope_context": 3,
        "canon_claim": 8,
        "reviewed_summary": 3,
        "played_evidence": 8,
        "gm_note": 5,
        "planning_intent": 8,
    },
    "session.player_safe_recap": {
        "shown_public_artifact": 8,
        "public_artifact": 8,
        "canon_claim": 10,
        "reviewed_summary": 4,
        "entity_shell": 12,
    },
}


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
                    "source": event.source,
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
        status = "active" if _marker_is_active(marker, now) else ("expired" if marker.status == "active" else marker.status)
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


def ensure_campaign_corpus_cards_current(db: Session, campaign_id: str) -> dict[str, object]:
    drafts = compile_campaign_cards(db, campaign_id)
    expected = {
        _card_id(campaign_id, draft): _source_hash(_card_hash_input(draft))
        for draft in drafts
    }
    existing = {
        card.id: card.source_hash
        for card in db.scalars(select(ScribeCorpusCard).where(ScribeCorpusCard.campaign_id == campaign_id))
    }
    fts_count = (
        db.execute(
            text("SELECT count(*) FROM scribe_corpus_cards_fts WHERE campaign_id = :campaign_id"),
            {"campaign_id": campaign_id},
        ).scalar()
        or 0
    )
    if existing == expected and int(fts_count) == len(expected):
        return {"rebuilt": False, "cardCount": len(expected)}
    count = rebuild_campaign_corpus(db, campaign_id)
    return {"rebuilt": True, "cardCount": count}


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


def _scope_ref(kind: str, source_id: str, revision: str, title: str, body: str) -> dict[str, object]:
    return {
        "kind": kind,
        "sourceClass": kind,
        "id": source_id,
        "revision": revision,
        "lane": "scope",
        "visibility": "gm_private",
        "title": title,
        "body": body,
        "quote": body[:MAX_EXCERPT_CHARS],
        "isSyntheticScopeRef": True,
        "claimRole": "scope_context",
        "sourceStatus": "scope_context",
        "admissibility": "included",
    }


def _scope_refs(
    db: Session,
    *,
    campaign_id: str,
    scope_kind: str,
    session_id: str | None,
    scene_id: str | None,
) -> list[dict[str, object]]:
    refs: list[dict[str, object]] = []
    campaign = db.get(Campaign, campaign_id)
    if campaign is not None:
        refs.append(_scope_ref("campaign", campaign.id, campaign.updated_at, "Campaign", campaign.description or campaign.name))
    if session_id is not None:
        session = db.get(CampaignSession, session_id)
        if session is not None and session.campaign_id == campaign_id:
            refs.append(_scope_ref("session", session.id, session.updated_at, "Session", session.title))
    if scope_kind == "scene" and scene_id is not None:
        scene = db.get(Scene, scene_id)
        if scene is not None and scene.campaign_id == campaign_id:
            refs.append(_scope_ref("scene", scene.id, scene.updated_at, "Scene", scene.title))
    return refs


def _card_body(card: ScribeCorpusCard) -> str:
    if card.claim_role in {"entity_shell", "debug_metadata"}:
        return card.excerpt
    text_value = card.searchable_text or card.excerpt
    title_prefix = f"{card.title}\n"
    if text_value.startswith(title_prefix):
        return text_value[len(title_prefix) :]
    return text_value


def _card_source_class(card: ScribeCorpusCard) -> str:
    if card.source_kind == "campaign_memory_entry":
        return "memory_entry"
    if card.source_kind == "session_transcript_event":
        return "transcript_event"
    return card.source_kind


def _json_load(value: str | None, default: object) -> object:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _card_to_source_ref(card: ScribeCorpusCard) -> dict[str, object]:
    body = _card_body(card)
    provenance = _json_load(card.provenance_json, {})
    ref: dict[str, object] = {
        "kind": card.source_kind,
        "sourceClass": _card_source_class(card),
        "id": card.source_id,
        "revision": card.source_revision,
        "lane": card.lane,
        "visibility": card.visibility,
        "title": card.title,
        "body": body,
        "quote": body[:MAX_EXCERPT_CHARS],
        "cardId": card.id,
        "sourceHash": card.source_hash,
        "cardVariant": card.card_variant,
        "claimRole": card.claim_role,
        "sourceStatus": card.source_status,
        "admissibility": "included",
        "sessionId": card.session_id,
        "sceneId": card.scene_id,
        "happenedAt": card.happened_at,
    }
    if isinstance(provenance, dict):
        for key, value in provenance.items():
            if value is not None and key not in ref:
                ref[key] = value
        if "orderIndex" in provenance:
            ref["orderIndex"] = provenance["orderIndex"]
        if "correctsEventId" in provenance:
            ref["correctsEventId"] = provenance["correctsEventId"]
        if card.source_kind == "planning_marker":
            ref["scopeKind"] = "scene" if card.scene_id else ("session" if card.session_id else "campaign")
            ref["relatedPlanningMarkerId"] = card.source_id
    if card.happened_at is not None:
        ref["capturedAt"] = card.happened_at
    return ref


def _marker_card_scope_compatible(card: ScribeCorpusCard, *, scope_kind: str, session_id: str | None, scene_id: str | None) -> bool:
    marker_scope = "scene" if card.scene_id else ("session" if card.session_id else "campaign")
    if marker_scope == "campaign":
        return True
    if scope_kind in {"session", "scene"} and marker_scope == "session" and card.session_id == session_id:
        return True
    if scope_kind == "session" and marker_scope == "scene" and card.session_id == session_id:
        return True
    if scope_kind == "scene" and marker_scope == "scene" and card.scene_id == scene_id:
        return True
    return False


def _session_recap_cards(cards: list[ScribeCorpusCard], session_id: str) -> list[ScribeCorpusCard]:
    return [
        card
        for card in cards
        if card.source_kind == "session_recap"
        and card.lane == "reviewed"
        and (card.session_id is None or card.session_id != session_id)
    ]


def _eligible_context_cards(
    cards: list[ScribeCorpusCard],
    *,
    task_kind: str,
    scope_kind: str,
    session_id: str | None,
    scene_id: str | None,
    visibility_mode: str,
    include_unshown_public_snippets: bool,
) -> list[ScribeCorpusCard]:
    eligible: list[ScribeCorpusCard] = []
    if task_kind == "session.build_recap":
        for card in cards:
            if card.source_kind == "session_transcript_event" and card.session_id == session_id:
                eligible.append(card)
            elif card.source_kind == "note" and card.session_id == session_id and card.source_status == "scoped_recall_eligible":
                eligible.append(card)
            elif card.source_kind == "campaign_memory_entry" and card.lane == "canon":
                eligible.append(card)
            elif card in _session_recap_cards(cards, str(session_id)):
                eligible.append(card)
            elif card.source_kind == "planning_marker" and card.source_status == "active" and _marker_card_scope_compatible(card, scope_kind="session", session_id=session_id, scene_id=None):
                eligible.append(card)
        return eligible
    if task_kind == "scene.branch_directions":
        for card in cards:
            if card.source_kind == "campaign_memory_entry" and card.lane == "canon":
                eligible.append(card)
            elif card.source_kind == "session_recap" and card.lane == "reviewed" and (scope_kind == "campaign" or card.session_id == session_id):
                eligible.append(card)
            elif card.source_kind == "note" and card.source_status == "scoped_recall_eligible" and scope_kind in {"session", "scene"} and card.session_id == session_id and (scope_kind != "scene" or card.scene_id == scene_id):
                eligible.append(card)
            elif card.source_kind == "session_transcript_event" and scope_kind in {"session", "scene"} and card.session_id == session_id and (scope_kind != "scene" or card.scene_id == scene_id):
                eligible.append(card)
            elif card.source_kind == "planning_marker" and card.source_status == "active" and _marker_card_scope_compatible(card, scope_kind=scope_kind, session_id=session_id, scene_id=scene_id):
                eligible.append(card)
        return eligible
    if task_kind == "session.player_safe_recap":
        for card in cards:
            if card.visibility not in {"public_safe", "player_display"}:
                continue
            if card.source_kind == "public_snippet":
                if include_unshown_public_snippets or card.visibility == "player_display":
                    eligible.append(card)
            elif card.source_kind == "session_recap" and card.session_id == session_id:
                eligible.append(card)
            elif card.source_kind == "campaign_memory_entry" and (card.session_id in {None, session_id}):
                eligible.append(card)
            elif card.source_kind == "entity" and card.claim_role == "entity_shell":
                eligible.append(card)
        return eligible
    return []


def _context_sort_key(task_kind: str, ref: dict[str, object]) -> tuple[object, ...]:
    role = str(ref.get("claimRole") or "")
    lane = str(ref.get("lane") or "")
    kind = str(ref.get("kind") or "")
    revision = str(ref.get("revision") or "")
    order_index = int(ref.get("orderIndex", 100000))
    if task_kind == "session.build_recap":
        role_order = {
            "source_evidence": 0 if lane == "played_evidence" else 1,
            "canon_claim": 2,
            "reviewed_summary": 3,
            "planning_intent": 4,
        }.get(role, 9)
        if lane == "gm_note":
            role_order = 1
        return (role_order, order_index, revision, kind, str(ref.get("id")))
    if task_kind == "scene.branch_directions":
        role_order = {
            "scope_context": 0,
            "canon_claim": 1,
            "reviewed_summary": 2,
            "source_evidence": 3,
            "planning_intent": 4,
        }.get(role, 9)
        if lane == "gm_note":
            role_order = 3
        return (role_order, -order_index, revision, kind, str(ref.get("id")))
    role_order = {
        "public_artifact": 0 if ref.get("visibility") == "player_display" else 1,
        "canon_claim": 2,
        "reviewed_summary": 3,
        "entity_shell": 4,
    }.get(role, 9)
    return (role_order, revision, kind, str(ref.get("id")))


def _ref_cap_bucket(ref: dict[str, object]) -> str:
    if ref.get("claimRole") == "public_artifact" and ref.get("visibility") == "player_display":
        return "shown_public_artifact"
    if ref.get("lane") == "gm_note":
        return "gm_note"
    if ref.get("lane") == "played_evidence":
        return "played_evidence"
    return str(ref.get("claimRole") or ref.get("lane") or "unknown")


def _apply_context_caps(task_kind: str, refs: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, dict[str, int]]]:
    caps = CONTEXT_ROLE_CAPS.get(task_kind, {})
    seen: dict[str, int] = {}
    total: dict[str, int] = {}
    included: list[dict[str, object]] = []
    for ref in refs:
        bucket = _ref_cap_bucket(ref)
        total[bucket] = total.get(bucket, 0) + 1
        cap = caps.get(bucket, caps.get(str(ref.get("claimRole")), MAX_LIMIT))
        if seen.get(bucket, 0) >= cap:
            continue
        seen[bucket] = seen.get(bucket, 0) + 1
        included.append(ref)
    truncation = {
        bucket: {"included": seen.get(bucket, 0), "total": count, "truncated": seen.get(bucket, 0) < count}
        for bucket, count in total.items()
        if seen.get(bucket, 0) < count
    }
    return included, truncation


def _source_key_for_ref(ref: dict[str, object]) -> str:
    return f"{ref.get('kind')}:{ref.get('id')}"


def _filter_context_exclusions(refs: list[dict[str, object]], excluded_source_refs: set[str]) -> list[dict[str, object]]:
    if not excluded_source_refs:
        return refs
    return [
        ref for ref in refs
        if str(ref.get("cardId") or "") not in excluded_source_refs and _source_key_for_ref(ref) not in excluded_source_refs
    ]


def _excluded_counts(cards: list[ScribeCorpusCard], included_refs: list[dict[str, object]], *, public_safe: bool) -> dict[str, int]:
    included_card_ids = {str(ref.get("cardId")) for ref in included_refs if ref.get("cardId")}
    counts: dict[str, int] = {}
    for card in cards:
        if card.id in included_card_ids:
            continue
        key = card.visibility if public_safe else card.lane
        counts[key] = counts.get(key, 0) + 1
    return counts


def _evidence_coverage_for_refs(refs: list[dict[str, object]], *, truncated: bool) -> str:
    if not refs:
        return "none"
    dynamic_refs = [ref for ref in refs if not ref.get("isSyntheticScopeRef")]
    if not dynamic_refs:
        return "weak"
    if any(ref.get("claimRole") in {"canon_claim", "reviewed_summary"} for ref in dynamic_refs) and not truncated:
        return "sufficient"
    return "partial" if len(dynamic_refs) > 1 else "weak"


def build_scribe_context_bundle(
    db: Session,
    *,
    campaign_id: str,
    task_kind: str,
    scope_kind: str,
    session_id: str | None,
    scene_id: str | None,
    visibility_mode: str,
    gm_instruction: str,
    include_unshown_public_snippets: bool = False,
    excluded_source_refs: set[str] | None = None,
) -> dict[str, object]:
    ensure_result = ensure_campaign_corpus_cards_current(db, campaign_id)
    cards = list(db.scalars(select(ScribeCorpusCard).where(ScribeCorpusCard.campaign_id == campaign_id)))
    dynamic_cards = _eligible_context_cards(
        cards,
        task_kind=task_kind,
        scope_kind=scope_kind,
        session_id=session_id,
        scene_id=scene_id,
        visibility_mode=visibility_mode,
        include_unshown_public_snippets=include_unshown_public_snippets,
    )
    dynamic_refs = [_card_to_source_ref(card) for card in dynamic_cards]
    if visibility_mode == "public_safe":
        scope_refs: list[dict[str, object]] = []
    else:
        scope_refs = _scope_refs(db, campaign_id=campaign_id, scope_kind=scope_kind, session_id=session_id, scene_id=scene_id)
    sorted_refs = sorted([*scope_refs, *dynamic_refs], key=lambda ref: _context_sort_key(task_kind, ref))
    sorted_refs = _filter_context_exclusions(sorted_refs, excluded_source_refs or set())
    capped_refs, truncation = _apply_context_caps(task_kind, sorted_refs)
    public_safe = visibility_mode == "public_safe"
    excluded_by_policy = _excluded_counts(cards, capped_refs, public_safe=public_safe)
    dynamic_count = sum(1 for ref in capped_refs if not ref.get("isSyntheticScopeRef"))
    evidence_coverage = _evidence_coverage_for_refs(capped_refs, truncated=bool(truncation))
    warnings: list[dict[str, object]] = []
    if task_kind == "session.player_safe_recap" and include_unshown_public_snippets:
        if any(ref.get("kind") == "public_snippet" and ref.get("visibility") == "public_safe" for ref in capped_refs):
            warnings.append(
                {
                    "code": "unshown_public_snippet_included",
                    "severity": "medium",
                    "message": "Unshown public snippets are manual public artifacts, not Scribe-verified safe text.",
                }
            )
    for bucket, data in truncation.items():
        code = "public_safe_source_limit" if task_kind == "session.player_safe_recap" else "context_sources_truncated"
        source_class = {
            "canon_claim": "memory_entry",
            "reviewed_summary": "session_recap",
            "shown_public_artifact": "public_snippet",
            "public_artifact": "public_snippet",
            "entity_shell": "entity",
        }.get(bucket, bucket)
        warnings.append(
            {
                "code": code,
                "severity": "low",
                "sourceClass": source_class,
                "bucket": bucket,
                "included": data["included"],
                "totalEligible": data["total"],
                "message": f"{data['included']} of {data['total']} eligible {bucket} sources included.",
            }
        )
    assembly = [
        {
            "cardId": ref.get("cardId"),
            "sourceKind": ref.get("kind"),
            "sourceId": ref.get("id"),
            "lane": ref.get("lane"),
            "claimRole": ref.get("claimRole"),
            "sourceStatus": ref.get("sourceStatus"),
            "title": ref.get("title"),
            "admissibility": ref.get("admissibility", "included"),
            "isSyntheticScopeRef": bool(ref.get("isSyntheticScopeRef")),
        }
        for ref in capped_refs
    ]
    trace = {
        "traceVisibility": "safe" if public_safe else "gm_private",
        "nodes": [
            {
                "cardId": ref.get("cardId"),
                "sourceKind": ref.get("kind"),
                "sourceId": None if public_safe else ref.get("id"),
                "title": ref.get("title") if not public_safe or ref.get("visibility") in {"public_safe", "player_display"} else None,
                "lane": ref.get("lane"),
                "visibility": ref.get("visibility"),
                "claimRole": ref.get("claimRole"),
                "admissibility": "included",
            }
            for ref in capped_refs
            if ref.get("cardId")
        ][:MAX_TRACE_NODES],
        "edges": [],
        "excludedByPolicy": excluded_by_policy,
    }
    metadata = {
        "version": CONTEXT_BUNDLE_VERSION,
        "taskKind": task_kind,
        "scopeKind": scope_kind,
        "visibilityMode": visibility_mode,
        "summary": {
            "sourceCount": len(capped_refs),
            "dynamicSourceCount": dynamic_count,
            "truncated": bool(truncation),
            "truncation": truncation,
            "excludedByPolicy": excluded_by_policy,
            "corpusCardCount": ensure_result.get("cardCount"),
        },
        "evidenceCoverage": evidence_coverage,
        "assembly": assembly,
        "trace": trace,
        "policy": _policy("public_safe" if public_safe else "debug_history"),
    }
    return {
        "source_refs": capped_refs,
        "warnings": warnings,
        "corpusBundle": metadata,
        "evidenceCoverage": evidence_coverage,
        "assembly": assembly,
    }


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
