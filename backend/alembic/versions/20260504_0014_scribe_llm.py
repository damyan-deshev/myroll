"""scribe llm spine

Revision ID: 20260504_0014
Revises: 20260502_0013
Create Date: 2026-05-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260504_0014"
down_revision = "20260502_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_order_counters",
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("next_order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.String(), nullable=False),
    )

    op.create_table(
        "session_transcript_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("corrects_event_id", sa.String(), sa.ForeignKey("session_transcript_events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False, server_default="live_dm_note"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="typed"),
        sa.Column("public_safe", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("event_type in ('live_dm_note', 'correction')", name="ck_session_transcript_events_event_type"),
        sa.CheckConstraint("order_index >= 0", name="ck_session_transcript_events_order_index"),
        sa.UniqueConstraint("session_id", "order_index", name="uq_session_transcript_events_session_order"),
    )
    op.create_index("ix_session_transcript_events_campaign_id", "session_transcript_events", ["campaign_id"])
    op.create_index("ix_session_transcript_events_session_id", "session_transcript_events", ["session_id"])
    op.create_index("ix_session_transcript_events_scene_id", "session_transcript_events", ["scene_id"])
    op.create_index("ix_session_transcript_events_corrects_event_id", "session_transcript_events", ["corrects_event_id"])

    op.create_table(
        "llm_provider_profiles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("vendor", sa.String(), nullable=False, server_default="custom"),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("key_source_type", sa.String(), nullable=False, server_default="none"),
        sa.Column("key_source_ref", sa.String(), nullable=True),
        sa.Column("conformance_level", sa.String(), nullable=False, server_default="unverified"),
        sa.Column("capabilities_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("last_probe_result_json", sa.Text(), nullable=True),
        sa.Column("probed_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("vendor in ('openai', 'ollama', 'lmstudio', 'kobold', 'openrouter', 'custom')", name="ck_llm_provider_profiles_vendor"),
        sa.CheckConstraint("key_source_type in ('none', 'env')", name="ck_llm_provider_profiles_key_source_type"),
        sa.CheckConstraint(
            "conformance_level in ('unverified', 'level_0_text_only', 'level_1_json_best_effort', 'level_2_json_validated', 'level_3_tool_capable')",
            name="ck_llm_provider_profiles_conformance_level",
        ),
    )

    op.create_table(
        "llm_context_packages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("task_kind", sa.String(), nullable=False),
        sa.Column("visibility_mode", sa.String(), nullable=False, server_default="gm_private"),
        sa.Column("gm_instruction", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_refs_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("rendered_prompt", sa.Text(), nullable=False),
        sa.Column("source_ref_hash", sa.String(), nullable=False),
        sa.Column("review_status", sa.String(), nullable=False, server_default="unreviewed"),
        sa.Column("reviewed_at", sa.String(), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("visibility_mode in ('gm_private', 'public_safe')", name="ck_llm_context_packages_visibility_mode"),
        sa.CheckConstraint("review_status in ('unreviewed', 'reviewed')", name="ck_llm_context_packages_review_status"),
    )
    op.create_index("ix_llm_context_packages_campaign_id", "llm_context_packages", ["campaign_id"])
    op.create_index("ix_llm_context_packages_session_id", "llm_context_packages", ["session_id"])
    op.create_index("ix_llm_context_packages_source_ref_hash", "llm_context_packages", ["source_ref_hash"])

    op.create_table(
        "llm_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider_profile_id", sa.String(), sa.ForeignKey("llm_provider_profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("context_package_id", sa.String(), sa.ForeignKey("llm_context_packages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("parent_run_id", sa.String(), sa.ForeignKey("llm_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("parse_failure_reason", sa.String(), nullable=True),
        sa.Column("repair_attempted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("request_metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("request_json", sa.Text(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("normalized_output_json", sa.Text(), nullable=True),
        sa.Column("prompt_tokens_estimate", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("cancel_requested_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("status in ('running', 'succeeded', 'failed', 'canceled')", name="ck_llm_runs_status"),
    )
    op.create_index("ix_llm_runs_campaign_id", "llm_runs", ["campaign_id"])
    op.create_index("ix_llm_runs_session_id", "llm_runs", ["session_id"])
    op.create_index("ix_llm_runs_provider_profile_id", "llm_runs", ["provider_profile_id"])
    op.create_index("ix_llm_runs_context_package_id", "llm_runs", ["context_package_id"])
    op.create_index("ix_llm_runs_parent_run_id", "llm_runs", ["parent_run_id"])

    op.create_table(
        "session_recaps",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_llm_run_id", sa.String(), sa.ForeignKey("llm_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("evidence_refs_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("ix_session_recaps_campaign_id", "session_recaps", ["campaign_id"])
    op.create_index("ix_session_recaps_session_id", "session_recaps", ["session_id"])
    op.create_index("ix_session_recaps_source_llm_run_id", "session_recaps", ["source_llm_run_id"])

    op.create_table(
        "campaign_memory_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_candidate_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("evidence_refs_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("ix_campaign_memory_entries_campaign_id", "campaign_memory_entries", ["campaign_id"])
    op.create_index("ix_campaign_memory_entries_session_id", "campaign_memory_entries", ["session_id"])
    op.create_index("ix_campaign_memory_entries_source_candidate_id", "campaign_memory_entries", ["source_candidate_id"])

    op.create_table(
        "memory_candidates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_llm_run_id", sa.String(), sa.ForeignKey("llm_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_recap_id", sa.String(), sa.ForeignKey("session_recaps.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("claim_strength", sa.String(), nullable=False),
        sa.Column("evidence_refs_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("validation_errors_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("edited_from_candidate_id", sa.String(), sa.ForeignKey("memory_candidates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("applied_memory_entry_id", sa.String(), sa.ForeignKey("campaign_memory_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("status in ('draft', 'edited', 'accepted', 'rejected')", name="ck_memory_candidates_status"),
        sa.CheckConstraint(
            "claim_strength in ('directly_evidenced', 'strong_inference', 'weak_inference', 'gm_review_required')",
            name="ck_memory_candidates_claim_strength",
        ),
    )
    op.create_index("ix_memory_candidates_campaign_id", "memory_candidates", ["campaign_id"])
    op.create_index("ix_memory_candidates_session_id", "memory_candidates", ["session_id"])
    op.create_index("ix_memory_candidates_source_llm_run_id", "memory_candidates", ["source_llm_run_id"])
    op.create_index("ix_memory_candidates_source_recap_id", "memory_candidates", ["source_recap_id"])
    op.create_index("ix_memory_candidates_edited_from_candidate_id", "memory_candidates", ["edited_from_candidate_id"])
    op.create_index("uq_memory_candidates_applied_entry", "memory_candidates", ["applied_memory_entry_id"], unique=True, sqlite_where=sa.text("applied_memory_entry_id IS NOT NULL"))

    op.create_table(
        "entity_aliases",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=True),
        sa.Column("alias_text", sa.String(), nullable=False),
        sa.Column("normalized_alias", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="manual"),
        sa.Column("source_ref_json", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(), nullable=False, server_default="gm_confirmed"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("source in ('manual', 'observed', 'generated_pending_approval')", name="ck_entity_aliases_source"),
        sa.CheckConstraint("confidence in ('gm_confirmed', 'observed', 'generated_pending_approval')", name="ck_entity_aliases_confidence"),
        sa.UniqueConstraint("campaign_id", "alias_text", name="uq_entity_aliases_campaign_alias"),
    )
    op.create_index("ix_entity_aliases_campaign_id", "entity_aliases", ["campaign_id"])
    op.create_index("ix_entity_aliases_entity_id", "entity_aliases", ["entity_id"])
    op.create_index("ix_entity_aliases_normalized_alias", "entity_aliases", ["normalized_alias"])

    op.create_table(
        "scribe_search_index",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_kind", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("source_revision", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("lane", sa.String(), nullable=False, server_default="canon"),
        sa.Column("visibility", sa.String(), nullable=False, server_default="gm_private"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.UniqueConstraint("source_kind", "source_id", "source_revision", name="uq_scribe_search_source_revision"),
    )
    op.create_index("ix_scribe_search_index_campaign_id", "scribe_search_index", ["campaign_id"])
    op.create_index("ix_scribe_search_index_source_kind", "scribe_search_index", ["source_kind"])
    op.create_index("ix_scribe_search_index_source_id", "scribe_search_index", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_scribe_search_index_source_id", table_name="scribe_search_index")
    op.drop_index("ix_scribe_search_index_source_kind", table_name="scribe_search_index")
    op.drop_index("ix_scribe_search_index_campaign_id", table_name="scribe_search_index")
    op.drop_table("scribe_search_index")
    op.drop_index("ix_entity_aliases_normalized_alias", table_name="entity_aliases")
    op.drop_index("ix_entity_aliases_entity_id", table_name="entity_aliases")
    op.drop_index("ix_entity_aliases_campaign_id", table_name="entity_aliases")
    op.drop_table("entity_aliases")
    op.drop_index("uq_memory_candidates_applied_entry", table_name="memory_candidates")
    op.drop_index("ix_memory_candidates_edited_from_candidate_id", table_name="memory_candidates")
    op.drop_index("ix_memory_candidates_source_recap_id", table_name="memory_candidates")
    op.drop_index("ix_memory_candidates_source_llm_run_id", table_name="memory_candidates")
    op.drop_index("ix_memory_candidates_session_id", table_name="memory_candidates")
    op.drop_index("ix_memory_candidates_campaign_id", table_name="memory_candidates")
    op.drop_table("memory_candidates")
    op.drop_index("ix_campaign_memory_entries_source_candidate_id", table_name="campaign_memory_entries")
    op.drop_index("ix_campaign_memory_entries_session_id", table_name="campaign_memory_entries")
    op.drop_index("ix_campaign_memory_entries_campaign_id", table_name="campaign_memory_entries")
    op.drop_table("campaign_memory_entries")
    op.drop_index("ix_session_recaps_source_llm_run_id", table_name="session_recaps")
    op.drop_index("ix_session_recaps_session_id", table_name="session_recaps")
    op.drop_index("ix_session_recaps_campaign_id", table_name="session_recaps")
    op.drop_table("session_recaps")
    op.drop_index("ix_llm_runs_parent_run_id", table_name="llm_runs")
    op.drop_index("ix_llm_runs_context_package_id", table_name="llm_runs")
    op.drop_index("ix_llm_runs_provider_profile_id", table_name="llm_runs")
    op.drop_index("ix_llm_runs_session_id", table_name="llm_runs")
    op.drop_index("ix_llm_runs_campaign_id", table_name="llm_runs")
    op.drop_table("llm_runs")
    op.drop_index("ix_llm_context_packages_source_ref_hash", table_name="llm_context_packages")
    op.drop_index("ix_llm_context_packages_session_id", table_name="llm_context_packages")
    op.drop_index("ix_llm_context_packages_campaign_id", table_name="llm_context_packages")
    op.drop_table("llm_context_packages")
    op.drop_table("llm_provider_profiles")
    op.drop_index("ix_session_transcript_events_corrects_event_id", table_name="session_transcript_events")
    op.drop_index("ix_session_transcript_events_scene_id", table_name="session_transcript_events")
    op.drop_index("ix_session_transcript_events_session_id", table_name="session_transcript_events")
    op.drop_index("ix_session_transcript_events_campaign_id", table_name="session_transcript_events")
    op.drop_table("session_transcript_events")
    op.drop_table("session_order_counters")
