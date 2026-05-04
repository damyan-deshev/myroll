"""llm proposal canonization bridge

Revision ID: 20260504_0017
Revises: 20260504_0016
Create Date: 2026-05-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260504_0017"
down_revision = "20260504_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("memory_candidates") as batch_op:
        batch_op.add_column(sa.Column("source_planning_marker_id", sa.String(), sa.ForeignKey("planning_markers.id", ondelete="SET NULL", name="fk_memory_candidates_source_planning_marker_id"), nullable=True))
        batch_op.add_column(sa.Column("source_proposal_option_id", sa.String(), sa.ForeignKey("proposal_options.id", ondelete="SET NULL", name="fk_memory_candidates_source_proposal_option_id"), nullable=True))
        batch_op.add_column(sa.Column("normalization_warnings_json", sa.Text(), nullable=False, server_default="[]"))
    op.create_index("ix_memory_candidates_source_planning_marker_id", "memory_candidates", ["source_planning_marker_id"])
    op.create_index("ix_memory_candidates_source_proposal_option_id", "memory_candidates", ["source_proposal_option_id"])

    with op.batch_alter_table("campaign_memory_entries") as batch_op:
        batch_op.add_column(sa.Column("source_planning_marker_id", sa.String(), sa.ForeignKey("planning_markers.id", ondelete="SET NULL", name="fk_campaign_memory_entries_source_planning_marker_id"), nullable=True))
        batch_op.add_column(sa.Column("source_proposal_option_id", sa.String(), sa.ForeignKey("proposal_options.id", ondelete="SET NULL", name="fk_campaign_memory_entries_source_proposal_option_id"), nullable=True))
    op.create_index("ix_campaign_memory_entries_source_planning_marker_id", "campaign_memory_entries", ["source_planning_marker_id"])
    op.create_index("ix_campaign_memory_entries_source_proposal_option_id", "campaign_memory_entries", ["source_proposal_option_id"])
    op.create_index(
        "uq_campaign_memory_entries_source_marker",
        "campaign_memory_entries",
        ["source_planning_marker_id"],
        unique=True,
        sqlite_where=sa.text("source_planning_marker_id IS NOT NULL"),
    )

    with op.batch_alter_table("planning_markers") as batch_op:
        batch_op.add_column(sa.Column("canonized_at", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("canon_memory_entry_id", sa.String(), sa.ForeignKey("campaign_memory_entries.id", ondelete="SET NULL", name="fk_planning_markers_canon_memory_entry_id"), nullable=True))
    op.create_index("ix_planning_markers_canon_memory_entry_id", "planning_markers", ["canon_memory_entry_id"])


def downgrade() -> None:
    op.drop_index("ix_planning_markers_canon_memory_entry_id", table_name="planning_markers")
    with op.batch_alter_table("planning_markers") as batch_op:
        batch_op.drop_column("canon_memory_entry_id")
        batch_op.drop_column("canonized_at")

    op.drop_index("uq_campaign_memory_entries_source_marker", table_name="campaign_memory_entries")
    op.drop_index("ix_campaign_memory_entries_source_proposal_option_id", table_name="campaign_memory_entries")
    op.drop_index("ix_campaign_memory_entries_source_planning_marker_id", table_name="campaign_memory_entries")
    with op.batch_alter_table("campaign_memory_entries") as batch_op:
        batch_op.drop_column("source_proposal_option_id")
        batch_op.drop_column("source_planning_marker_id")

    op.drop_index("ix_memory_candidates_source_proposal_option_id", table_name="memory_candidates")
    op.drop_index("ix_memory_candidates_source_planning_marker_id", table_name="memory_candidates")
    with op.batch_alter_table("memory_candidates") as batch_op:
        batch_op.drop_column("normalization_warnings_json")
        batch_op.drop_column("source_proposal_option_id")
        batch_op.drop_column("source_planning_marker_id")
