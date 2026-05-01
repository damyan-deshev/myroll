"""manual fog mvp

Revision ID: 20260427_0007
Revises: 20260427_0006
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0007"
down_revision = "20260427_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scene_map_fog_masks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_map_id", sa.String(), sa.ForeignKey("scene_maps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("relative_path", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("width > 0", name="ck_scene_map_fog_masks_width_positive"),
        sa.CheckConstraint("height > 0", name="ck_scene_map_fog_masks_height_positive"),
        sa.CheckConstraint("revision >= 1", name="ck_scene_map_fog_masks_revision_positive"),
        sa.UniqueConstraint("scene_map_id", name="uq_scene_map_fog_masks_scene_map_id"),
    )
    op.create_index("ix_scene_map_fog_masks_campaign_id", "scene_map_fog_masks", ["campaign_id"])
    op.create_index("ix_scene_map_fog_masks_scene_id", "scene_map_fog_masks", ["scene_id"])


def downgrade() -> None:
    op.drop_index("ix_scene_map_fog_masks_scene_id", table_name="scene_map_fog_masks")
    op.drop_index("ix_scene_map_fog_masks_campaign_id", table_name="scene_map_fog_masks")
    op.drop_table("scene_map_fog_masks")
