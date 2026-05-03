from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AppMeta(Base):
    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(nullable=False)
    starts_at: Mapped[str | None] = mapped_column()
    ended_at: Mapped[str | None] = mapped_column()
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class SceneContext(Base):
    __tablename__ = "scene_contexts"
    __table_args__ = (
        CheckConstraint(
            "staged_display_mode in ('none', 'blackout', 'intermission', 'scene_title', 'active_map', 'initiative', 'public_snippet')",
            name="ck_scene_contexts_staged_display_mode",
        ),
        Index("uq_scene_contexts_scene_id", "scene_id", unique=True),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_id: Mapped[str] = mapped_column(
        ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    active_encounter_id: Mapped[str | None] = mapped_column(
        ForeignKey("combat_encounters.id", ondelete="SET NULL"), index=True
    )
    staged_display_mode: Mapped[str] = mapped_column(default="none", nullable=False)
    staged_public_snippet_id: Mapped[str | None] = mapped_column(
        ForeignKey("public_snippets.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class SceneEntityLink(Base):
    __tablename__ = "scene_entity_links"
    __table_args__ = (
        CheckConstraint(
            "role in ('featured', 'supporting', 'location', 'clue', 'threat', 'other')",
            name="ck_scene_entity_links_role",
        ),
        Index("uq_scene_entity_links_scene_entity", "scene_id", "entity_id", unique=True),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_id: Mapped[str] = mapped_column(
        ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[str] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(default="supporting", nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class ScenePublicSnippetLink(Base):
    __tablename__ = "scene_public_snippet_links"
    __table_args__ = (
        Index("uq_scene_public_snippet_links_scene_snippet", "scene_id", "public_snippet_id", unique=True),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_id: Mapped[str] = mapped_column(
        ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    public_snippet_id: Mapped[str] = mapped_column(
        ForeignKey("public_snippets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class DisplayState(Base):
    __tablename__ = "display_states"

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_id: Mapped[str | None] = mapped_column(
        ForeignKey("scenes.id", ondelete="SET NULL"), index=True
    )
    mode: Mapped[str] = mapped_column(nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint(
            "kind in ('map_image', 'handout_image', 'npc_portrait', 'item_image', 'scene_image', 'token_image', 'audio', 'markdown', 'pdf', 'other')",
            name="ck_assets_kind",
        ),
        CheckConstraint(
            "visibility in ('private', 'public_displayable')",
            name="ck_assets_visibility",
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(nullable=False)
    visibility: Mapped[str] = mapped_column(default="private", nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    mime_type: Mapped[str] = mapped_column(nullable=False)
    byte_size: Mapped[int] = mapped_column(nullable=False)
    checksum: Mapped[str] = mapped_column(nullable=False)
    relative_path: Mapped[str] = mapped_column(nullable=False)
    original_filename: Mapped[str | None] = mapped_column()
    width: Mapped[int | None] = mapped_column()
    height: Mapped[int | None] = mapped_column()
    duration_ms: Mapped[int | None] = mapped_column()
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class AppRuntime(Base):
    __tablename__ = "app_runtime"
    __table_args__ = (CheckConstraint("id = 'runtime'", name="ck_app_runtime_singleton"),)

    id: Mapped[str] = mapped_column(primary_key=True)
    active_campaign_id: Mapped[str | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL")
    )
    active_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL")
    )
    active_scene_id: Mapped[str | None] = mapped_column(
        ForeignKey("scenes.id", ondelete="SET NULL")
    )
    updated_at: Mapped[str] = mapped_column(nullable=False)


class CampaignMap(Base):
    __tablename__ = "maps"
    __table_args__ = (
        CheckConstraint("width > 0", name="ck_maps_width_positive"),
        CheckConstraint("height > 0", name="ck_maps_height_positive"),
        CheckConstraint("grid_size_px >= 4 AND grid_size_px <= 500", name="ck_maps_grid_size"),
        CheckConstraint("grid_opacity >= 0 AND grid_opacity <= 1", name="ck_maps_grid_opacity"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(nullable=False)
    width: Mapped[int] = mapped_column(nullable=False)
    height: Mapped[int] = mapped_column(nullable=False)
    grid_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    grid_size_px: Mapped[int] = mapped_column(default=70, nullable=False)
    grid_offset_x: Mapped[float] = mapped_column(default=0, nullable=False)
    grid_offset_y: Mapped[float] = mapped_column(default=0, nullable=False)
    grid_color: Mapped[str] = mapped_column(default="#FFFFFF", nullable=False)
    grid_opacity: Mapped[float] = mapped_column(default=0.35, nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class SceneMap(Base):
    __tablename__ = "scene_maps"
    __table_args__ = (
        CheckConstraint(
            "player_fit_mode in ('fit', 'fill', 'stretch', 'actual_size')",
            name="ck_scene_maps_player_fit_mode",
        ),
        Index(
            "uq_scene_maps_one_active_per_scene",
            "scene_id",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_id: Mapped[str] = mapped_column(
        ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    map_id: Mapped[str] = mapped_column(
        ForeignKey("maps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)
    player_fit_mode: Mapped[str] = mapped_column(default="fit", nullable=False)
    player_grid_visible: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class SceneMapFogMask(Base):
    __tablename__ = "scene_map_fog_masks"
    __table_args__ = (
        CheckConstraint("width > 0", name="ck_scene_map_fog_masks_width_positive"),
        CheckConstraint("height > 0", name="ck_scene_map_fog_masks_height_positive"),
        CheckConstraint("revision >= 1", name="ck_scene_map_fog_masks_revision_positive"),
        Index("uq_scene_map_fog_masks_scene_map_id", "scene_map_id", unique=True),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_id: Mapped[str] = mapped_column(
        ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_map_id: Mapped[str] = mapped_column(
        ForeignKey("scene_maps.id", ondelete="CASCADE"), nullable=False
    )
    width: Mapped[int] = mapped_column(nullable=False)
    height: Mapped[int] = mapped_column(nullable=False)
    relative_path: Mapped[str] = mapped_column(nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    revision: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class SceneMapToken(Base):
    __tablename__ = "scene_map_tokens"
    __table_args__ = (
        CheckConstraint(
            "visibility in ('gm_only', 'player_visible', 'hidden_until_revealed')",
            name="ck_scene_map_tokens_visibility",
        ),
        CheckConstraint(
            "label_visibility in ('gm_only', 'player_visible', 'hidden')",
            name="ck_scene_map_tokens_label_visibility",
        ),
        CheckConstraint(
            "shape in ('circle', 'square', 'portrait', 'marker')",
            name="ck_scene_map_tokens_shape",
        ),
        CheckConstraint("width > 0 AND width <= 1000", name="ck_scene_map_tokens_width"),
        CheckConstraint("height > 0 AND height <= 1000", name="ck_scene_map_tokens_height"),
        CheckConstraint("rotation >= 0 AND rotation < 360", name="ck_scene_map_tokens_rotation"),
        CheckConstraint("opacity >= 0 AND opacity <= 1", name="ck_scene_map_tokens_opacity"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_id: Mapped[str] = mapped_column(
        ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_map_id: Mapped[str] = mapped_column(
        ForeignKey("scene_maps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[str | None] = mapped_column()
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(nullable=False)
    x: Mapped[float] = mapped_column(nullable=False)
    y: Mapped[float] = mapped_column(nullable=False)
    width: Mapped[float] = mapped_column(nullable=False)
    height: Mapped[float] = mapped_column(nullable=False)
    rotation: Mapped[float] = mapped_column(default=0, nullable=False)
    z_index: Mapped[int] = mapped_column(default=0, nullable=False)
    visibility: Mapped[str] = mapped_column(default="gm_only", nullable=False)
    label_visibility: Mapped[str] = mapped_column(default="gm_only", nullable=False)
    shape: Mapped[str] = mapped_column(default="circle", nullable=False)
    color: Mapped[str] = mapped_column(default="#D94841", nullable=False)
    border_color: Mapped[str] = mapped_column(default="#FFFFFF", nullable=False)
    opacity: Mapped[float] = mapped_column(default=1, nullable=False)
    status_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        CheckConstraint(
            "kind in ('pc', 'npc', 'creature', 'location', 'item', 'handout', 'faction', 'vehicle', 'generic')",
            name="ck_entities_kind",
        ),
        CheckConstraint("visibility in ('private', 'public_known')", name="ck_entities_visibility"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    display_name: Mapped[str | None] = mapped_column()
    visibility: Mapped[str] = mapped_column(default="private", nullable=False)
    portrait_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), index=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class CustomFieldDefinition(Base):
    __tablename__ = "custom_field_definitions"
    __table_args__ = (
        CheckConstraint(
            "field_type in ('short_text', 'long_text', 'number', 'boolean', 'select', 'multi_select', 'radio', 'resource', 'image')",
            name="ck_custom_field_definitions_field_type",
        ),
        Index("uq_custom_field_definitions_campaign_key", "campaign_id", "key", unique=True),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(nullable=False)
    label: Mapped[str] = mapped_column(nullable=False)
    field_type: Mapped[str] = mapped_column(nullable=False)
    applies_to_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    required: Mapped[bool] = mapped_column(default=False, nullable=False)
    default_value_json: Mapped[str | None] = mapped_column(Text)
    options_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    public_by_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class CustomFieldValue(Base):
    __tablename__ = "custom_field_values"
    __table_args__ = (
        Index("uq_custom_field_values_entity_field", "entity_id", "field_definition_id", unique=True),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    field_definition_id: Mapped[str] = mapped_column(
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class PartyTrackerConfig(Base):
    __tablename__ = "party_tracker_configs"
    __table_args__ = (
        CheckConstraint("layout in ('compact', 'standard', 'wide')", name="ck_party_tracker_configs_layout"),
        Index("uq_party_tracker_configs_campaign_id", "campaign_id", unique=True),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    layout: Mapped[str] = mapped_column(default="standard", nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class PartyTrackerMember(Base):
    __tablename__ = "party_tracker_members"
    __table_args__ = (
        Index("uq_party_tracker_members_config_entity", "config_id", "entity_id", unique=True),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    config_id: Mapped[str] = mapped_column(ForeignKey("party_tracker_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class PartyTrackerField(Base):
    __tablename__ = "party_tracker_fields"
    __table_args__ = (
        Index("uq_party_tracker_fields_config_field", "config_id", "field_definition_id", unique=True),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    config_id: Mapped[str] = mapped_column(ForeignKey("party_tracker_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_definition_id: Mapped[str] = mapped_column(
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    public_visible: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class CombatEncounter(Base):
    __tablename__ = "combat_encounters"
    __table_args__ = (
        CheckConstraint("status in ('active', 'paused', 'ended')", name="ck_combat_encounters_status"),
        CheckConstraint("round >= 1", name="ck_combat_encounters_round"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"), index=True)
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default="active", nullable=False)
    round: Mapped[int] = mapped_column(default=1, nullable=False)
    active_combatant_id: Mapped[str | None] = mapped_column(index=True)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class Combatant(Base):
    __tablename__ = "combatants"
    __table_args__ = (
        CheckConstraint(
            "disposition in ('pc', 'ally', 'neutral', 'enemy', 'hazard', 'other')",
            name="ck_combatants_disposition",
        ),
        CheckConstraint("initiative IS NULL OR (initiative >= -100 AND initiative <= 100)", name="ck_combatants_initiative"),
        CheckConstraint("order_index >= 0", name="ck_combatants_order_index"),
        CheckConstraint("armor_class IS NULL OR (armor_class >= 0 AND armor_class <= 100)", name="ck_combatants_armor_class"),
        CheckConstraint("hp_current IS NULL OR (hp_current >= -1000 AND hp_current <= 10000)", name="ck_combatants_hp_current"),
        CheckConstraint("hp_max IS NULL OR (hp_max >= 0 AND hp_max <= 10000)", name="ck_combatants_hp_max"),
        CheckConstraint("hp_temp >= 0 AND hp_temp <= 10000", name="ck_combatants_hp_temp"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    encounter_id: Mapped[str] = mapped_column(ForeignKey("combat_encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id", ondelete="SET NULL"), index=True)
    token_id: Mapped[str | None] = mapped_column(ForeignKey("scene_map_tokens.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(nullable=False)
    disposition: Mapped[str] = mapped_column(default="enemy", nullable=False)
    initiative: Mapped[float | None] = mapped_column()
    order_index: Mapped[int] = mapped_column(default=0, nullable=False)
    armor_class: Mapped[int | None] = mapped_column()
    hp_current: Mapped[int | None] = mapped_column()
    hp_max: Mapped[int | None] = mapped_column()
    hp_temp: Mapped[int] = mapped_column(default=0, nullable=False)
    conditions_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    public_status_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    public_visible: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_defeated: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class NoteSource(Base):
    __tablename__ = "note_sources"
    __table_args__ = (
        CheckConstraint("kind in ('internal', 'imported_markdown')", name="ck_note_sources_kind"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    readonly: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str | None] = mapped_column(ForeignKey("note_sources.id", ondelete="SET NULL"), index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"), index=True)
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"), index=True)
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(nullable=False)
    private_body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    source_label: Mapped[str | None] = mapped_column()
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class PublicSnippet(Base):
    __tablename__ = "public_snippets"
    __table_args__ = (
        CheckConstraint("format in ('markdown')", name="ck_public_snippets_format"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    note_id: Mapped[str | None] = mapped_column(ForeignKey("notes.id", ondelete="SET NULL"), index=True)
    title: Mapped[str | None] = mapped_column()
    body: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(default="markdown", nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class SessionOrderCounter(Base):
    __tablename__ = "session_order_counters"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    next_order_index: Mapped[int] = mapped_column(default=0, nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class SessionTranscriptEvent(Base):
    __tablename__ = "session_transcript_events"
    __table_args__ = (
        CheckConstraint(
            "event_type in ('live_dm_note', 'correction')",
            name="ck_session_transcript_events_event_type",
        ),
        CheckConstraint("order_index >= 0", name="ck_session_transcript_events_order_index"),
        UniqueConstraint("session_id", "order_index", name="uq_session_transcript_events_session_order"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"), index=True)
    corrects_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("session_transcript_events.id", ondelete="SET NULL"), index=True
    )
    event_type: Mapped[str] = mapped_column(default="live_dm_note", nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(default="typed", nullable=False)
    public_safe: Mapped[bool] = mapped_column(default=False, nullable=False)
    order_index: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class LlmProviderProfile(Base):
    __tablename__ = "llm_provider_profiles"
    __table_args__ = (
        CheckConstraint(
            "vendor in ('openai', 'ollama', 'lmstudio', 'kobold', 'openrouter', 'custom')",
            name="ck_llm_provider_profiles_vendor",
        ),
        CheckConstraint(
            "key_source_type in ('none', 'env')",
            name="ck_llm_provider_profiles_key_source_type",
        ),
        CheckConstraint(
            "conformance_level in ('unverified', 'level_0_text_only', 'level_1_json_best_effort', 'level_2_json_validated', 'level_3_tool_capable')",
            name="ck_llm_provider_profiles_conformance_level",
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(nullable=False)
    vendor: Mapped[str] = mapped_column(default="custom", nullable=False)
    base_url: Mapped[str] = mapped_column(nullable=False)
    model_id: Mapped[str] = mapped_column(nullable=False)
    key_source_type: Mapped[str] = mapped_column(default="none", nullable=False)
    key_source_ref: Mapped[str | None] = mapped_column()
    conformance_level: Mapped[str] = mapped_column(default="unverified", nullable=False)
    capabilities_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    last_probe_result_json: Mapped[str | None] = mapped_column(Text)
    probed_at: Mapped[str | None] = mapped_column()
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class LlmContextPackage(Base):
    __tablename__ = "llm_context_packages"
    __table_args__ = (
        CheckConstraint(
            "visibility_mode in ('gm_private', 'public_safe')",
            name="ck_llm_context_packages_visibility_mode",
        ),
        CheckConstraint(
            "review_status in ('unreviewed', 'reviewed')",
            name="ck_llm_context_packages_review_status",
        ),
        CheckConstraint(
            "scope_kind in ('campaign', 'session', 'scene')",
            name="ck_llm_context_packages_scope_kind",
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"), index=True)
    task_kind: Mapped[str] = mapped_column(nullable=False)
    scope_kind: Mapped[str] = mapped_column(default="session", nullable=False)
    visibility_mode: Mapped[str] = mapped_column(default="gm_private", nullable=False)
    gm_instruction: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_refs_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    rendered_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref_hash: Mapped[str] = mapped_column(nullable=False, index=True)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    review_status: Mapped[str] = mapped_column(default="unreviewed", nullable=False)
    reviewed_at: Mapped[str | None] = mapped_column()
    reviewed_by: Mapped[str | None] = mapped_column()
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class LlmRun(Base):
    __tablename__ = "llm_runs"
    __table_args__ = (
        CheckConstraint(
            "status in ('running', 'succeeded', 'failed', 'canceled')",
            name="ck_llm_runs_status",
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"), index=True)
    provider_profile_id: Mapped[str | None] = mapped_column(ForeignKey("llm_provider_profiles.id", ondelete="SET NULL"), index=True)
    context_package_id: Mapped[str | None] = mapped_column(ForeignKey("llm_context_packages.id", ondelete="SET NULL"), index=True)
    parent_run_id: Mapped[str | None] = mapped_column(ForeignKey("llm_runs.id", ondelete="SET NULL"), index=True)
    task_kind: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default="running", nullable=False)
    error_code: Mapped[str | None] = mapped_column()
    error_message: Mapped[str | None] = mapped_column(Text)
    parse_failure_reason: Mapped[str | None] = mapped_column()
    repair_attempted: Mapped[bool] = mapped_column(default=False, nullable=False)
    request_metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    request_json: Mapped[str | None] = mapped_column(Text)
    response_text: Mapped[str | None] = mapped_column(Text)
    normalized_output_json: Mapped[str | None] = mapped_column(Text)
    prompt_tokens_estimate: Mapped[int | None] = mapped_column()
    duration_ms: Mapped[int | None] = mapped_column()
    cancel_requested_at: Mapped[str | None] = mapped_column()
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class SessionRecap(Base):
    __tablename__ = "session_recaps"

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    source_llm_run_id: Mapped[str | None] = mapped_column(ForeignKey("llm_runs.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class MemoryCandidate(Base):
    __tablename__ = "memory_candidates"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft', 'edited', 'accepted', 'rejected')",
            name="ck_memory_candidates_status",
        ),
        CheckConstraint(
            "claim_strength in ('directly_evidenced', 'strong_inference', 'weak_inference', 'gm_review_required')",
            name="ck_memory_candidates_claim_strength",
        ),
        Index("uq_memory_candidates_applied_entry", "applied_memory_entry_id", unique=True, sqlite_where=text("applied_memory_entry_id IS NOT NULL")),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"), index=True)
    source_llm_run_id: Mapped[str | None] = mapped_column(ForeignKey("llm_runs.id", ondelete="SET NULL"), index=True)
    source_recap_id: Mapped[str | None] = mapped_column(ForeignKey("session_recaps.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(default="draft", nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    claim_strength: Mapped[str] = mapped_column(nullable=False)
    evidence_refs_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    validation_errors_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    edited_from_candidate_id: Mapped[str | None] = mapped_column(ForeignKey("memory_candidates.id", ondelete="SET NULL"), index=True)
    applied_memory_entry_id: Mapped[str | None] = mapped_column(ForeignKey("campaign_memory_entries.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class CampaignMemoryEntry(Base):
    __tablename__ = "campaign_memory_entries"

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"), index=True)
    source_candidate_id: Mapped[str | None] = mapped_column(ForeignKey("memory_candidates.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (
        CheckConstraint(
            "source in ('manual', 'observed', 'generated_pending_approval')",
            name="ck_entity_aliases_source",
        ),
        CheckConstraint(
            "confidence in ('gm_confirmed', 'observed', 'generated_pending_approval')",
            name="ck_entity_aliases_confidence",
        ),
        UniqueConstraint("campaign_id", "alias_text", name="uq_entity_aliases_campaign_alias"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    alias_text: Mapped[str] = mapped_column(nullable=False)
    normalized_alias: Mapped[str] = mapped_column(nullable=False, index=True)
    language: Mapped[str | None] = mapped_column()
    source: Mapped[str] = mapped_column(default="manual", nullable=False)
    source_ref_json: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(default="gm_confirmed", nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class ScribeSearchIndex(Base):
    __tablename__ = "scribe_search_index"
    __table_args__ = (
        UniqueConstraint("source_kind", "source_id", "source_revision", name="uq_scribe_search_source_revision"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_kind: Mapped[str] = mapped_column(nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(nullable=False, index=True)
    source_revision: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    lane: Mapped[str] = mapped_column(default="canon", nullable=False)
    visibility: Mapped[str] = mapped_column(default="gm_private", nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class ProposalSet(Base):
    __tablename__ = "proposal_sets"
    __table_args__ = (
        CheckConstraint(
            "scope_kind in ('campaign', 'session', 'scene')",
            name="ck_proposal_sets_scope_kind",
        ),
        CheckConstraint(
            "status in ('proposed', 'partially_used', 'rejected', 'superseded')",
            name="ck_proposal_sets_status",
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"), index=True)
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"), index=True)
    llm_run_id: Mapped[str | None] = mapped_column(ForeignKey("llm_runs.id", ondelete="SET NULL"), index=True)
    context_package_id: Mapped[str | None] = mapped_column(ForeignKey("llm_context_packages.id", ondelete="SET NULL"), index=True)
    task_kind: Mapped[str] = mapped_column(nullable=False)
    scope_kind: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default="proposed", nullable=False)
    normalization_warnings_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class ProposalOption(Base):
    __tablename__ = "proposal_options"
    __table_args__ = (
        CheckConstraint(
            "status in ('proposed', 'selected', 'rejected', 'saved_for_later', 'superseded', 'canonized')",
            name="ck_proposal_options_status",
        ),
        UniqueConstraint("proposal_set_id", "stable_option_key", name="uq_proposal_options_set_key"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    proposal_set_id: Mapped[str] = mapped_column(ForeignKey("proposal_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    stable_option_key: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    consequences: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reveals: Mapped[str] = mapped_column(Text, default="", nullable=False)
    stays_hidden: Mapped[str] = mapped_column(Text, default="", nullable=False)
    proposed_delta_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    planning_marker_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(default="proposed", nullable=False)
    selected_at: Mapped[str | None] = mapped_column()
    canonized_at: Mapped[str | None] = mapped_column()
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class PlanningMarker(Base):
    __tablename__ = "planning_markers"
    __table_args__ = (
        CheckConstraint(
            "scope_kind in ('campaign', 'session', 'scene')",
            name="ck_planning_markers_scope_kind",
        ),
        CheckConstraint(
            "status in ('active', 'expired', 'superseded', 'canonized', 'discarded')",
            name="ck_planning_markers_status",
        ),
        Index("uq_planning_markers_source_option", "source_proposal_option_id", unique=True, sqlite_where=text("source_proposal_option_id IS NOT NULL")),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id", ondelete="SET NULL"), index=True)
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"), index=True)
    source_proposal_option_id: Mapped[str | None] = mapped_column(ForeignKey("proposal_options.id", ondelete="SET NULL"), index=True)
    scope_kind: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default="active", nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    marker_text: Mapped[str] = mapped_column(Text, nullable=False)
    original_marker_text: Mapped[str | None] = mapped_column(Text)
    lint_warnings_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    provenance_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    edited_at: Mapped[str | None] = mapped_column()
    edited_from_source: Mapped[bool] = mapped_column(default=False, nullable=False)
    expires_at: Mapped[str | None] = mapped_column()
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class WorkspaceWidget(Base):
    __tablename__ = "workspace_widgets"
    __table_args__ = (
        CheckConstraint(
            "scope_type in ('global', 'campaign', 'scene')",
            name="ck_workspace_widgets_scope_type",
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    scope_type: Mapped[str] = mapped_column(default="global", nullable=False)
    scope_id: Mapped[str | None] = mapped_column()
    kind: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    x: Mapped[int] = mapped_column(nullable=False)
    y: Mapped[int] = mapped_column(nullable=False)
    width: Mapped[int] = mapped_column(nullable=False)
    height: Mapped[int] = mapped_column(nullable=False)
    z_index: Mapped[int] = mapped_column(nullable=False)
    locked: Mapped[bool] = mapped_column(default=False, nullable=False)
    minimized: Mapped[bool] = mapped_column(default=False, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class PlayerDisplayRuntime(Base):
    __tablename__ = "player_display_runtime"
    __table_args__ = (
        CheckConstraint("id = 'player_display'", name="ck_player_display_runtime_singleton"),
        CheckConstraint(
            "mode in ('blackout', 'intermission', 'scene_title', 'image', 'map', 'text', 'party', 'initiative')",
            name="ck_player_display_runtime_mode",
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(nullable=False)
    active_campaign_id: Mapped[str | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"), index=True
    )
    active_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), index=True
    )
    active_scene_id: Mapped[str | None] = mapped_column(
        ForeignKey("scenes.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str | None] = mapped_column()
    subtitle: Mapped[str | None] = mapped_column()
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    revision: Mapped[int] = mapped_column(default=1, nullable=False)
    identify_revision: Mapped[int] = mapped_column(default=0, nullable=False)
    identify_until: Mapped[str | None] = mapped_column()
    updated_at: Mapped[str] = mapped_column(nullable=False)
