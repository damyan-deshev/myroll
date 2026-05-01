"""player display runtime singleton

Revision ID: 20260427_0004
Revises: 20260427_0003
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0004"
down_revision = "20260427_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_display_runtime",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column(
            "active_campaign_id",
            sa.String(),
            sa.ForeignKey("campaigns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "active_session_id",
            sa.String(),
            sa.ForeignKey("sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "active_scene_id",
            sa.String(),
            sa.ForeignKey("scenes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("subtitle", sa.String(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("identify_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("identify_until", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("id = 'player_display'", name="ck_player_display_runtime_singleton"),
        sa.CheckConstraint(
            "mode in ('blackout', 'intermission', 'scene_title')",
            name="ck_player_display_runtime_mode",
        ),
    )
    op.create_index(
        "ix_player_display_runtime_active_campaign_id",
        "player_display_runtime",
        ["active_campaign_id"],
    )
    op.create_index(
        "ix_player_display_runtime_active_session_id",
        "player_display_runtime",
        ["active_session_id"],
    )
    op.create_index(
        "ix_player_display_runtime_active_scene_id",
        "player_display_runtime",
        ["active_scene_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_player_display_runtime_active_scene_id", table_name="player_display_runtime")
    op.drop_index("ix_player_display_runtime_active_session_id", table_name="player_display_runtime")
    op.drop_index("ix_player_display_runtime_active_campaign_id", table_name="player_display_runtime")
    op.drop_table("player_display_runtime")
