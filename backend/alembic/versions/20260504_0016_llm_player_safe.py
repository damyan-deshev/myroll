"""llm player-safe recap gate

Revision ID: 20260504_0016
Revises: 20260504_0015
Create Date: 2026-05-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260504_0016"
down_revision = "20260504_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("session_recaps", sa.Column("public_safe", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("session_recaps", sa.Column("sensitivity_reason", sa.String(), nullable=True))
    op.add_column("campaign_memory_entries", sa.Column("public_safe", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("campaign_memory_entries", sa.Column("sensitivity_reason", sa.String(), nullable=True))

    op.add_column("llm_context_packages", sa.Column("context_options_json", sa.Text(), nullable=False, server_default="{}"))

    op.add_column("public_snippets", sa.Column("creation_source", sa.String(), nullable=False, server_default="manual"))
    op.add_column("public_snippets", sa.Column("source_llm_run_id", sa.String(), nullable=True))
    op.add_column("public_snippets", sa.Column("source_draft_hash", sa.String(), nullable=True))
    op.add_column("public_snippets", sa.Column("safety_warnings_json", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("public_snippets", sa.Column("last_published_at", sa.String(), nullable=True))
    op.add_column("public_snippets", sa.Column("publication_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_public_snippets_source_llm_run_id", "public_snippets", ["source_llm_run_id"])


def downgrade() -> None:
    op.drop_index("ix_public_snippets_source_llm_run_id", table_name="public_snippets")
    op.drop_column("public_snippets", "publication_count")
    op.drop_column("public_snippets", "last_published_at")
    op.drop_column("public_snippets", "safety_warnings_json")
    op.drop_column("public_snippets", "source_draft_hash")
    op.drop_column("public_snippets", "source_llm_run_id")
    op.drop_column("public_snippets", "creation_source")
    op.drop_column("llm_context_packages", "context_options_json")
    op.drop_column("campaign_memory_entries", "sensitivity_reason")
    op.drop_column("campaign_memory_entries", "public_safe")
    op.drop_column("session_recaps", "sensitivity_reason")
    op.drop_column("session_recaps", "public_safe")
