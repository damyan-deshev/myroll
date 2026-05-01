"""combat tracker basics

Revision ID: 20260427_0011
Revises: 20260427_0010
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0011"
down_revision = "20260427_0010"
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
        "combat_encounters",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scene_id", sa.String(), sa.ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("round", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active_combatant_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("status in ('active', 'paused', 'ended')", name="ck_combat_encounters_status"),
        sa.CheckConstraint("round >= 1", name="ck_combat_encounters_round"),
    )
    op.create_index("ix_combat_encounters_campaign_id", "combat_encounters", ["campaign_id"])
    op.create_index("ix_combat_encounters_session_id", "combat_encounters", ["session_id"])
    op.create_index("ix_combat_encounters_scene_id", "combat_encounters", ["scene_id"])
    op.create_index("ix_combat_encounters_active_combatant_id", "combat_encounters", ["active_combatant_id"])

    op.create_table(
        "combatants",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("encounter_id", sa.String(), sa.ForeignKey("combat_encounters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("token_id", sa.String(), sa.ForeignKey("scene_map_tokens.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("disposition", sa.String(), nullable=False, server_default="enemy"),
        sa.Column("initiative", sa.Float(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("armor_class", sa.Integer(), nullable=True),
        sa.Column("hp_current", sa.Integer(), nullable=True),
        sa.Column("hp_max", sa.Integer(), nullable=True),
        sa.Column("hp_temp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conditions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("public_status_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("public_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_defeated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "disposition in ('pc', 'ally', 'neutral', 'enemy', 'hazard', 'other')",
            name="ck_combatants_disposition",
        ),
        sa.CheckConstraint("initiative IS NULL OR (initiative >= -100 AND initiative <= 100)", name="ck_combatants_initiative"),
        sa.CheckConstraint("order_index >= 0", name="ck_combatants_order_index"),
        sa.CheckConstraint("armor_class IS NULL OR (armor_class >= 0 AND armor_class <= 100)", name="ck_combatants_armor_class"),
        sa.CheckConstraint("hp_current IS NULL OR (hp_current >= -1000 AND hp_current <= 10000)", name="ck_combatants_hp_current"),
        sa.CheckConstraint("hp_max IS NULL OR (hp_max >= 0 AND hp_max <= 10000)", name="ck_combatants_hp_max"),
        sa.CheckConstraint("hp_temp >= 0 AND hp_temp <= 10000", name="ck_combatants_hp_temp"),
    )
    op.create_index("ix_combatants_campaign_id", "combatants", ["campaign_id"])
    op.create_index("ix_combatants_encounter_id", "combatants", ["encounter_id"])
    op.create_index("ix_combatants_entity_id", "combatants", ["entity_id"])
    op.create_index("ix_combatants_token_id", "combatants", ["token_id"])

    _rebuild_player_display_runtime("mode in ('blackout', 'intermission', 'scene_title', 'image', 'map', 'text', 'party', 'initiative')")


def downgrade() -> None:
    op.execute(
        """
        UPDATE player_display_runtime
        SET mode = 'blackout',
            title = NULL,
            subtitle = NULL,
            payload_json = '{}'
        WHERE mode = 'initiative'
        """
    )
    _rebuild_player_display_runtime("mode in ('blackout', 'intermission', 'scene_title', 'image', 'map', 'text', 'party')")
    op.drop_index("ix_combatants_token_id", table_name="combatants")
    op.drop_index("ix_combatants_entity_id", table_name="combatants")
    op.drop_index("ix_combatants_encounter_id", table_name="combatants")
    op.drop_index("ix_combatants_campaign_id", table_name="combatants")
    op.drop_table("combatants")
    op.drop_index("ix_combat_encounters_active_combatant_id", table_name="combat_encounters")
    op.drop_index("ix_combat_encounters_scene_id", table_name="combat_encounters")
    op.drop_index("ix_combat_encounters_session_id", table_name="combat_encounters")
    op.drop_index("ix_combat_encounters_campaign_id", table_name="combat_encounters")
    op.drop_table("combat_encounters")
