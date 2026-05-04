"""add stable proposal option order

Revision ID: 20260504_0018
Revises: 20260504_0017
Create Date: 2026-05-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260504_0018"
down_revision = "20260504_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("proposal_options") as batch_op:
        batch_op.add_column(sa.Column("option_index", sa.Integer(), nullable=False, server_default="0"))
    op.execute(
        """
        UPDATE proposal_options
        SET option_index = (
            SELECT count(*) - 1
            FROM proposal_options AS prior
            WHERE prior.proposal_set_id = proposal_options.proposal_set_id
              AND prior.rowid <= proposal_options.rowid
        )
        """
    )
    op.create_index("uq_proposal_options_set_index", "proposal_options", ["proposal_set_id", "option_index"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_proposal_options_set_index", table_name="proposal_options")
    with op.batch_alter_table("proposal_options") as batch_op:
        batch_op.drop_column("option_index")
