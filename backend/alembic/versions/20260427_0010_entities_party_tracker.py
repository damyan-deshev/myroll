"""entities party tracker

Revision ID: 20260427_0010
Revises: 20260427_0009
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0010"
down_revision = "20260427_0009"
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
        "entities",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("visibility", sa.String(), nullable=False, server_default="private"),
        sa.Column("portrait_asset_id", sa.String(), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "kind in ('pc', 'npc', 'creature', 'location', 'item', 'handout', 'faction', 'vehicle', 'generic')",
            name="ck_entities_kind",
        ),
        sa.CheckConstraint("visibility in ('private', 'public_known')", name="ck_entities_visibility"),
    )
    op.create_index("ix_entities_campaign_id", "entities", ["campaign_id"])
    op.create_index("ix_entities_portrait_asset_id", "entities", ["portrait_asset_id"])

    op.create_table(
        "custom_field_definitions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("field_type", sa.String(), nullable=False),
        sa.Column("applies_to_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_value_json", sa.Text(), nullable=True),
        sa.Column("options_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("public_by_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "field_type in ('short_text', 'long_text', 'number', 'boolean', 'select', 'multi_select', 'radio', 'resource', 'image')",
            name="ck_custom_field_definitions_field_type",
        ),
    )
    op.create_index("ix_custom_field_definitions_campaign_id", "custom_field_definitions", ["campaign_id"])
    op.create_index(
        "uq_custom_field_definitions_campaign_key",
        "custom_field_definitions",
        ["campaign_id", "key"],
        unique=True,
    )

    op.create_table(
        "custom_field_values",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_definition_id", sa.String(), sa.ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("ix_custom_field_values_campaign_id", "custom_field_values", ["campaign_id"])
    op.create_index("ix_custom_field_values_entity_id", "custom_field_values", ["entity_id"])
    op.create_index("ix_custom_field_values_field_definition_id", "custom_field_values", ["field_definition_id"])
    op.create_index(
        "uq_custom_field_values_entity_field",
        "custom_field_values",
        ["entity_id", "field_definition_id"],
        unique=True,
    )

    op.create_table(
        "party_tracker_configs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("layout", sa.String(), nullable=False, server_default="standard"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("layout in ('compact', 'standard', 'wide')", name="ck_party_tracker_configs_layout"),
    )
    op.create_index("ix_party_tracker_configs_campaign_id", "party_tracker_configs", ["campaign_id"])
    op.create_index("uq_party_tracker_configs_campaign_id", "party_tracker_configs", ["campaign_id"], unique=True)

    op.create_table(
        "party_tracker_members",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("config_id", sa.String(), sa.ForeignKey("party_tracker_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("ix_party_tracker_members_config_id", "party_tracker_members", ["config_id"])
    op.create_index("ix_party_tracker_members_campaign_id", "party_tracker_members", ["campaign_id"])
    op.create_index("ix_party_tracker_members_entity_id", "party_tracker_members", ["entity_id"])
    op.create_index("uq_party_tracker_members_config_entity", "party_tracker_members", ["config_id", "entity_id"], unique=True)

    op.create_table(
        "party_tracker_fields",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("config_id", sa.String(), sa.ForeignKey("party_tracker_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_definition_id", sa.String(), sa.ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("public_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("ix_party_tracker_fields_config_id", "party_tracker_fields", ["config_id"])
    op.create_index("ix_party_tracker_fields_campaign_id", "party_tracker_fields", ["campaign_id"])
    op.create_index("ix_party_tracker_fields_field_definition_id", "party_tracker_fields", ["field_definition_id"])
    op.create_index(
        "uq_party_tracker_fields_config_field",
        "party_tracker_fields",
        ["config_id", "field_definition_id"],
        unique=True,
    )

    _rebuild_player_display_runtime("mode in ('blackout', 'intermission', 'scene_title', 'image', 'map', 'text', 'party')")


def downgrade() -> None:
    op.execute(
        """
        UPDATE player_display_runtime
        SET mode = 'blackout',
            title = NULL,
            subtitle = NULL,
            payload_json = '{}'
        WHERE mode = 'party'
        """
    )
    _rebuild_player_display_runtime("mode in ('blackout', 'intermission', 'scene_title', 'image', 'map', 'text')")
    op.drop_index("uq_party_tracker_fields_config_field", table_name="party_tracker_fields")
    op.drop_index("ix_party_tracker_fields_field_definition_id", table_name="party_tracker_fields")
    op.drop_index("ix_party_tracker_fields_campaign_id", table_name="party_tracker_fields")
    op.drop_index("ix_party_tracker_fields_config_id", table_name="party_tracker_fields")
    op.drop_table("party_tracker_fields")
    op.drop_index("uq_party_tracker_members_config_entity", table_name="party_tracker_members")
    op.drop_index("ix_party_tracker_members_entity_id", table_name="party_tracker_members")
    op.drop_index("ix_party_tracker_members_campaign_id", table_name="party_tracker_members")
    op.drop_index("ix_party_tracker_members_config_id", table_name="party_tracker_members")
    op.drop_table("party_tracker_members")
    op.drop_index("uq_party_tracker_configs_campaign_id", table_name="party_tracker_configs")
    op.drop_index("ix_party_tracker_configs_campaign_id", table_name="party_tracker_configs")
    op.drop_table("party_tracker_configs")
    op.drop_index("uq_custom_field_values_entity_field", table_name="custom_field_values")
    op.drop_index("ix_custom_field_values_field_definition_id", table_name="custom_field_values")
    op.drop_index("ix_custom_field_values_entity_id", table_name="custom_field_values")
    op.drop_index("ix_custom_field_values_campaign_id", table_name="custom_field_values")
    op.drop_table("custom_field_values")
    op.drop_index("uq_custom_field_definitions_campaign_key", table_name="custom_field_definitions")
    op.drop_index("ix_custom_field_definitions_campaign_id", table_name="custom_field_definitions")
    op.drop_table("custom_field_definitions")
    op.drop_index("ix_entities_portrait_asset_id", table_name="entities")
    op.drop_index("ix_entities_campaign_id", table_name="entities")
    op.drop_table("entities")
