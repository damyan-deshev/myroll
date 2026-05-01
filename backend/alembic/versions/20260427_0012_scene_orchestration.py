"""scene orchestration

Revision ID: 20260427_0012
Revises: 20260427_0011
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0012"
down_revision = "20260427_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scene_contexts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("active_encounter_id", sa.String(), sa.ForeignKey("combat_encounters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("staged_display_mode", sa.String(), nullable=False, server_default="none"),
        sa.Column("staged_public_snippet_id", sa.String(), sa.ForeignKey("public_snippets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "staged_display_mode in ('none', 'blackout', 'intermission', 'scene_title', 'active_map', 'initiative', 'public_snippet')",
            name="ck_scene_contexts_staged_display_mode",
        ),
    )
    op.create_index("ix_scene_contexts_campaign_id", "scene_contexts", ["campaign_id"])
    op.create_index("ix_scene_contexts_scene_id", "scene_contexts", ["scene_id"])
    op.create_index("uq_scene_contexts_scene_id", "scene_contexts", ["scene_id"], unique=True)
    op.create_index("ix_scene_contexts_active_encounter_id", "scene_contexts", ["active_encounter_id"])
    op.create_index("ix_scene_contexts_staged_public_snippet_id", "scene_contexts", ["staged_public_snippet_id"])

    op.create_table(
        "scene_entity_links",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="supporting"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "role in ('featured', 'supporting', 'location', 'clue', 'threat', 'other')",
            name="ck_scene_entity_links_role",
        ),
    )
    op.create_index("ix_scene_entity_links_campaign_id", "scene_entity_links", ["campaign_id"])
    op.create_index("ix_scene_entity_links_scene_id", "scene_entity_links", ["scene_id"])
    op.create_index("ix_scene_entity_links_entity_id", "scene_entity_links", ["entity_id"])
    op.create_index("uq_scene_entity_links_scene_entity", "scene_entity_links", ["scene_id", "entity_id"], unique=True)

    op.create_table(
        "scene_public_snippet_links",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("public_snippet_id", sa.String(), sa.ForeignKey("public_snippets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("ix_scene_public_snippet_links_campaign_id", "scene_public_snippet_links", ["campaign_id"])
    op.create_index("ix_scene_public_snippet_links_scene_id", "scene_public_snippet_links", ["scene_id"])
    op.create_index("ix_scene_public_snippet_links_public_snippet_id", "scene_public_snippet_links", ["public_snippet_id"])
    op.create_index(
        "uq_scene_public_snippet_links_scene_snippet",
        "scene_public_snippet_links",
        ["scene_id", "public_snippet_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_scene_public_snippet_links_scene_snippet", table_name="scene_public_snippet_links")
    op.drop_index("ix_scene_public_snippet_links_public_snippet_id", table_name="scene_public_snippet_links")
    op.drop_index("ix_scene_public_snippet_links_scene_id", table_name="scene_public_snippet_links")
    op.drop_index("ix_scene_public_snippet_links_campaign_id", table_name="scene_public_snippet_links")
    op.drop_table("scene_public_snippet_links")

    op.drop_index("uq_scene_entity_links_scene_entity", table_name="scene_entity_links")
    op.drop_index("ix_scene_entity_links_entity_id", table_name="scene_entity_links")
    op.drop_index("ix_scene_entity_links_scene_id", table_name="scene_entity_links")
    op.drop_index("ix_scene_entity_links_campaign_id", table_name="scene_entity_links")
    op.drop_table("scene_entity_links")

    op.drop_index("ix_scene_contexts_staged_public_snippet_id", table_name="scene_contexts")
    op.drop_index("ix_scene_contexts_active_encounter_id", table_name="scene_contexts")
    op.drop_index("uq_scene_contexts_scene_id", table_name="scene_contexts")
    op.drop_index("ix_scene_contexts_scene_id", table_name="scene_contexts")
    op.drop_index("ix_scene_contexts_campaign_id", table_name="scene_contexts")
    op.drop_table("scene_contexts")
