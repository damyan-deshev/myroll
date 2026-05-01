"""workspace widgets

Revision ID: 20260427_0003
Revises: 20260427_0002
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0003"
down_revision = "20260427_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_widgets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("scope_type", sa.String(), nullable=False, server_default="global"),
        sa.Column("scope_id", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("x", sa.Integer(), nullable=False),
        sa.Column("y", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("z_index", sa.Integer(), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("minimized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("config_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "scope_type in ('global', 'campaign', 'scene')",
            name="ck_workspace_widgets_scope_type",
        ),
    )
    op.create_index(
        "ix_workspace_widgets_scope_order",
        "workspace_widgets",
        ["scope_type", "scope_id", "z_index", "title", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_widgets_scope_order", table_name="workspace_widgets")
    op.drop_table("workspace_widgets")
