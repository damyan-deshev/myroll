"""llm branch proposals

Revision ID: 20260504_0015
Revises: 20260504_0014
Create Date: 2026-05-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260504_0015"
down_revision = "20260504_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_context_packages", sa.Column("scope_kind", sa.String(), nullable=False, server_default="session"))
    # SQLite cannot add a foreign key constraint through ALTER TABLE; the ORM
    # keeps the relationship while existing SQLite databases receive the plain
    # nullable column here.
    op.add_column("llm_context_packages", sa.Column("scene_id", sa.String(), nullable=True))
    op.add_column("llm_context_packages", sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"))
    op.create_index("ix_llm_context_packages_scene_id", "llm_context_packages", ["scene_id"])

    op.create_table(
        "proposal_sets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("llm_run_id", sa.String(), sa.ForeignKey("llm_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("context_package_id", sa.String(), sa.ForeignKey("llm_context_packages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_kind", sa.String(), nullable=False),
        sa.Column("scope_kind", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="proposed"),
        sa.Column("normalization_warnings_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("scope_kind in ('campaign', 'session', 'scene')", name="ck_proposal_sets_scope_kind"),
        sa.CheckConstraint("status in ('proposed', 'partially_used', 'rejected', 'superseded')", name="ck_proposal_sets_status"),
    )
    op.create_index("ix_proposal_sets_campaign_id", "proposal_sets", ["campaign_id"])
    op.create_index("ix_proposal_sets_session_id", "proposal_sets", ["session_id"])
    op.create_index("ix_proposal_sets_scene_id", "proposal_sets", ["scene_id"])
    op.create_index("ix_proposal_sets_llm_run_id", "proposal_sets", ["llm_run_id"])
    op.create_index("ix_proposal_sets_context_package_id", "proposal_sets", ["context_package_id"])

    op.create_table(
        "proposal_options",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("proposal_set_id", sa.String(), sa.ForeignKey("proposal_sets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stable_option_key", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("consequences", sa.Text(), nullable=False, server_default=""),
        sa.Column("reveals", sa.Text(), nullable=False, server_default=""),
        sa.Column("stays_hidden", sa.Text(), nullable=False, server_default=""),
        sa.Column("proposed_delta_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("planning_marker_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="proposed"),
        sa.Column("selected_at", sa.String(), nullable=True),
        sa.Column("canonized_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "status in ('proposed', 'selected', 'rejected', 'saved_for_later', 'superseded', 'canonized')",
            name="ck_proposal_options_status",
        ),
        sa.UniqueConstraint("proposal_set_id", "stable_option_key", name="uq_proposal_options_set_key"),
    )
    op.create_index("ix_proposal_options_proposal_set_id", "proposal_options", ["proposal_set_id"])

    op.create_table(
        "planning_markers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_proposal_option_id", sa.String(), sa.ForeignKey("proposal_options.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scope_kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("marker_text", sa.Text(), nullable=False),
        sa.Column("original_marker_text", sa.Text(), nullable=True),
        sa.Column("lint_warnings_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("provenance_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("edited_at", sa.String(), nullable=True),
        sa.Column("edited_from_source", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("scope_kind in ('campaign', 'session', 'scene')", name="ck_planning_markers_scope_kind"),
        sa.CheckConstraint(
            "status in ('active', 'expired', 'superseded', 'canonized', 'discarded')",
            name="ck_planning_markers_status",
        ),
    )
    op.create_index("ix_planning_markers_campaign_id", "planning_markers", ["campaign_id"])
    op.create_index("ix_planning_markers_session_id", "planning_markers", ["session_id"])
    op.create_index("ix_planning_markers_scene_id", "planning_markers", ["scene_id"])
    op.create_index("ix_planning_markers_source_proposal_option_id", "planning_markers", ["source_proposal_option_id"])
    op.create_index(
        "uq_planning_markers_source_option",
        "planning_markers",
        ["source_proposal_option_id"],
        unique=True,
        sqlite_where=sa.text("source_proposal_option_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_planning_markers_source_option", table_name="planning_markers")
    op.drop_index("ix_planning_markers_source_proposal_option_id", table_name="planning_markers")
    op.drop_index("ix_planning_markers_scene_id", table_name="planning_markers")
    op.drop_index("ix_planning_markers_session_id", table_name="planning_markers")
    op.drop_index("ix_planning_markers_campaign_id", table_name="planning_markers")
    op.drop_table("planning_markers")
    op.drop_index("ix_proposal_options_proposal_set_id", table_name="proposal_options")
    op.drop_table("proposal_options")
    op.drop_index("ix_proposal_sets_context_package_id", table_name="proposal_sets")
    op.drop_index("ix_proposal_sets_llm_run_id", table_name="proposal_sets")
    op.drop_index("ix_proposal_sets_scene_id", table_name="proposal_sets")
    op.drop_index("ix_proposal_sets_session_id", table_name="proposal_sets")
    op.drop_index("ix_proposal_sets_campaign_id", table_name="proposal_sets")
    op.drop_table("proposal_sets")
    op.drop_index("ix_llm_context_packages_scene_id", table_name="llm_context_packages")
    op.drop_column("llm_context_packages", "warnings_json")
    op.drop_column("llm_context_packages", "scene_id")
    op.drop_column("llm_context_packages", "scope_kind")
