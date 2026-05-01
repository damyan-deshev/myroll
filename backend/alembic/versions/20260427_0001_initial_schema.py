"""initial schema

Revision ID: 20260427_0001
Revises:
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_meta",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("starts_at", sa.String(), nullable=True),
        sa.Column("ended_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("ix_sessions_campaign_id", "sessions", ["campaign_id"])
    op.create_table(
        "scenes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("ix_scenes_campaign_id", "scenes", ["campaign_id"])
    op.create_index("ix_scenes_session_id", "scenes", ["session_id"])
    op.create_table(
        "display_states",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("ix_display_states_campaign_id", "display_states", ["campaign_id"])
    op.create_index("ix_display_states_scene_id", "display_states", ["scene_id"])
    op.create_table(
        "assets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(), nullable=False),
        sa.Column("relative_path", sa.String(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("ix_assets_campaign_id", "assets", ["campaign_id"])


def downgrade() -> None:
    op.drop_index("ix_assets_campaign_id", table_name="assets")
    op.drop_table("assets")
    op.drop_index("ix_display_states_scene_id", table_name="display_states")
    op.drop_index("ix_display_states_campaign_id", table_name="display_states")
    op.drop_table("display_states")
    op.drop_index("ix_scenes_session_id", table_name="scenes")
    op.drop_index("ix_scenes_campaign_id", table_name="scenes")
    op.drop_table("scenes")
    op.drop_index("ix_sessions_campaign_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("campaigns")
    op.drop_table("app_meta")
