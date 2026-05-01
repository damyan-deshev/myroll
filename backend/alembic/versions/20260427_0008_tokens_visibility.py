"""tokens visibility

Revision ID: 20260427_0008
Revises: 20260427_0007
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0008"
down_revision = "20260427_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scene_map_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_map_id", sa.String(), sa.ForeignKey("scene_maps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("asset_id", sa.String(), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("rotation", sa.Float(), nullable=False, server_default="0"),
        sa.Column("z_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("visibility", sa.String(), nullable=False, server_default="gm_only"),
        sa.Column("label_visibility", sa.String(), nullable=False, server_default="gm_only"),
        sa.Column("shape", sa.String(), nullable=False, server_default="circle"),
        sa.Column("color", sa.String(), nullable=False, server_default="#D94841"),
        sa.Column("border_color", sa.String(), nullable=False, server_default="#FFFFFF"),
        sa.Column("opacity", sa.Float(), nullable=False, server_default="1"),
        sa.Column("status_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "visibility in ('gm_only', 'player_visible', 'hidden_until_revealed')",
            name="ck_scene_map_tokens_visibility",
        ),
        sa.CheckConstraint(
            "label_visibility in ('gm_only', 'player_visible', 'hidden')",
            name="ck_scene_map_tokens_label_visibility",
        ),
        sa.CheckConstraint(
            "shape in ('circle', 'square', 'portrait', 'marker')",
            name="ck_scene_map_tokens_shape",
        ),
        sa.CheckConstraint("width > 0 AND width <= 1000", name="ck_scene_map_tokens_width"),
        sa.CheckConstraint("height > 0 AND height <= 1000", name="ck_scene_map_tokens_height"),
        sa.CheckConstraint("rotation >= 0 AND rotation < 360", name="ck_scene_map_tokens_rotation"),
        sa.CheckConstraint("opacity >= 0 AND opacity <= 1", name="ck_scene_map_tokens_opacity"),
    )
    op.create_index("ix_scene_map_tokens_campaign_id", "scene_map_tokens", ["campaign_id"])
    op.create_index("ix_scene_map_tokens_scene_id", "scene_map_tokens", ["scene_id"])
    op.create_index("ix_scene_map_tokens_scene_map_id", "scene_map_tokens", ["scene_map_id"])
    op.create_index("ix_scene_map_tokens_asset_id", "scene_map_tokens", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_scene_map_tokens_asset_id", table_name="scene_map_tokens")
    op.drop_index("ix_scene_map_tokens_scene_map_id", table_name="scene_map_tokens")
    op.drop_index("ix_scene_map_tokens_scene_id", table_name="scene_map_tokens")
    op.drop_index("ix_scene_map_tokens_campaign_id", table_name="scene_map_tokens")
    op.drop_table("scene_map_tokens")
