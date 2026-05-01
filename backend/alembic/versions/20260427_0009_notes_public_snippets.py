"""notes public snippets

Revision ID: 20260427_0009
Revises: 20260427_0008
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0009"
down_revision = "20260427_0008"
branch_labels = None
depends_on = None


def _rebuild_player_display_runtime(mode_check: str) -> None:
    op.drop_index("ix_player_display_runtime_active_scene_id", table_name="player_display_runtime")
    op.drop_index("ix_player_display_runtime_active_session_id", table_name="player_display_runtime")
    op.drop_index("ix_player_display_runtime_active_campaign_id", table_name="player_display_runtime")
    op.create_table(
        "player_display_runtime_rebuild",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("active_campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("active_session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("active_scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("subtitle", sa.String(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("identify_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("identify_until", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("id = 'player_display'", name="ck_player_display_runtime_singleton"),
        sa.CheckConstraint(mode_check, name="ck_player_display_runtime_mode"),
    )
    op.execute(
        """
        INSERT INTO player_display_runtime_rebuild (
            id,
            mode,
            active_campaign_id,
            active_session_id,
            active_scene_id,
            title,
            subtitle,
            payload_json,
            revision,
            identify_revision,
            identify_until,
            updated_at
        )
        SELECT
            id,
            mode,
            active_campaign_id,
            active_session_id,
            active_scene_id,
            title,
            subtitle,
            payload_json,
            revision,
            identify_revision,
            identify_until,
            updated_at
        FROM player_display_runtime
        """
    )
    op.drop_table("player_display_runtime")
    op.rename_table("player_display_runtime_rebuild", "player_display_runtime")
    op.create_index("ix_player_display_runtime_active_campaign_id", "player_display_runtime", ["active_campaign_id"])
    op.create_index("ix_player_display_runtime_active_session_id", "player_display_runtime", ["active_session_id"])
    op.create_index("ix_player_display_runtime_active_scene_id", "player_display_runtime", ["active_scene_id"])


def upgrade() -> None:
    op.create_table(
        "note_sources",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("readonly", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("kind in ('internal', 'imported_markdown')", name="ck_note_sources_kind"),
    )
    op.create_index("ix_note_sources_campaign_id", "note_sources", ["campaign_id"])

    op.create_table(
        "notes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.String(), sa.ForeignKey("note_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("asset_id", sa.String(), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("private_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("source_label", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("ix_notes_campaign_id", "notes", ["campaign_id"])
    op.create_index("ix_notes_source_id", "notes", ["source_id"])
    op.create_index("ix_notes_session_id", "notes", ["session_id"])
    op.create_index("ix_notes_scene_id", "notes", ["scene_id"])
    op.create_index("ix_notes_asset_id", "notes", ["asset_id"])

    op.create_table(
        "public_snippets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note_id", sa.String(), sa.ForeignKey("notes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("format", sa.String(), nullable=False, server_default="markdown"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("format in ('markdown')", name="ck_public_snippets_format"),
    )
    op.create_index("ix_public_snippets_campaign_id", "public_snippets", ["campaign_id"])
    op.create_index("ix_public_snippets_note_id", "public_snippets", ["note_id"])

    _rebuild_player_display_runtime("mode in ('blackout', 'intermission', 'scene_title', 'image', 'map', 'text')")


def downgrade() -> None:
    op.execute(
        """
        UPDATE player_display_runtime
        SET mode = 'blackout',
            title = NULL,
            subtitle = NULL,
            payload_json = '{}'
        WHERE mode = 'text'
        """
    )
    _rebuild_player_display_runtime("mode in ('blackout', 'intermission', 'scene_title', 'image', 'map')")
    op.drop_index("ix_public_snippets_note_id", table_name="public_snippets")
    op.drop_index("ix_public_snippets_campaign_id", table_name="public_snippets")
    op.drop_table("public_snippets")
    op.drop_index("ix_notes_asset_id", table_name="notes")
    op.drop_index("ix_notes_scene_id", table_name="notes")
    op.drop_index("ix_notes_session_id", table_name="notes")
    op.drop_index("ix_notes_source_id", table_name="notes")
    op.drop_index("ix_notes_campaign_id", table_name="notes")
    op.drop_table("notes")
    op.drop_index("ix_note_sources_campaign_id", table_name="note_sources")
    op.drop_table("note_sources")
