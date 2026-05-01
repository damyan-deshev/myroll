"""asset metadata and image display

Revision ID: 20260427_0005
Revises: 20260427_0004
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0005"
down_revision = "20260427_0004"
branch_labels = None
depends_on = None


ASSET_KINDS = (
    "'map_image'",
    "'handout_image'",
    "'npc_portrait'",
    "'item_image'",
    "'scene_image'",
    "'audio'",
    "'markdown'",
    "'pdf'",
    "'other'",
)


def _rebuild_player_display_runtime(mode_check: str) -> None:
    op.drop_index("ix_player_display_runtime_active_scene_id", table_name="player_display_runtime")
    op.drop_index("ix_player_display_runtime_active_session_id", table_name="player_display_runtime")
    op.drop_index("ix_player_display_runtime_active_campaign_id", table_name="player_display_runtime")
    op.create_table(
        "player_display_runtime_rebuild",
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


def upgrade() -> None:
    with op.batch_alter_table(
        "assets",
        recreate="always",
        table_args=(
            sa.CheckConstraint(f"kind in ({', '.join(ASSET_KINDS)})", name="ck_assets_kind"),
            sa.CheckConstraint(
                "visibility in ('private', 'public_displayable')",
                name="ck_assets_visibility",
            ),
        ),
    ) as batch_op:
        batch_op.add_column(sa.Column("name", sa.String(), nullable=False, server_default="Untitled asset"))
        batch_op.add_column(sa.Column("visibility", sa.String(), nullable=False, server_default="private"))
        batch_op.add_column(sa.Column("original_filename", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("duration_ms", sa.Integer(), nullable=True))

    _rebuild_player_display_runtime("mode in ('blackout', 'intermission', 'scene_title', 'image')")


def downgrade() -> None:
    _rebuild_player_display_runtime("mode in ('blackout', 'intermission', 'scene_title')")

    with op.batch_alter_table("assets", recreate="always") as batch_op:
        batch_op.drop_column("duration_ms")
        batch_op.drop_column("tags_json")
        batch_op.drop_column("original_filename")
        batch_op.drop_column("visibility")
        batch_op.drop_column("name")
