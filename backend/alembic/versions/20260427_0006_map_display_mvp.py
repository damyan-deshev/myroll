"""map display mvp

Revision ID: 20260427_0006
Revises: 20260427_0005
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0006"
down_revision = "20260427_0005"
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
    op.create_table(
        "maps",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.String(), sa.ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("grid_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("grid_size_px", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("grid_offset_x", sa.Float(), nullable=False, server_default="0"),
        sa.Column("grid_offset_y", sa.Float(), nullable=False, server_default="0"),
        sa.Column("grid_color", sa.String(), nullable=False, server_default="#FFFFFF"),
        sa.Column("grid_opacity", sa.Float(), nullable=False, server_default="0.35"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("width > 0", name="ck_maps_width_positive"),
        sa.CheckConstraint("height > 0", name="ck_maps_height_positive"),
        sa.CheckConstraint("grid_size_px >= 4 AND grid_size_px <= 500", name="ck_maps_grid_size"),
        sa.CheckConstraint("grid_opacity >= 0 AND grid_opacity <= 1", name="ck_maps_grid_opacity"),
    )
    op.create_index("ix_maps_campaign_id", "maps", ["campaign_id"])
    op.create_index("ix_maps_asset_id", "maps", ["asset_id"])

    op.create_table(
        "scene_maps",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("map_id", sa.String(), sa.ForeignKey("maps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("player_fit_mode", sa.String(), nullable=False, server_default="fit"),
        sa.Column("player_grid_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "player_fit_mode in ('fit', 'fill', 'stretch', 'actual_size')",
            name="ck_scene_maps_player_fit_mode",
        ),
    )
    op.create_index("ix_scene_maps_campaign_id", "scene_maps", ["campaign_id"])
    op.create_index("ix_scene_maps_scene_id", "scene_maps", ["scene_id"])
    op.create_index("ix_scene_maps_map_id", "scene_maps", ["map_id"])
    op.create_index(
        "uq_scene_maps_one_active_per_scene",
        "scene_maps",
        ["scene_id"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
    )

    _rebuild_player_display_runtime("mode in ('blackout', 'intermission', 'scene_title', 'image', 'map')")


def downgrade() -> None:
    _rebuild_player_display_runtime("mode in ('blackout', 'intermission', 'scene_title', 'image')")
    op.drop_index("uq_scene_maps_one_active_per_scene", table_name="scene_maps")
    op.drop_index("ix_scene_maps_map_id", table_name="scene_maps")
    op.drop_index("ix_scene_maps_scene_id", table_name="scene_maps")
    op.drop_index("ix_scene_maps_campaign_id", table_name="scene_maps")
    op.drop_table("scene_maps")
    op.drop_index("ix_maps_asset_id", table_name="maps")
    op.drop_index("ix_maps_campaign_id", table_name="maps")
    op.drop_table("maps")
