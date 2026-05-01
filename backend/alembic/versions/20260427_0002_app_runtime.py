"""app runtime singleton

Revision ID: 20260427_0002
Revises: 20260427_0001
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0002"
down_revision = "20260427_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_runtime",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("active_campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="SET NULL")),
        sa.Column("active_session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="SET NULL")),
        sa.Column("active_scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("id = 'runtime'", name="ck_app_runtime_singleton"),
    )


def downgrade() -> None:
    op.drop_table("app_runtime")
