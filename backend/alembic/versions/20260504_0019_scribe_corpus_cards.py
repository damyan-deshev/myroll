"""scribe corpus cards and FTS recall

Revision ID: 20260504_0019
Revises: 20260504_0018
Create Date: 2026-05-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260504_0019"
down_revision = "20260504_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("notes") as batch_op:
        batch_op.add_column(sa.Column("recall_status", sa.String(), nullable=False, server_default="private_prep"))
        batch_op.create_check_constraint(
            "ck_notes_recall_status",
            "recall_status in ('private_prep', 'scoped_recall_eligible', 'archived')",
        )

    op.create_table(
        "scribe_corpus_cards",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_kind", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("source_revision", sa.String(), nullable=False),
        sa.Column("card_variant", sa.String(), nullable=False, server_default="default"),
        sa.Column("source_hash", sa.String(), nullable=False),
        sa.Column("lane", sa.String(), nullable=False),
        sa.Column("visibility", sa.String(), nullable=False),
        sa.Column("review_status", sa.String(), nullable=False),
        sa.Column("source_status", sa.String(), nullable=False, server_default="active"),
        sa.Column("claim_role", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("happened_at", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("searchable_text", sa.Text(), nullable=False),
        sa.Column("entity_refs_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("alias_refs_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("provenance_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "card_variant in ('default', 'public_projection', 'entity_shell', 'debug_metadata')",
            name="ck_scribe_corpus_cards_card_variant",
        ),
        sa.CheckConstraint(
            "lane in ('canon', 'reviewed', 'played_evidence', 'gm_note', 'planning', 'public', 'debug_history')",
            name="ck_scribe_corpus_cards_lane",
        ),
        sa.CheckConstraint(
            "visibility in ('gm_private', 'public_safe', 'player_display')",
            name="ck_scribe_corpus_cards_visibility",
        ),
        sa.CheckConstraint(
            "review_status in ('raw', 'reviewed', 'accepted', 'planning_only', 'public_artifact', 'debug_only')",
            name="ck_scribe_corpus_cards_review_status",
        ),
        sa.CheckConstraint(
            "claim_role in ('canon_claim', 'reviewed_summary', 'source_evidence', 'planning_intent', 'public_artifact', 'entity_shell', 'debug_metadata')",
            name="ck_scribe_corpus_cards_claim_role",
        ),
        sa.UniqueConstraint(
            "campaign_id",
            "source_kind",
            "source_id",
            "source_revision",
            "card_variant",
            name="uq_scribe_corpus_cards_source_projection",
        ),
    )
    op.create_index("ix_scribe_corpus_cards_campaign_id", "scribe_corpus_cards", ["campaign_id"])
    op.create_index("ix_scribe_corpus_cards_source_kind", "scribe_corpus_cards", ["source_kind"])
    op.create_index("ix_scribe_corpus_cards_source_id", "scribe_corpus_cards", ["source_id"])
    op.create_index("ix_scribe_corpus_cards_source_hash", "scribe_corpus_cards", ["source_hash"])
    op.create_index("ix_scribe_corpus_cards_lane", "scribe_corpus_cards", ["lane"])
    op.create_index("ix_scribe_corpus_cards_visibility", "scribe_corpus_cards", ["visibility"])
    op.create_index("ix_scribe_corpus_cards_session_id", "scribe_corpus_cards", ["session_id"])
    op.create_index("ix_scribe_corpus_cards_scene_id", "scribe_corpus_cards", ["scene_id"])
    op.create_index("ix_scribe_corpus_cards_happened_at", "scribe_corpus_cards", ["happened_at"])

    op.execute(
        """
        CREATE VIRTUAL TABLE scribe_corpus_cards_fts USING fts5(
            card_id UNINDEXED,
            campaign_id UNINDEXED,
            title,
            excerpt,
            searchable_text,
            tokenize = 'unicode61 remove_diacritics 2'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS scribe_corpus_cards_fts")
    op.drop_index("ix_scribe_corpus_cards_happened_at", table_name="scribe_corpus_cards")
    op.drop_index("ix_scribe_corpus_cards_scene_id", table_name="scribe_corpus_cards")
    op.drop_index("ix_scribe_corpus_cards_session_id", table_name="scribe_corpus_cards")
    op.drop_index("ix_scribe_corpus_cards_visibility", table_name="scribe_corpus_cards")
    op.drop_index("ix_scribe_corpus_cards_lane", table_name="scribe_corpus_cards")
    op.drop_index("ix_scribe_corpus_cards_source_hash", table_name="scribe_corpus_cards")
    op.drop_index("ix_scribe_corpus_cards_source_id", table_name="scribe_corpus_cards")
    op.drop_index("ix_scribe_corpus_cards_source_kind", table_name="scribe_corpus_cards")
    op.drop_index("ix_scribe_corpus_cards_campaign_id", table_name="scribe_corpus_cards")
    op.drop_table("scribe_corpus_cards")

    with op.batch_alter_table("notes") as batch_op:
        batch_op.drop_constraint("ck_notes_recall_status", type_="check")
        batch_op.drop_column("recall_status")
