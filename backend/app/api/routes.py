from __future__ import annotations

import uuid
import json
import math
import re
from datetime import timedelta
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from backend.app.api.errors import api_error
from backend.app.asset_store import AssetImportError, resolve_asset_path, store_image_path, store_image_stream
from backend.app.bundled_assets import BundledAssetPackError, BundledMap, find_bundled_map, load_bundled_packs
from backend.app.db.engine import assert_database_ok, session_for_settings
from backend.app.db.meta import get_app_meta, get_schema_version
from backend.app.db.models import (
    AppRuntime,
    Asset,
    Campaign,
    CampaignMap,
    CombatEncounter,
    Combatant,
    CustomFieldDefinition,
    CustomFieldValue,
    Entity,
    Note,
    NoteSource,
    PartyTrackerConfig,
    PartyTrackerField,
    PartyTrackerMember,
    PlayerDisplayRuntime,
    PublicSnippet,
    Scene,
    SceneContext,
    SceneEntityLink,
    SceneMap,
    SceneMapFogMask,
    SceneMapToken,
    ScenePublicSnippetLink,
    WorkspaceWidget,
)
from backend.app.db.models import Session as CampaignSession
from backend.app.db.seed import DEMO_SEED_VERSION, PLAYER_DISPLAY_ID, RUNTIME_ID, SEED_META_KEY
from backend.app.db.seed_ids import deterministic_uuid
from backend.app.fog_store import (
    FogPoint,
    FogRect,
    FogStoreError,
    apply_all,
    apply_brush,
    apply_rect,
    create_hidden_mask,
    fog_relative_path,
    load_mask,
    resolve_fog_path,
    save_mask_atomic,
)
from backend.app.storage_export import (
    StorageExportError,
    backup_database,
    create_export_archive,
    directory_size,
    iso_from_timestamp,
    latest_file,
    profile_hint,
)
from backend.app.time import to_utc_z, utc_now, utc_now_z
from backend.app.workspace_defaults import DEFAULT_WIDGET_IDS, DEFAULT_WORKSPACE_WIDGETS


router = APIRouter()

IMAGE_ASSET_KINDS = {"map_image", "handout_image", "npc_portrait", "item_image", "scene_image", "token_image"}
ASSET_VISIBILITIES = {"private", "public_displayable"}
DISPLAY_FIT_MODES = {"fit", "fill", "stretch", "actual_size"}
TOKEN_VISIBILITIES = {"gm_only", "player_visible", "hidden_until_revealed"}
LABEL_VISIBILITIES = {"gm_only", "player_visible", "hidden"}
TOKEN_SHAPES = {"circle", "square", "portrait", "marker"}
ENTITY_KINDS = {"pc", "npc", "creature", "location", "item", "handout", "faction", "vehicle", "generic"}
ENTITY_VISIBILITIES = {"private", "public_known"}
CUSTOM_FIELD_TYPES = {"short_text", "long_text", "number", "boolean", "select", "multi_select", "radio", "resource", "image"}
PARTY_LAYOUTS = {"compact", "standard", "wide"}
COMBAT_STATUSES = {"active", "paused", "ended"}
COMBAT_DISPOSITIONS = {"pc", "ally", "neutral", "enemy", "hazard", "other"}
SCENE_STAGED_DISPLAY_MODES = {"none", "blackout", "intermission", "scene_title", "active_map", "initiative", "public_snippet"}
SCENE_ENTITY_ROLES = {"featured", "supporting", "location", "clue", "threat", "other"}
NOTE_SOURCE_KINDS = {"internal", "imported_markdown"}
SNIPPET_FORMATS = {"markdown"}
MARKDOWN_IMPORT_SUFFIXES = {".md", ".markdown", ".txt"}
MAX_MARKDOWN_IMPORT_BYTES = 2 * 1024 * 1024
HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
FIELD_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _trim_required(value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value


def _trim_optional(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    created_at: str
    updated_at: str


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value: object) -> object:
        return _trim_required(value)

    @field_validator("description", mode="before")
    @classmethod
    def trim_description(cls, value: object) -> object:
        return _trim_optional(value)


class StorageArtifactOut(BaseModel):
    archive_name: str
    byte_size: int
    created_at: str
    download_url: str | None = None


class StorageStatusOut(BaseModel):
    profile: str
    db_path: str
    asset_dir: str
    backup_dir: str
    export_dir: str
    db_size_bytes: int
    asset_size_bytes: int
    latest_backup: StorageArtifactOut | None
    latest_export: StorageArtifactOut | None
    schema_version: str | None
    seed_version: str | None
    expected_seed_version: str
    private_demo_name_map_active: bool


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    campaign_id: str
    title: str
    starts_at: str | None
    ended_at: str | None
    created_at: str
    updated_at: str


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value: object) -> object:
        return _trim_required(value)


class SceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    campaign_id: str
    session_id: str | None
    title: str
    summary: str | None
    created_at: str
    updated_at: str


class SceneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    summary: str | None = Field(default=None, max_length=4000)
    session_id: UUID | None = None

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value: object) -> object:
        return _trim_required(value)

    @field_validator("summary", mode="before")
    @classmethod
    def trim_summary(cls, value: object) -> object:
        return _trim_optional(value)


class ActivateCampaignIn(BaseModel):
    campaign_id: UUID


class ActivateSessionIn(BaseModel):
    session_id: UUID


class ActivateSceneIn(BaseModel):
    scene_id: UUID


class RuntimeOut(BaseModel):
    active_campaign_id: str | None
    active_campaign_name: str | None
    active_session_id: str | None
    active_session_title: str | None
    active_scene_id: str | None
    active_scene_title: str | None
    updated_at: str


class WorkspaceWidgetOut(BaseModel):
    id: str
    scope_type: str
    scope_id: str | None
    kind: str
    title: str
    x: int
    y: int
    width: int
    height: int
    z_index: int
    locked: bool
    minimized: bool
    config: dict[str, object]
    created_at: str
    updated_at: str


class WorkspaceWidgetsOut(BaseModel):
    widgets: list[WorkspaceWidgetOut]
    updated_at: str


class WorkspaceWidgetPatch(BaseModel):
    x: int | None = Field(default=None, ge=0, le=10000)
    y: int | None = Field(default=None, ge=0, le=10000)
    width: int | None = Field(default=None, ge=220, le=2400)
    height: int | None = Field(default=None, ge=160, le=1800)
    z_index: int | None = Field(default=None, ge=0, le=100000)
    locked: bool | None = None
    minimized: bool | None = None


class ShowSceneTitleIn(BaseModel):
    scene_id: UUID | None = None


class PlayerDisplayOut(BaseModel):
    mode: str
    title: str | None
    subtitle: str | None
    active_campaign_id: str | None
    active_campaign_name: str | None
    active_session_id: str | None
    active_session_title: str | None
    active_scene_id: str | None
    active_scene_title: str | None
    payload: dict[str, object]
    revision: int
    identify_revision: int
    identify_until: str | None
    updated_at: str


class AssetOut(BaseModel):
    id: str
    campaign_id: str
    kind: str
    visibility: str
    name: str
    mime_type: str
    byte_size: int
    checksum: str
    relative_path: str
    original_filename: str | None
    width: int | None
    height: int | None
    duration_ms: int | None
    tags: list[str]
    created_at: str
    updated_at: str


class ShowImageIn(BaseModel):
    asset_id: UUID
    title: str | None = Field(default=None, max_length=160)
    caption: str | None = Field(default=None, max_length=4000)
    fit_mode: str = "fit"

    @field_validator("title", "caption", mode="before")
    @classmethod
    def trim_copy(cls, value: object) -> object:
        return _trim_optional(value)

    @field_validator("fit_mode", mode="before")
    @classmethod
    def trim_fit_mode(cls, value: object) -> object:
        return _trim_required(value)


class MapOut(BaseModel):
    id: str
    campaign_id: str
    asset_id: str
    asset_name: str | None
    asset_visibility: str | None
    asset_url: str
    name: str
    width: int
    height: int
    grid_enabled: bool
    grid_size_px: int
    grid_offset_x: float
    grid_offset_y: float
    grid_color: str
    grid_opacity: float
    created_at: str
    updated_at: str


class AssetBatchErrorOut(BaseModel):
    code: str
    message: str


class AssetBatchItemOut(BaseModel):
    filename: str
    asset: AssetOut | None = None
    map: MapOut | None = None
    error: AssetBatchErrorOut | None = None


class AssetBatchUploadOut(BaseModel):
    results: list[AssetBatchItemOut]


class BundledGridOut(BaseModel):
    cols: int
    rows: int
    feet_per_cell: int
    px_per_cell: int
    offset_x: float
    offset_y: float


class BundledPackOut(BaseModel):
    id: str
    title: str
    asset_count: int
    category_count: int
    collections: list[str]


class BundledMapOut(BaseModel):
    id: str
    pack_id: str
    title: str
    collection: str
    group: str
    category_key: str
    category_label: str
    width: int
    height: int
    tags: list[str]
    grid: BundledGridOut


class BundledMapCreate(BaseModel):
    pack_id: str = Field(min_length=1, max_length=160)
    asset_id: str = Field(min_length=1, max_length=240)
    name: str | None = Field(default=None, max_length=160)

    @field_validator("pack_id", "asset_id", mode="before")
    @classmethod
    def trim_required_fields(cls, value: object) -> object:
        return _trim_required(value)

    @field_validator("name", mode="before")
    @classmethod
    def trim_optional_name(cls, value: object) -> object:
        return _trim_optional(value)


class BundledMapCreateOut(BaseModel):
    asset: AssetOut
    map: MapOut
    created_asset: bool
    created_map: bool


class MapCreate(BaseModel):
    asset_id: UUID
    name: str | None = Field(default=None, max_length=160)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value: object) -> object:
        return _trim_optional(value)


class MapGridPatch(BaseModel):
    grid_enabled: bool | None = None
    grid_size_px: int | None = Field(default=None, ge=4, le=500)
    grid_offset_x: float | None = None
    grid_offset_y: float | None = None
    grid_color: str | None = None
    grid_opacity: float | None = Field(default=None, ge=0, le=1)

    @field_validator("grid_color", mode="before")
    @classmethod
    def trim_color(cls, value: object) -> object:
        return _trim_optional(value)


class SceneMapOut(BaseModel):
    id: str
    campaign_id: str
    scene_id: str
    map_id: str
    is_active: bool
    player_fit_mode: str
    player_grid_visible: bool
    map: MapOut
    created_at: str
    updated_at: str


class SceneMapCreate(BaseModel):
    map_id: UUID
    is_active: bool = False
    player_fit_mode: str = "fit"
    player_grid_visible: bool = True

    @field_validator("player_fit_mode", mode="before")
    @classmethod
    def trim_fit_mode(cls, value: object) -> object:
        return _trim_required(value)


class SceneMapPatch(BaseModel):
    player_fit_mode: str | None = None
    player_grid_visible: bool | None = None

    @field_validator("player_fit_mode", mode="before")
    @classmethod
    def trim_fit_mode(cls, value: object) -> object:
        return _trim_optional(value)


class ShowMapIn(BaseModel):
    scene_map_id: UUID | None = None


class FogMaskOut(BaseModel):
    id: str
    campaign_id: str
    scene_id: str
    scene_map_id: str
    enabled: bool
    revision: int
    width: int
    height: int
    mask_url: str
    updated_at: str


class FogPointIn(BaseModel):
    x: float
    y: float


class FogRectIn(BaseModel):
    x: float
    y: float
    width: float
    height: float


class FogOperationIn(BaseModel):
    type: str
    rect: FogRectIn | None = None
    points: list[FogPointIn] | None = None
    radius: float | None = None

    @field_validator("type", mode="before")
    @classmethod
    def trim_type(cls, value: object) -> object:
        return _trim_required(value)


class FogOperationsIn(BaseModel):
    operations: list[FogOperationIn] = Field(min_length=1, max_length=16)


class FogOperationResultOut(BaseModel):
    fog: FogMaskOut
    player_display: PlayerDisplayOut | None


class TokenOut(BaseModel):
    id: str
    campaign_id: str
    scene_id: str
    scene_map_id: str
    entity_id: str | None
    asset_id: str | None
    asset_name: str | None
    asset_visibility: str | None
    asset_url: str | None
    name: str
    x: float
    y: float
    width: float
    height: float
    rotation: float
    z_index: int
    visibility: str
    label_visibility: str
    shape: str
    color: str
    border_color: str
    opacity: float
    status: list[dict[str, object]]
    created_at: str
    updated_at: str


class TokensOut(BaseModel):
    tokens: list[TokenOut]
    updated_at: str


class TokenMutationOut(BaseModel):
    token: TokenOut
    player_display: PlayerDisplayOut | None


class TokenDeleteOut(BaseModel):
    deleted_token_id: str
    player_display: PlayerDisplayOut | None


class TokenCreate(BaseModel):
    name: str = Field(default="Token", min_length=1, max_length=160)
    x: float | None = None
    y: float | None = None
    width: float = Field(default=70, gt=0, le=1000)
    height: float = Field(default=70, gt=0, le=1000)
    rotation: float = 0
    z_index: int = Field(default=0, ge=-10000, le=10000)
    visibility: str = "gm_only"
    label_visibility: str = "gm_only"
    shape: str = "circle"
    color: str = "#D94841"
    border_color: str = "#FFFFFF"
    opacity: float = Field(default=1, ge=0, le=1)
    asset_id: UUID | None = None
    entity_id: str | None = Field(default=None, max_length=160)
    status: list[dict[str, object]] = Field(default_factory=list, max_length=20)

    @field_validator("name", "visibility", "label_visibility", "shape", "color", "border_color", mode="before")
    @classmethod
    def trim_required_token_fields(cls, value: object) -> object:
        return _trim_required(value)

    @field_validator("entity_id", mode="before")
    @classmethod
    def trim_entity_id(cls, value: object) -> object:
        return _trim_optional(value)


class TokenPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    x: float | None = None
    y: float | None = None
    width: float | None = Field(default=None, gt=0, le=1000)
    height: float | None = Field(default=None, gt=0, le=1000)
    rotation: float | None = None
    z_index: int | None = Field(default=None, ge=-10000, le=10000)
    visibility: str | None = None
    label_visibility: str | None = None
    shape: str | None = None
    color: str | None = None
    border_color: str | None = None
    opacity: float | None = Field(default=None, ge=0, le=1)
    asset_id: UUID | None = None
    entity_id: str | None = Field(default=None, max_length=160)
    status: list[dict[str, object]] | None = Field(default=None, max_length=20)

    @field_validator("name", "visibility", "label_visibility", "shape", "color", "border_color", mode="before")
    @classmethod
    def trim_optional_token_fields(cls, value: object) -> object:
        return _trim_optional(value)

    @field_validator("entity_id", mode="before")
    @classmethod
    def trim_entity_id(cls, value: object) -> object:
        return _trim_optional(value)


class EntityOut(BaseModel):
    id: str
    campaign_id: str
    kind: str
    name: str
    display_name: str | None
    visibility: str
    portrait_asset_id: str | None
    portrait_asset_name: str | None
    portrait_asset_visibility: str | None
    tags: list[str]
    notes: str
    field_values: dict[str, object]
    created_at: str
    updated_at: str


class EntitiesOut(BaseModel):
    entities: list[EntityOut]
    updated_at: str


class EntityCreate(BaseModel):
    kind: str = "pc"
    name: str = Field(min_length=1, max_length=160)
    display_name: str | None = Field(default=None, max_length=160)
    visibility: str = "private"
    portrait_asset_id: UUID | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=20_000)

    @field_validator("kind", "name", "visibility", mode="before")
    @classmethod
    def trim_required_fields(cls, value: object) -> object:
        return _trim_required(value)

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_display_name(cls, value: object) -> object:
        return _trim_optional(value)


class EntityPatch(BaseModel):
    kind: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    display_name: str | None = Field(default=None, max_length=160)
    visibility: str | None = None
    portrait_asset_id: UUID | None = None
    tags: list[str] | None = None
    notes: str | None = Field(default=None, max_length=20_000)

    @field_validator("kind", "name", "visibility", mode="before")
    @classmethod
    def trim_required_optional_fields(cls, value: object) -> object:
        return _trim_optional(value)

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_display_name(cls, value: object) -> object:
        return _trim_optional(value)


class CustomFieldDefinitionOut(BaseModel):
    id: str
    campaign_id: str
    key: str
    label: str
    field_type: str
    applies_to: list[str]
    required: bool
    default_value: object | None
    options: list[str]
    public_by_default: bool
    sort_order: int
    created_at: str
    updated_at: str


class CustomFieldsOut(BaseModel):
    fields: list[CustomFieldDefinitionOut]
    updated_at: str


class CustomFieldCreate(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=160)
    field_type: str = "short_text"
    applies_to: list[str] = Field(default_factory=lambda: ["pc"])
    required: bool = False
    default_value: object | None = None
    options: list[str] = Field(default_factory=list)
    public_by_default: bool = False
    sort_order: int = Field(default=0, ge=-10000, le=10000)

    @field_validator("key", "label", "field_type", mode="before")
    @classmethod
    def trim_required_fields(cls, value: object) -> object:
        return _trim_required(value)


class CustomFieldPatch(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=160)
    applies_to: list[str] | None = None
    required: bool | None = None
    default_value: object | None = None
    options: list[str] | None = None
    public_by_default: bool | None = None
    sort_order: int | None = Field(default=None, ge=-10000, le=10000)

    @field_validator("label", mode="before")
    @classmethod
    def trim_label(cls, value: object) -> object:
        return _trim_optional(value)


class FieldValuesPatch(BaseModel):
    values: dict[str, object | None] = Field(default_factory=dict)


class PartyMemberOut(BaseModel):
    id: str
    entity_id: str
    sort_order: int
    entity: EntityOut


class PartyFieldOut(BaseModel):
    id: str
    field_definition_id: str
    sort_order: int
    public_visible: bool
    field: CustomFieldDefinitionOut


class PartyTrackerOut(BaseModel):
    id: str
    campaign_id: str
    layout: str
    members: list[PartyMemberOut]
    fields: list[PartyFieldOut]
    updated_at: str


class PartyFieldPatchIn(BaseModel):
    field_definition_id: UUID
    public_visible: bool = False


class PartyTrackerPatch(BaseModel):
    layout: str | None = None
    member_ids: list[UUID] | None = None
    fields: list[PartyFieldPatchIn] | None = None

    @field_validator("layout", mode="before")
    @classmethod
    def trim_layout(cls, value: object) -> object:
        return _trim_optional(value)


class ShowPartyIn(BaseModel):
    campaign_id: UUID | None = None


class CombatantOut(BaseModel):
    id: str
    campaign_id: str
    encounter_id: str
    entity_id: str | None
    token_id: str | None
    name: str
    disposition: str
    initiative: float | None
    order_index: int
    armor_class: int | None
    hp_current: int | None
    hp_max: int | None
    hp_temp: int
    conditions: list[dict[str, object]]
    public_status: list[object]
    notes: str
    public_visible: bool
    is_defeated: bool
    portrait_asset_id: str | None
    portrait_asset_name: str | None
    created_at: str
    updated_at: str


class CombatEncounterOut(BaseModel):
    id: str
    campaign_id: str
    session_id: str | None
    scene_id: str | None
    title: str
    status: str
    round: int
    active_combatant_id: str | None
    combatants: list[CombatantOut]
    created_at: str
    updated_at: str


class CombatEncountersOut(BaseModel):
    encounters: list[CombatEncounterOut]
    updated_at: str


class CombatEncounterCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    session_id: UUID | None = None
    scene_id: UUID | None = None
    status: str = "active"

    @field_validator("title", "status", mode="before")
    @classmethod
    def trim_required_fields(cls, value: object) -> object:
        return _trim_required(value)


class CombatEncounterPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    session_id: UUID | None = None
    scene_id: UUID | None = None
    status: str | None = None
    round: int | None = Field(default=None, ge=1, le=10_000)
    active_combatant_id: UUID | None = None

    @field_validator("title", "status", mode="before")
    @classmethod
    def trim_optional_fields(cls, value: object) -> object:
        return _trim_optional(value)


class CombatantCreate(BaseModel):
    entity_id: UUID | None = None
    token_id: UUID | None = None
    name: str | None = Field(default=None, max_length=160)
    disposition: str | None = None
    initiative: float | None = Field(default=None, ge=-100, le=100)
    armor_class: int | None = Field(default=None, ge=0, le=100)
    hp_current: int | None = Field(default=None, ge=-1000, le=10000)
    hp_max: int | None = Field(default=None, ge=0, le=10000)
    hp_temp: int = Field(default=0, ge=0, le=10000)
    conditions: list[dict[str, object]] = Field(default_factory=list, max_length=20)
    public_status: list[object] = Field(default_factory=list, max_length=12)
    notes: str = Field(default="", max_length=4000)
    public_visible: bool | None = None
    is_defeated: bool = False

    @field_validator("name", "disposition", mode="before")
    @classmethod
    def trim_fields(cls, value: object) -> object:
        return _trim_optional(value)


class CombatantPatch(BaseModel):
    entity_id: UUID | None = None
    token_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    disposition: str | None = None
    initiative: float | None = Field(default=None, ge=-100, le=100)
    order_index: int | None = Field(default=None, ge=0, le=10000)
    armor_class: int | None = Field(default=None, ge=0, le=100)
    hp_current: int | None = Field(default=None, ge=-1000, le=10000)
    hp_max: int | None = Field(default=None, ge=0, le=10000)
    hp_temp: int | None = Field(default=None, ge=0, le=10000)
    conditions: list[dict[str, object]] | None = Field(default=None, max_length=20)
    public_status: list[object] | None = Field(default=None, max_length=12)
    notes: str | None = Field(default=None, max_length=4000)
    public_visible: bool | None = None
    is_defeated: bool | None = None

    @field_validator("name", "disposition", mode="before")
    @classmethod
    def trim_optional_fields(cls, value: object) -> object:
        return _trim_optional(value)


class CombatReorderIn(BaseModel):
    combatant_ids: list[UUID] = Field(min_length=1, max_length=200)


class CombatantDeleteOut(BaseModel):
    deleted_combatant_id: str
    encounter: CombatEncounterOut


class ShowInitiativeIn(BaseModel):
    encounter_id: UUID


class NoteSummaryOut(BaseModel):
    id: str
    campaign_id: str
    source_id: str | None
    session_id: str | None
    scene_id: str | None
    asset_id: str | None
    title: str
    tags: list[str]
    source_label: str | None
    created_at: str
    updated_at: str


class NoteOut(NoteSummaryOut):
    private_body: str


class NotesOut(BaseModel):
    notes: list[NoteSummaryOut]
    updated_at: str


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    private_body: str = Field(default="", max_length=200_000)
    tags: list[str] = Field(default_factory=list)
    session_id: UUID | None = None
    scene_id: UUID | None = None
    asset_id: UUID | None = None

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value: object) -> object:
        return _trim_required(value)


class NotePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    private_body: str | None = Field(default=None, max_length=200_000)
    tags: list[str] | None = None
    session_id: UUID | None = None
    scene_id: UUID | None = None
    asset_id: UUID | None = None

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value: object) -> object:
        return _trim_optional(value)


class PublicSnippetOut(BaseModel):
    id: str
    campaign_id: str
    note_id: str | None
    title: str | None
    body: str
    format: str
    created_at: str
    updated_at: str


class PublicSnippetsOut(BaseModel):
    snippets: list[PublicSnippetOut]
    updated_at: str


class PublicSnippetCreate(BaseModel):
    note_id: UUID | None = None
    title: str | None = Field(default=None, max_length=160)
    body: str = Field(min_length=1, max_length=8000)
    format: str = "markdown"

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value: object) -> object:
        return _trim_optional(value)

    @field_validator("body", "format", mode="before")
    @classmethod
    def trim_required_fields(cls, value: object) -> object:
        return _trim_required(value)


class PublicSnippetPatch(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    body: str | None = Field(default=None, min_length=1, max_length=8000)
    format: str | None = None

    @field_validator("title", "body", "format", mode="before")
    @classmethod
    def trim_fields(cls, value: object) -> object:
        return _trim_optional(value)


class ShowSnippetIn(BaseModel):
    snippet_id: UUID


class SceneContextConfigOut(BaseModel):
    id: str
    campaign_id: str
    scene_id: str
    active_encounter_id: str | None
    staged_display_mode: str
    staged_public_snippet_id: str | None
    created_at: str
    updated_at: str


class SceneEntityLinkOut(BaseModel):
    id: str
    campaign_id: str
    scene_id: str
    entity_id: str
    role: str
    sort_order: int
    notes: str
    entity: EntityOut
    created_at: str
    updated_at: str


class ScenePublicSnippetLinkOut(BaseModel):
    id: str
    campaign_id: str
    scene_id: str
    public_snippet_id: str
    sort_order: int
    snippet: PublicSnippetOut
    created_at: str
    updated_at: str


class SceneContextOut(BaseModel):
    scene: SceneOut
    context: SceneContextConfigOut
    active_map: SceneMapOut | None
    notes: list[NoteSummaryOut]
    public_snippets: list[ScenePublicSnippetLinkOut]
    entities: list[SceneEntityLinkOut]
    active_encounter: CombatEncounterOut | None
    updated_at: str


class SceneContextPatch(BaseModel):
    active_encounter_id: UUID | None = None
    staged_display_mode: str | None = None
    staged_public_snippet_id: UUID | None = None

    @field_validator("staged_display_mode", mode="before")
    @classmethod
    def trim_display_mode(cls, value: object) -> object:
        return _trim_optional(value)


class SceneEntityLinkCreate(BaseModel):
    entity_id: UUID
    role: str = "supporting"
    sort_order: int = Field(default=0, ge=0, le=10000)
    notes: str = Field(default="", max_length=2000)

    @field_validator("role", mode="before")
    @classmethod
    def trim_role(cls, value: object) -> object:
        return _trim_required(value)

    @field_validator("notes", mode="before")
    @classmethod
    def trim_notes(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ScenePublicSnippetLinkCreate(BaseModel):
    public_snippet_id: UUID
    sort_order: int = Field(default=0, ge=0, le=10000)


def get_db(request: Request):
    yield from session_for_settings(request.app.state.settings)


DbSession = Annotated[Session, Depends(get_db)]


def _new_id() -> str:
    return str(uuid.uuid4())


def _require_campaign(db: Session, campaign_id: UUID | str) -> Campaign:
    campaign = db.get(Campaign, str(campaign_id))
    if campaign is None:
        raise api_error(404, "campaign_not_found", "Campaign not found")
    return campaign


def _require_session(db: Session, session_id: UUID | str) -> CampaignSession:
    session = db.get(CampaignSession, str(session_id))
    if session is None:
        raise api_error(404, "session_not_found", "Session not found")
    return session


def _require_scene(db: Session, scene_id: UUID | str) -> Scene:
    scene = db.get(Scene, str(scene_id))
    if scene is None:
        raise api_error(404, "scene_not_found", "Scene not found")
    return scene


def _require_asset(db: Session, asset_id: UUID | str) -> Asset:
    asset = db.get(Asset, str(asset_id))
    if asset is None:
        raise api_error(404, "asset_not_found", "Asset not found")
    return asset


def _require_map(db: Session, map_id: UUID | str) -> CampaignMap:
    campaign_map = db.get(CampaignMap, str(map_id))
    if campaign_map is None:
        raise api_error(404, "map_not_found", "Map not found")
    return campaign_map


def _require_scene_map(db: Session, scene_map_id: UUID | str) -> SceneMap:
    scene_map = db.get(SceneMap, str(scene_map_id))
    if scene_map is None:
        raise api_error(404, "scene_map_not_found", "Scene map not found")
    return scene_map


def _require_fog_mask(db: Session, fog_mask_id: UUID | str) -> SceneMapFogMask:
    fog = db.get(SceneMapFogMask, str(fog_mask_id))
    if fog is None:
        raise api_error(404, "fog_mask_not_found", "Fog mask not found")
    return fog


def _require_token(db: Session, token_id: UUID | str) -> SceneMapToken:
    token = db.get(SceneMapToken, str(token_id))
    if token is None:
        raise api_error(404, "token_not_found", "Token not found")
    return token


def _require_note(db: Session, note_id: UUID | str) -> Note:
    note = db.get(Note, str(note_id))
    if note is None:
        raise api_error(404, "note_not_found", "Note not found")
    return note


def _require_public_snippet(db: Session, snippet_id: UUID | str) -> PublicSnippet:
    snippet = db.get(PublicSnippet, str(snippet_id))
    if snippet is None:
        raise api_error(404, "public_snippet_not_found", "Public snippet not found")
    return snippet


def _require_entity(db: Session, entity_id: UUID | str) -> Entity:
    entity = db.get(Entity, str(entity_id))
    if entity is None:
        raise api_error(404, "entity_not_found", "Entity not found")
    return entity


def _require_custom_field(db: Session, field_id: UUID | str) -> CustomFieldDefinition:
    field = db.get(CustomFieldDefinition, str(field_id))
    if field is None:
        raise api_error(404, "custom_field_not_found", "Custom field not found")
    return field


def _require_combat_encounter(db: Session, encounter_id: UUID | str) -> CombatEncounter:
    encounter = db.get(CombatEncounter, str(encounter_id))
    if encounter is None:
        raise api_error(404, "combat_encounter_not_found", "Combat encounter not found")
    return encounter


def _require_combatant(db: Session, combatant_id: UUID | str) -> Combatant:
    combatant = db.get(Combatant, str(combatant_id))
    if combatant is None:
        raise api_error(404, "combatant_not_found", "Combatant not found")
    return combatant


def _require_scene_entity_link(db: Session, link_id: UUID | str) -> SceneEntityLink:
    link = db.get(SceneEntityLink, str(link_id))
    if link is None:
        raise api_error(404, "scene_entity_link_not_found", "Scene entity link not found")
    return link


def _require_scene_public_snippet_link(db: Session, link_id: UUID | str) -> ScenePublicSnippetLink:
    link = db.get(ScenePublicSnippetLink, str(link_id))
    if link is None:
        raise api_error(404, "scene_public_snippet_link_not_found", "Scene public snippet link not found")
    return link


def _require_image_asset_kind(kind: str) -> str:
    if kind not in IMAGE_ASSET_KINDS:
        raise api_error(400, "invalid_asset_kind", "Asset kind must be an image kind")
    return kind


def _require_asset_visibility(visibility: str) -> str:
    if visibility not in ASSET_VISIBILITIES:
        raise api_error(400, "invalid_asset_visibility", "Asset visibility is invalid")
    return visibility


def _require_fit_mode(value: str) -> str:
    if value not in DISPLAY_FIT_MODES:
        raise api_error(400, "invalid_fit_mode", "Fit mode is invalid")
    return value


def _normalize_hex_color(value: str) -> str:
    color = value.strip()
    if not HEX_COLOR_RE.fullmatch(color):
        raise api_error(400, "invalid_grid_color", "Grid color must be a hex color")
    hex_value = color[1:]
    if len(hex_value) == 3:
        hex_value = "".join(character * 2 for character in hex_value)
    return f"#{hex_value.upper()}"


def _normalize_token_color(value: str) -> str:
    try:
        return _normalize_hex_color(value)
    except Exception as error:
        if getattr(error, "status_code", None) == 400:
            raise api_error(400, "invalid_token_color", "Token color must be a hex color") from error
        raise


def _require_finite(value: float, code: str, message: str) -> float:
    if not math.isfinite(value):
        raise api_error(400, code, message)
    return value


def _normalize_rotation(value: float) -> float:
    rotation = _require_finite(float(value), "invalid_token_rotation", "Token rotation must be finite")
    return rotation % 360


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _require_token_visibility(value: str) -> str:
    if value not in TOKEN_VISIBILITIES:
        raise api_error(400, "invalid_token_visibility", "Token visibility is invalid")
    return value


def _require_label_visibility(value: str) -> str:
    if value not in LABEL_VISIBILITIES:
        raise api_error(400, "invalid_label_visibility", "Token label visibility is invalid")
    return value


def _require_token_shape(value: str) -> str:
    if value not in TOKEN_SHAPES:
        raise api_error(400, "invalid_token_shape", "Token shape is invalid")
    return value


def _clean_asset_name(value: str | None, fallback: str | None) -> str:
    name = (value or "").strip()
    if not name and fallback:
        name = Path(fallback).stem.strip()
    if not name:
        name = "Image asset"
    return name[:160]


def _normalize_tags(tags: list[str] | str | None) -> list[str]:
    values = tags.split(",") if isinstance(tags, str) else tags or []
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        tag = str(raw).strip()
        if not tag:
            continue
        tag = tag[:64]
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(tag)
        if len(normalized) >= 30:
            break
    return normalized


def _parse_tags_json(value: str | None) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(tag) for tag in parsed if isinstance(tag, str)]


def _parse_json_list(value: str | None) -> list[dict[str, object]]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _normalize_public_status(value: list[object] | None) -> list[object]:
    normalized: list[object] = []
    for item in value or []:
        if isinstance(item, str):
            label = item.strip()
        elif isinstance(item, dict) and set(item.keys()) <= {"label"} and isinstance(item.get("label"), str):
            label = str(item["label"]).strip()
        else:
            raise api_error(400, "invalid_public_status", "Public status accepts only strings or { label } objects")
        if not label:
            continue
        if len(label) > 80:
            raise api_error(400, "invalid_public_status", "Public status labels must be 80 characters or fewer")
        normalized.append({"label": label} if isinstance(item, dict) else label)
        if len(normalized) >= 12:
            break
    return normalized


def _parse_public_status_json(value: str | None) -> list[object]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return _normalize_public_status(parsed if isinstance(parsed, list) else [])


def _note_source_id(campaign_id: str, kind: str, name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"myroll:note-source:{campaign_id}:{kind}:{name}"))


def _require_snippet_format(value: str) -> str:
    if value not in SNIPPET_FORMATS:
        raise api_error(400, "invalid_snippet_format", "Snippet format is invalid")
    return value


def _note_source_if_missing(db: Session, campaign_id: str, *, kind: str, name: str, now: str) -> NoteSource:
    source_id = _note_source_id(campaign_id, kind, name)
    source = db.get(NoteSource, source_id)
    if source is not None:
        return source
    source = NoteSource(
        id=source_id,
        campaign_id=campaign_id,
        kind=kind,
        name=name[:160],
        readonly=False,
        created_at=now,
        updated_at=now,
    )
    db.add(source)
    db.flush()
    return source


def _validate_note_links(
    db: Session,
    campaign_id: str,
    *,
    session_id: UUID | str | None,
    scene_id: UUID | str | None,
    asset_id: UUID | str | None,
) -> tuple[str | None, str | None, str | None]:
    resolved_session_id = str(session_id) if session_id is not None else None
    resolved_scene_id = str(scene_id) if scene_id is not None else None
    resolved_asset_id = str(asset_id) if asset_id is not None else None
    if resolved_session_id is not None:
        session = _require_session(db, resolved_session_id)
        if session.campaign_id != campaign_id:
            raise api_error(400, "session_campaign_mismatch", "Session does not belong to campaign")
    if resolved_scene_id is not None:
        scene = _require_scene(db, resolved_scene_id)
        if scene.campaign_id != campaign_id:
            raise api_error(400, "scene_campaign_mismatch", "Scene does not belong to campaign")
    if resolved_asset_id is not None:
        asset = _require_asset(db, resolved_asset_id)
        if asset.campaign_id != campaign_id:
            raise api_error(400, "asset_campaign_mismatch", "Asset does not belong to campaign")
    return resolved_session_id, resolved_scene_id, resolved_asset_id


def _note_summary_out(note: Note) -> NoteSummaryOut:
    return NoteSummaryOut(
        id=note.id,
        campaign_id=note.campaign_id,
        source_id=note.source_id,
        session_id=note.session_id,
        scene_id=note.scene_id,
        asset_id=note.asset_id,
        title=note.title,
        tags=_parse_tags_json(note.tags_json),
        source_label=note.source_label,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def _note_out(note: Note) -> NoteOut:
    summary = _note_summary_out(note)
    return NoteOut(**summary.model_dump(), private_body=note.private_body)


def _notes_response(db: Session, campaign_id: str) -> NotesOut:
    notes = list(
        db.scalars(
            select(Note)
            .where(Note.campaign_id == campaign_id)
            .order_by(Note.updated_at.desc(), Note.title, Note.id)
        )
    )
    updated_at = max((note.updated_at for note in notes), default=utc_now_z())
    return NotesOut(notes=[_note_summary_out(note) for note in notes], updated_at=updated_at)


def _public_snippet_out(snippet: PublicSnippet) -> PublicSnippetOut:
    return PublicSnippetOut(
        id=snippet.id,
        campaign_id=snippet.campaign_id,
        note_id=snippet.note_id,
        title=snippet.title,
        body=snippet.body,
        format=snippet.format,
        created_at=snippet.created_at,
        updated_at=snippet.updated_at,
    )


def _public_snippets_response(db: Session, campaign_id: str) -> PublicSnippetsOut:
    snippets = list(
        db.scalars(
            select(PublicSnippet)
            .where(PublicSnippet.campaign_id == campaign_id)
            .order_by(PublicSnippet.updated_at.desc(), PublicSnippet.title, PublicSnippet.id)
        )
    )
    updated_at = max((snippet.updated_at for snippet in snippets), default=utc_now_z())
    return PublicSnippetsOut(snippets=[_public_snippet_out(snippet) for snippet in snippets], updated_at=updated_at)


def _scene_out(scene: Scene) -> SceneOut:
    return SceneOut(
        id=scene.id,
        campaign_id=scene.campaign_id,
        session_id=scene.session_id,
        title=scene.title,
        summary=scene.summary,
        created_at=scene.created_at,
        updated_at=scene.updated_at,
    )


def _scene_context_id(scene_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"myroll:scene-context:{scene_id}"))


def _require_scene_staged_display_mode(value: str) -> str:
    if value not in SCENE_STAGED_DISPLAY_MODES:
        raise api_error(400, "invalid_staged_display_mode", "Staged display mode is invalid")
    return value


def _require_scene_entity_role(value: str) -> str:
    if value not in SCENE_ENTITY_ROLES:
        raise api_error(400, "invalid_scene_entity_role", "Scene entity role is invalid")
    return value


def _ensure_scene_context(db: Session, scene: Scene) -> SceneContext:
    context = db.scalars(select(SceneContext).where(SceneContext.scene_id == scene.id)).one_or_none()
    if context is not None:
        return context
    now = utc_now_z()
    context = SceneContext(
        id=_scene_context_id(scene.id),
        campaign_id=scene.campaign_id,
        scene_id=scene.id,
        active_encounter_id=None,
        staged_display_mode="none",
        staged_public_snippet_id=None,
        created_at=now,
        updated_at=now,
    )
    db.add(context)
    db.flush()
    return context


def _active_scene_map(db: Session, scene_id: str) -> SceneMap | None:
    return db.scalars(select(SceneMap).where(SceneMap.scene_id == scene_id, SceneMap.is_active.is_(True))).one_or_none()


def _scene_entity_link_out(db: Session, link: SceneEntityLink) -> SceneEntityLinkOut:
    entity = _require_entity(db, link.entity_id)
    return SceneEntityLinkOut(
        id=link.id,
        campaign_id=link.campaign_id,
        scene_id=link.scene_id,
        entity_id=link.entity_id,
        role=link.role,
        sort_order=link.sort_order,
        notes=link.notes,
        entity=_entity_out(db, entity),
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


def _scene_public_snippet_link_out(link: ScenePublicSnippetLink, snippet: PublicSnippet) -> ScenePublicSnippetLinkOut:
    return ScenePublicSnippetLinkOut(
        id=link.id,
        campaign_id=link.campaign_id,
        scene_id=link.scene_id,
        public_snippet_id=link.public_snippet_id,
        sort_order=link.sort_order,
        snippet=_public_snippet_out(snippet),
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


def _scene_public_snippet_link(
    db: Session,
    scene_id: str,
    public_snippet_id: UUID | str,
) -> ScenePublicSnippetLink | None:
    return db.scalars(
        select(ScenePublicSnippetLink).where(
            ScenePublicSnippetLink.scene_id == scene_id,
            ScenePublicSnippetLink.public_snippet_id == str(public_snippet_id),
        )
    ).one_or_none()


def _scene_context_config_out(context: SceneContext) -> SceneContextConfigOut:
    return SceneContextConfigOut(
        id=context.id,
        campaign_id=context.campaign_id,
        scene_id=context.scene_id,
        active_encounter_id=context.active_encounter_id,
        staged_display_mode=context.staged_display_mode,
        staged_public_snippet_id=context.staged_public_snippet_id,
        created_at=context.created_at,
        updated_at=context.updated_at,
    )


def _scene_context_response(db: Session, scene: Scene) -> SceneContextOut:
    context = _ensure_scene_context(db, scene)
    active_scene_map = _active_scene_map(db, scene.id)
    notes = list(
        db.scalars(
            select(Note)
            .where(Note.scene_id == scene.id)
            .order_by(Note.updated_at.desc(), Note.title, Note.id)
        )
    )
    entity_links = list(
        db.scalars(
            select(SceneEntityLink)
            .where(SceneEntityLink.scene_id == scene.id)
            .order_by(SceneEntityLink.sort_order, SceneEntityLink.role, SceneEntityLink.id)
        )
    )
    snippet_links = list(
        db.scalars(
            select(ScenePublicSnippetLink)
            .where(ScenePublicSnippetLink.scene_id == scene.id)
            .order_by(ScenePublicSnippetLink.sort_order, ScenePublicSnippetLink.id)
        )
    )
    snippet_link_out: list[ScenePublicSnippetLinkOut] = []
    for link in snippet_links:
        snippet = db.get(PublicSnippet, link.public_snippet_id)
        if snippet is not None:
            snippet_link_out.append(_scene_public_snippet_link_out(link, snippet))
    active_encounter = db.get(CombatEncounter, context.active_encounter_id) if context.active_encounter_id else None
    updated_candidates = [
        scene.updated_at,
        context.updated_at,
        *(note.updated_at for note in notes),
        *(link.updated_at for link in entity_links),
        *(link.updated_at for link in snippet_links),
    ]
    if active_scene_map is not None:
        updated_candidates.append(active_scene_map.updated_at)
    if active_encounter is not None:
        updated_candidates.append(active_encounter.updated_at)
    return SceneContextOut(
        scene=_scene_out(scene),
        context=_scene_context_config_out(context),
        active_map=_scene_map_out(db, active_scene_map) if active_scene_map is not None else None,
        notes=[_note_summary_out(note) for note in notes],
        public_snippets=snippet_link_out,
        entities=[_scene_entity_link_out(db, link) for link in entity_links],
        active_encounter=_combat_encounter_out(db, active_encounter) if active_encounter is not None else None,
        updated_at=max(updated_candidates),
    )


def _validate_scene_context_patch(db: Session, scene: Scene, context: SceneContext, data: dict[str, object]) -> None:
    if "active_encounter_id" in data:
        if data["active_encounter_id"] is None:
            context.active_encounter_id = None
        else:
            encounter = _require_combat_encounter(db, data["active_encounter_id"])
            if encounter.campaign_id != scene.campaign_id:
                raise api_error(400, "combat_encounter_campaign_mismatch", "Combat encounter does not belong to scene campaign")
            if encounter.scene_id != scene.id:
                raise api_error(400, "combat_encounter_scene_mismatch", "Combat encounter is not linked to this scene")
            context.active_encounter_id = encounter.id
    if "staged_display_mode" in data and data["staged_display_mode"] is not None:
        context.staged_display_mode = _require_scene_staged_display_mode(str(data["staged_display_mode"]))
    if "staged_public_snippet_id" in data:
        if data["staged_public_snippet_id"] is None:
            context.staged_public_snippet_id = None
        else:
            snippet = _require_public_snippet(db, data["staged_public_snippet_id"])
            if snippet.campaign_id != scene.campaign_id:
                raise api_error(400, "public_snippet_campaign_mismatch", "Public snippet does not belong to scene campaign")
            if _scene_public_snippet_link(db, scene.id, snippet.id) is None:
                raise api_error(400, "public_snippet_not_linked_to_scene", "Public snippet is not linked to this scene")
            context.staged_public_snippet_id = snippet.id
    context.updated_at = utc_now_z()


def _decode_markdown_bytes(content: bytes) -> str:
    if len(content) > MAX_MARKDOWN_IMPORT_BYTES:
        raise api_error(413, "markdown_file_too_large", "Markdown import is too large")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise api_error(400, "markdown_decode_failed", "Markdown import must be UTF-8") from error


def _validate_markdown_suffix(name: str) -> None:
    if Path(name).suffix.lower() not in MARKDOWN_IMPORT_SUFFIXES:
        raise api_error(400, "unsupported_markdown_extension", "Markdown import must be .md, .markdown, or .txt")


def _apply_text_display(display: PlayerDisplayRuntime, db: Session, snippet: PublicSnippet) -> None:
    campaign = db.get(Campaign, snippet.campaign_id)
    public_payload = {
        "type": "public_snippet",
        "snippet_id": snippet.id,
        "title": snippet.title,
        "body": snippet.body,
        "format": snippet.format,
    }
    display.mode = "text"
    display.active_campaign_id = snippet.campaign_id
    display.active_session_id = None
    display.active_scene_id = None
    display.title = snippet.title
    display.subtitle = campaign.name if campaign else None
    display.payload_json = json.dumps(public_payload)
    display.revision += 1
    display.updated_at = utc_now_z()


def _public_party_value_payload(db: Session, field: CustomFieldDefinition, value: object) -> dict[str, object] | None:
    public_value = value
    if field.field_type == "image":
        asset = db.get(Asset, str(value))
        if (
            asset is None
            or asset.visibility != "public_displayable"
            or asset.kind not in IMAGE_ASSET_KINDS
            or not asset.mime_type.startswith("image/")
        ):
            return None
        public_value = {
            "asset_id": asset.id,
            "asset_url": f"/api/player-display/assets/{asset.id}/blob",
            "name": asset.name,
            "mime_type": asset.mime_type,
            "width": asset.width,
            "height": asset.height,
        }
    return {
        "key": field.key,
        "label": field.label,
        "type": field.field_type,
        "value": public_value,
    }


def _create_public_party_payload(db: Session, campaign_id: str) -> dict[str, object]:
    config = _party_config_for_campaign(db, campaign_id)
    if config is None:
        raise api_error(404, "party_tracker_not_configured", "Party tracker is not configured")
    party_fields = list(
        db.scalars(
            select(PartyTrackerField)
            .where(PartyTrackerField.config_id == config.id, PartyTrackerField.public_visible.is_(True))
            .order_by(PartyTrackerField.sort_order, PartyTrackerField.id)
        )
    )
    fields = [db.get(CustomFieldDefinition, party_field.field_definition_id) for party_field in party_fields]
    fields = [field for field in fields if field is not None]
    members = list(
        db.scalars(
            select(PartyTrackerMember)
            .where(PartyTrackerMember.config_id == config.id)
            .order_by(PartyTrackerMember.sort_order, PartyTrackerMember.id)
        )
    )
    cards: list[dict[str, object]] = []
    for member in members:
        entity = db.get(Entity, member.entity_id)
        if entity is None or entity.visibility != "public_known":
            continue
        values = _field_values_for_entity(db, entity)
        card_fields: list[dict[str, object]] = []
        for field in fields:
            if entity.kind not in _field_applies_to(field):
                continue
            value = values.get(field.key, _field_default_value(field))
            if value is None:
                continue
            public_field = _public_party_value_payload(db, field, value)
            if public_field is not None:
                card_fields.append(public_field)
        card: dict[str, object] = {
            "entity_id": entity.id,
            "display_name": entity.display_name or entity.name,
            "kind": entity.kind,
            "portrait_asset_id": None,
            "portrait_url": None,
            "fields": card_fields,
        }
        asset = db.get(Asset, entity.portrait_asset_id) if entity.portrait_asset_id else None
        if (
            asset is not None
            and asset.visibility == "public_displayable"
            and asset.kind in IMAGE_ASSET_KINDS
            and asset.mime_type.startswith("image/")
        ):
            card["portrait_asset_id"] = asset.id
            card["portrait_url"] = f"/api/player-display/assets/{asset.id}/blob"
        cards.append(card)
    return {
        "type": "party",
        "campaign_id": campaign_id,
        "layout": config.layout,
        "cards": cards,
    }


def _apply_party_display(display: PlayerDisplayRuntime, db: Session, campaign_id: str) -> None:
    campaign = _require_campaign(db, campaign_id)
    public_payload = _create_public_party_payload(db, campaign_id)
    display.mode = "party"
    display.active_campaign_id = campaign_id
    display.active_session_id = None
    display.active_scene_id = None
    display.title = "Party"
    display.subtitle = campaign.name
    display.payload_json = json.dumps(public_payload)
    display.revision += 1
    display.updated_at = utc_now_z()


def _create_note_record(
    db: Session,
    *,
    campaign_id: str,
    title: str,
    private_body: str,
    tags: list[str] | str | None,
    session_id: UUID | str | None,
    scene_id: UUID | str | None,
    asset_id: UUID | str | None,
    source_kind: str,
    source_name: str,
    source_label: str | None,
) -> Note:
    now = utc_now_z()
    resolved_session_id, resolved_scene_id, resolved_asset_id = _validate_note_links(
        db,
        campaign_id,
        session_id=session_id,
        scene_id=scene_id,
        asset_id=asset_id,
    )
    source = _note_source_if_missing(db, campaign_id, kind=source_kind, name=source_name, now=now)
    note = Note(
        id=_new_id(),
        campaign_id=campaign_id,
        source_id=source.id,
        session_id=resolved_session_id,
        scene_id=resolved_scene_id,
        asset_id=resolved_asset_id,
        title=title,
        private_body=private_body,
        tags_json=json.dumps(_normalize_tags(tags)),
        source_label=source_label,
        created_at=now,
        updated_at=now,
    )
    db.add(note)
    return note


def _party_config_id(campaign_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"myroll:party-tracker:{campaign_id}"))


def _require_entity_kind(value: str) -> str:
    if value not in ENTITY_KINDS:
        raise api_error(400, "invalid_entity_kind", "Entity kind is invalid")
    return value


def _require_entity_visibility(value: str) -> str:
    if value not in ENTITY_VISIBILITIES:
        raise api_error(400, "invalid_entity_visibility", "Entity visibility is invalid")
    return value


def _require_field_type(value: str) -> str:
    if value not in CUSTOM_FIELD_TYPES:
        raise api_error(400, "invalid_custom_field_type", "Custom field type is invalid")
    return value


def _require_party_layout(value: str) -> str:
    if value not in PARTY_LAYOUTS:
        raise api_error(400, "invalid_party_layout", "Party layout is invalid")
    return value


def _normalize_field_key(value: str) -> str:
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    key = re.sub(r"[^a-z0-9_]", "", key)
    if not FIELD_KEY_RE.fullmatch(key):
        raise api_error(400, "invalid_custom_field_key", "Custom field key must be a lowercase slug")
    return key


def _normalize_entity_kinds(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values or ["pc"]:
        kind = _require_entity_kind(str(raw).strip())
        if kind not in seen:
            normalized.append(kind)
            seen.add(kind)
    if not normalized:
        raise api_error(400, "custom_field_applies_to_empty", "Custom field must apply to at least one entity kind")
    return normalized


def _normalize_options(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        option = str(raw).strip()[:80]
        if not option:
            continue
        key = option.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(option)
        if len(normalized) >= 30:
            break
    return normalized


def _parse_string_list_json(value: str | None) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if isinstance(item, str)]


def _validate_portrait_asset(db: Session, campaign_id: str, asset_id: UUID | str | None) -> Asset | None:
    if asset_id is None:
        return None
    asset = _require_asset(db, asset_id)
    if asset.campaign_id != campaign_id:
        raise api_error(400, "asset_campaign_mismatch", "Asset does not belong to campaign")
    if asset.kind not in IMAGE_ASSET_KINDS or not asset.mime_type.startswith("image/"):
        raise api_error(400, "asset_not_displayable_image", "Asset is not a displayable image")
    if asset.width is None or asset.height is None:
        raise api_error(400, "asset_missing_image_metadata", "Asset is missing image metadata")
    return asset


def _validate_entity_reference(db: Session, campaign_id: str, entity_id: str | None) -> Entity | None:
    if entity_id is None:
        return None
    entity = _require_entity(db, entity_id)
    if entity.campaign_id != campaign_id:
        raise api_error(400, "entity_campaign_mismatch", "Entity does not belong to campaign")
    return entity


def _field_options(field: CustomFieldDefinition) -> list[str]:
    return _parse_string_list_json(field.options_json)


def _field_applies_to(field: CustomFieldDefinition) -> list[str]:
    return _parse_string_list_json(field.applies_to_json)


def _field_default_value(field: CustomFieldDefinition) -> object | None:
    if field.default_value_json is None:
        return None
    try:
        return json.loads(field.default_value_json)
    except json.JSONDecodeError:
        return None


def _field_out(field: CustomFieldDefinition) -> CustomFieldDefinitionOut:
    return CustomFieldDefinitionOut(
        id=field.id,
        campaign_id=field.campaign_id,
        key=field.key,
        label=field.label,
        field_type=field.field_type,
        applies_to=_field_applies_to(field),
        required=field.required,
        default_value=_field_default_value(field),
        options=_field_options(field),
        public_by_default=field.public_by_default,
        sort_order=field.sort_order,
        created_at=field.created_at,
        updated_at=field.updated_at,
    )


def _value_for_field(db: Session, campaign_id: str, field: CustomFieldDefinition, value: object | None) -> object | None:
    field_type = _require_field_type(field.field_type)
    if value is None:
        return None
    if field_type == "short_text":
        return str(value).strip()[:240]
    if field_type == "long_text":
        return str(value)[:4000]
    if field_type == "number":
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as error:
            raise api_error(400, "invalid_field_value", "Number field value is invalid") from error
        if not math.isfinite(number):
            raise api_error(400, "invalid_field_value", "Number field value must be finite")
        return number
    if field_type == "boolean":
        if not isinstance(value, bool):
            raise api_error(400, "invalid_field_value", "Boolean field value is invalid")
        return value
    if field_type in {"select", "radio"}:
        option = str(value).strip()
        if option not in _field_options(field):
            raise api_error(400, "invalid_field_value", "Selected option is invalid")
        return option
    if field_type == "multi_select":
        if not isinstance(value, list):
            raise api_error(400, "invalid_field_value", "Multi-select field value is invalid")
        allowed = set(_field_options(field))
        selected: list[str] = []
        for raw in value:
            option = str(raw).strip()
            if option not in allowed:
                raise api_error(400, "invalid_field_value", "Selected option is invalid")
            if option not in selected:
                selected.append(option)
        return selected
    if field_type == "resource":
        if not isinstance(value, dict):
            raise api_error(400, "invalid_field_value", "Resource field value is invalid")
        try:
            current = float(value.get("current", 0))
            maximum_raw = value.get("max")
            maximum = float(maximum_raw) if maximum_raw is not None and maximum_raw != "" else None
        except (TypeError, ValueError) as error:
            raise api_error(400, "invalid_field_value", "Resource field value is invalid") from error
        if not math.isfinite(current) or (maximum is not None and not math.isfinite(maximum)):
            raise api_error(400, "invalid_field_value", "Resource values must be finite")
        payload: dict[str, object] = {"current": current}
        if maximum is not None:
            payload["max"] = maximum
        return payload
    if field_type == "image":
        asset = _validate_portrait_asset(db, campaign_id, str(value))
        return asset.id if asset else None
    raise api_error(400, "invalid_custom_field_type", "Custom field type is invalid")


def _validate_custom_field_definition_payload(
    db: Session,
    campaign_id: str,
    *,
    field_type: str,
    applies_to: list[str],
    options: list[str],
    default_value: object | None,
) -> tuple[str, list[str], list[str], object | None]:
    normalized_type = _require_field_type(field_type)
    normalized_applies_to = _normalize_entity_kinds(applies_to)
    normalized_options = _normalize_options(options)
    if normalized_type in {"select", "multi_select", "radio"} and not normalized_options:
        raise api_error(400, "custom_field_options_required", "Select-style fields require options")
    if normalized_type not in {"select", "multi_select", "radio"} and normalized_options:
        normalized_options = []
    fake_field = CustomFieldDefinition(
        id="validation",
        campaign_id=campaign_id,
        key="validation",
        label="Validation",
        field_type=normalized_type,
        applies_to_json=json.dumps(normalized_applies_to),
        required=False,
        default_value_json=None,
        options_json=json.dumps(normalized_options),
        public_by_default=False,
        sort_order=0,
        created_at=utc_now_z(),
        updated_at=utc_now_z(),
    )
    normalized_default = _value_for_field(db, campaign_id, fake_field, default_value) if default_value is not None else None
    return normalized_type, normalized_applies_to, normalized_options, normalized_default


def _field_values_for_entity(db: Session, entity: Entity) -> dict[str, object]:
    fields = {
        field.id: field
        for field in db.scalars(
            select(CustomFieldDefinition)
            .where(CustomFieldDefinition.campaign_id == entity.campaign_id)
            .order_by(CustomFieldDefinition.sort_order, CustomFieldDefinition.label, CustomFieldDefinition.id)
        )
    }
    values: dict[str, object] = {}
    for row in db.scalars(select(CustomFieldValue).where(CustomFieldValue.entity_id == entity.id)):
        field = fields.get(row.field_definition_id)
        if field is None:
            continue
        try:
            values[field.key] = json.loads(row.value_json)
        except json.JSONDecodeError:
            continue
    return values


def _entity_out(db: Session, entity: Entity) -> EntityOut:
    asset = db.get(Asset, entity.portrait_asset_id) if entity.portrait_asset_id else None
    return EntityOut(
        id=entity.id,
        campaign_id=entity.campaign_id,
        kind=entity.kind,
        name=entity.name,
        display_name=entity.display_name,
        visibility=entity.visibility,
        portrait_asset_id=entity.portrait_asset_id,
        portrait_asset_name=asset.name if asset else None,
        portrait_asset_visibility=asset.visibility if asset else None,
        tags=_parse_tags_json(entity.tags_json),
        notes=entity.notes,
        field_values=_field_values_for_entity(db, entity),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _entities_response(db: Session, campaign_id: str) -> EntitiesOut:
    entities = list(
        db.scalars(
            select(Entity)
            .where(Entity.campaign_id == campaign_id)
            .order_by(Entity.kind, Entity.name, Entity.id)
        )
    )
    updated_at = max((entity.updated_at for entity in entities), default=utc_now_z())
    return EntitiesOut(entities=[_entity_out(db, entity) for entity in entities], updated_at=updated_at)


def _custom_fields_response(db: Session, campaign_id: str) -> CustomFieldsOut:
    fields = list(
        db.scalars(
            select(CustomFieldDefinition)
            .where(CustomFieldDefinition.campaign_id == campaign_id)
            .order_by(CustomFieldDefinition.sort_order, CustomFieldDefinition.label, CustomFieldDefinition.id)
        )
    )
    updated_at = max((field.updated_at for field in fields), default=utc_now_z())
    return CustomFieldsOut(fields=[_field_out(field) for field in fields], updated_at=updated_at)


def _party_config_for_campaign(db: Session, campaign_id: str) -> PartyTrackerConfig | None:
    return db.scalars(select(PartyTrackerConfig).where(PartyTrackerConfig.campaign_id == campaign_id)).one_or_none()


def _ensure_party_config(db: Session, campaign_id: str) -> PartyTrackerConfig:
    config = _party_config_for_campaign(db, campaign_id)
    if config is not None:
        return config
    now = utc_now_z()
    config = PartyTrackerConfig(
        id=_party_config_id(campaign_id),
        campaign_id=campaign_id,
        layout="standard",
        created_at=now,
        updated_at=now,
    )
    db.add(config)
    db.flush()
    return config


def _party_tracker_out(db: Session, campaign_id: str) -> PartyTrackerOut:
    config = _party_config_for_campaign(db, campaign_id)
    if config is None:
        now = utc_now_z()
        return PartyTrackerOut(id=_party_config_id(campaign_id), campaign_id=campaign_id, layout="standard", members=[], fields=[], updated_at=now)
    members = list(
        db.scalars(
            select(PartyTrackerMember)
            .where(PartyTrackerMember.config_id == config.id)
            .order_by(PartyTrackerMember.sort_order, PartyTrackerMember.id)
        )
    )
    fields = list(
        db.scalars(
            select(PartyTrackerField)
            .where(PartyTrackerField.config_id == config.id)
            .order_by(PartyTrackerField.sort_order, PartyTrackerField.id)
        )
    )
    member_out: list[PartyMemberOut] = []
    for member in members:
        entity = db.get(Entity, member.entity_id)
        if entity is not None:
            member_out.append(PartyMemberOut(id=member.id, entity_id=member.entity_id, sort_order=member.sort_order, entity=_entity_out(db, entity)))
    field_out: list[PartyFieldOut] = []
    for party_field in fields:
        field = db.get(CustomFieldDefinition, party_field.field_definition_id)
        if field is not None:
            field_out.append(
                PartyFieldOut(
                    id=party_field.id,
                    field_definition_id=party_field.field_definition_id,
                    sort_order=party_field.sort_order,
                    public_visible=party_field.public_visible,
                    field=_field_out(field),
                )
            )
    updated_candidates = [config.updated_at, *(member.entity.updated_at for member in member_out), *(field.field.updated_at for field in field_out)]
    return PartyTrackerOut(
        id=config.id,
        campaign_id=campaign_id,
        layout=config.layout,
        members=member_out,
        fields=field_out,
        updated_at=max(updated_candidates),
    )


def _require_combat_status(value: str) -> str:
    if value not in COMBAT_STATUSES:
        raise api_error(400, "invalid_combat_status", "Combat encounter status is invalid")
    return value


def _require_combat_disposition(value: str) -> str:
    if value not in COMBAT_DISPOSITIONS:
        raise api_error(400, "invalid_combatant_disposition", "Combatant disposition is invalid")
    return value


def _validate_combat_links(
    db: Session,
    campaign_id: str,
    *,
    session_id: UUID | str | None,
    scene_id: UUID | str | None,
) -> tuple[str | None, str | None]:
    resolved_session_id = str(session_id) if session_id is not None else None
    resolved_scene_id = str(scene_id) if scene_id is not None else None
    if resolved_session_id is not None:
        session = _require_session(db, resolved_session_id)
        if session.campaign_id != campaign_id:
            raise api_error(400, "session_campaign_mismatch", "Session does not belong to campaign")
    if resolved_scene_id is not None:
        scene = _require_scene(db, resolved_scene_id)
        if scene.campaign_id != campaign_id:
            raise api_error(400, "scene_campaign_mismatch", "Scene does not belong to campaign")
    return resolved_session_id, resolved_scene_id


def _validate_combatant_refs(
    db: Session,
    campaign_id: str,
    *,
    entity_id: UUID | str | None,
    token_id: UUID | str | None,
) -> tuple[Entity | None, SceneMapToken | None]:
    entity = _validate_entity_reference(db, campaign_id, str(entity_id) if entity_id is not None else None)
    token = None
    if token_id is not None:
        token = _require_token(db, token_id)
        if token.campaign_id != campaign_id:
            raise api_error(400, "token_campaign_mismatch", "Token does not belong to campaign")
    return entity, token


def _default_combatant_name(entity: Entity | None, token: SceneMapToken | None, fallback: str | None) -> str:
    if fallback:
        return fallback
    if entity is not None:
        return entity.display_name or entity.name
    if token is not None:
        return token.name
    return "Combatant"


def _default_combatant_disposition(entity: Entity | None, fallback: str | None) -> str:
    if fallback is not None:
        return _require_combat_disposition(fallback)
    if entity is not None and entity.kind == "pc":
        return "pc"
    if entity is not None and entity.kind in {"npc", "creature"}:
        return "enemy"
    return "enemy"


def _default_public_visible(entity: Entity | None, token: SceneMapToken | None, explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    if entity is not None and entity.visibility == "public_known":
        return True
    if token is not None and token.visibility == "player_visible":
        return True
    return False


def _combatants_for_encounter(db: Session, encounter_id: str) -> list[Combatant]:
    return list(
        db.scalars(
            select(Combatant)
            .where(Combatant.encounter_id == encounter_id)
            .order_by(Combatant.order_index, Combatant.initiative.desc().nullslast(), Combatant.name, Combatant.id)
        )
    )


def _combatant_portrait_asset(db: Session, combatant: Combatant) -> Asset | None:
    entity = db.get(Entity, combatant.entity_id) if combatant.entity_id else None
    token = db.get(SceneMapToken, combatant.token_id) if combatant.token_id else None
    asset = db.get(Asset, entity.portrait_asset_id) if entity and entity.portrait_asset_id else None
    if asset is None and token and token.asset_id:
        asset = db.get(Asset, token.asset_id)
    if asset is None or asset.kind not in IMAGE_ASSET_KINDS or not asset.mime_type.startswith("image/"):
        return None
    return asset


def _combatant_out(db: Session, combatant: Combatant) -> CombatantOut:
    portrait = _combatant_portrait_asset(db, combatant)
    return CombatantOut(
        id=combatant.id,
        campaign_id=combatant.campaign_id,
        encounter_id=combatant.encounter_id,
        entity_id=combatant.entity_id,
        token_id=combatant.token_id,
        name=combatant.name,
        disposition=combatant.disposition,
        initiative=combatant.initiative,
        order_index=combatant.order_index,
        armor_class=combatant.armor_class,
        hp_current=combatant.hp_current,
        hp_max=combatant.hp_max,
        hp_temp=combatant.hp_temp,
        conditions=_parse_json_list(combatant.conditions_json),
        public_status=_parse_public_status_json(combatant.public_status_json),
        notes=combatant.notes,
        public_visible=combatant.public_visible,
        is_defeated=combatant.is_defeated,
        portrait_asset_id=portrait.id if portrait else None,
        portrait_asset_name=portrait.name if portrait else None,
        created_at=combatant.created_at,
        updated_at=combatant.updated_at,
    )


def _combat_encounter_out(db: Session, encounter: CombatEncounter) -> CombatEncounterOut:
    return CombatEncounterOut(
        id=encounter.id,
        campaign_id=encounter.campaign_id,
        session_id=encounter.session_id,
        scene_id=encounter.scene_id,
        title=encounter.title,
        status=encounter.status,
        round=encounter.round,
        active_combatant_id=encounter.active_combatant_id,
        combatants=[_combatant_out(db, combatant) for combatant in _combatants_for_encounter(db, encounter.id)],
        created_at=encounter.created_at,
        updated_at=encounter.updated_at,
    )


def _combat_encounters_response(db: Session, campaign_id: str) -> CombatEncountersOut:
    encounters = list(
        db.scalars(
            select(CombatEncounter)
            .where(CombatEncounter.campaign_id == campaign_id)
            .order_by(CombatEncounter.updated_at.desc(), CombatEncounter.title, CombatEncounter.id)
        )
    )
    updated_at = max((encounter.updated_at for encounter in encounters), default=utc_now_z())
    return CombatEncountersOut(encounters=[_combat_encounter_out(db, encounter) for encounter in encounters], updated_at=updated_at)


def _apply_combatant_patch_data(db: Session, combatant: Combatant, data: dict[str, object]) -> None:
    if "entity_id" in data or "token_id" in data:
        entity, token = _validate_combatant_refs(
            db,
            combatant.campaign_id,
            entity_id=data.get("entity_id", combatant.entity_id),
            token_id=data.get("token_id", combatant.token_id),
        )
        combatant.entity_id = entity.id if entity else None
        combatant.token_id = token.id if token else None
    if "disposition" in data and data["disposition"] is not None:
        combatant.disposition = _require_combat_disposition(str(data["disposition"]))
    if "conditions" in data and data["conditions"] is not None:
        combatant.conditions_json = json.dumps(data["conditions"])
    if "public_status" in data and data["public_status"] is not None:
        combatant.public_status_json = json.dumps(_normalize_public_status(data["public_status"]))  # type: ignore[arg-type]
    for key in ("initiative", "armor_class", "hp_current", "hp_max"):
        if key in data:
            setattr(combatant, key, data[key])
    for key in ("name", "order_index", "hp_temp", "notes", "public_visible", "is_defeated"):
        if key in data and data[key] is not None:
            setattr(combatant, key, data[key])
    combatant.updated_at = utc_now_z()


def _advance_combat_turn(encounter: CombatEncounter, direction: int, combatants: list[Combatant]) -> None:
    eligible = [combatant for combatant in combatants if not combatant.is_defeated]
    if not eligible:
        encounter.active_combatant_id = None
        encounter.updated_at = utc_now_z()
        return
    current_index = next((index for index, combatant in enumerate(eligible) if combatant.id == encounter.active_combatant_id), None)
    if current_index is None:
        target = eligible[0] if direction >= 0 else eligible[-1]
    elif direction >= 0:
        if current_index + 1 >= len(eligible):
            target = eligible[0]
            encounter.round += 1
        else:
            target = eligible[current_index + 1]
    else:
        if current_index - 1 < 0:
            target = eligible[-1]
            encounter.round = max(1, encounter.round - 1)
        else:
            target = eligible[current_index - 1]
    encounter.active_combatant_id = target.id
    encounter.updated_at = utc_now_z()


def _initiative_portrait_payload(db: Session, combatant: Combatant) -> tuple[str | None, str | None]:
    asset = _combatant_portrait_asset(db, combatant)
    if (
        asset is not None
        and asset.visibility == "public_displayable"
        and asset.kind in IMAGE_ASSET_KINDS
        and asset.mime_type.startswith("image/")
    ):
        return asset.id, f"/api/player-display/assets/{asset.id}/blob"
    return None, None


def _create_public_initiative_payload(db: Session, encounter: CombatEncounter) -> dict[str, object]:
    public_combatants: list[dict[str, object]] = []
    for combatant in _combatants_for_encounter(db, encounter.id):
        if not combatant.public_visible:
            continue
        portrait_asset_id, portrait_url = _initiative_portrait_payload(db, combatant)
        public_combatants.append(
            {
                "id": combatant.id,
                "name": combatant.name,
                "disposition": combatant.disposition,
                "initiative": combatant.initiative,
                "is_active": combatant.id == encounter.active_combatant_id,
                "portrait_asset_id": portrait_asset_id,
                "portrait_url": portrait_url,
                "public_status": _parse_public_status_json(combatant.public_status_json),
            }
        )
    return {
        "type": "initiative",
        "encounter_id": encounter.id,
        "round": encounter.round,
        "active_combatant_id": encounter.active_combatant_id,
        "combatants": public_combatants,
    }


def _apply_initiative_display(display: PlayerDisplayRuntime, db: Session, encounter: CombatEncounter) -> None:
    _require_campaign(db, encounter.campaign_id)
    public_payload = _create_public_initiative_payload(db, encounter)
    display.mode = "initiative"
    display.active_campaign_id = encounter.campaign_id
    display.active_session_id = encounter.session_id
    display.active_scene_id = encounter.scene_id
    display.title = "Initiative"
    display.subtitle = encounter.title
    display.payload_json = json.dumps(public_payload)
    display.revision += 1
    display.updated_at = utc_now_z()


def _asset_out(asset: Asset) -> AssetOut:
    return AssetOut(
        id=asset.id,
        campaign_id=asset.campaign_id,
        kind=asset.kind,
        visibility=asset.visibility,
        name=asset.name,
        mime_type=asset.mime_type,
        byte_size=asset.byte_size,
        checksum=asset.checksum,
        relative_path=asset.relative_path,
        original_filename=asset.original_filename,
        width=asset.width,
        height=asset.height,
        duration_ms=asset.duration_ms,
        tags=_parse_tags_json(asset.tags_json),
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def _token_asset_url(asset_id: str) -> str:
    return f"/api/assets/{asset_id}/blob"


def _token_out(db: Session, token: SceneMapToken) -> TokenOut:
    asset = db.get(Asset, token.asset_id) if token.asset_id else None
    return TokenOut(
        id=token.id,
        campaign_id=token.campaign_id,
        scene_id=token.scene_id,
        scene_map_id=token.scene_map_id,
        entity_id=token.entity_id,
        asset_id=token.asset_id,
        asset_name=asset.name if asset else None,
        asset_visibility=asset.visibility if asset else None,
        asset_url=_token_asset_url(token.asset_id) if asset else None,
        name=token.name,
        x=token.x,
        y=token.y,
        width=token.width,
        height=token.height,
        rotation=token.rotation,
        z_index=token.z_index,
        visibility=token.visibility,
        label_visibility=token.label_visibility,
        shape=token.shape,
        color=token.color,
        border_color=token.border_color,
        opacity=token.opacity,
        status=_parse_json_list(token.status_json),
        created_at=token.created_at,
        updated_at=token.updated_at,
    )


def _tokens_response(db: Session, scene_map_id: str) -> TokensOut:
    tokens = list(
        db.scalars(
            select(SceneMapToken)
            .where(SceneMapToken.scene_map_id == scene_map_id)
            .order_by(SceneMapToken.z_index, SceneMapToken.name, SceneMapToken.id)
        )
    )
    updated_at = max((token.updated_at for token in tokens), default=utc_now_z())
    return TokensOut(tokens=[_token_out(db, token) for token in tokens], updated_at=updated_at)


def _create_asset_record(
    db: Session,
    campaign_id: UUID | str,
    *,
    kind: str,
    visibility: str,
    name: str | None,
    tags: list[str] | str | None,
    stored,  # noqa: ANN001
) -> Asset:
    now = utc_now_z()
    asset = Asset(
        id=_new_id(),
        campaign_id=str(campaign_id),
        kind=_require_image_asset_kind(kind),
        visibility=_require_asset_visibility(visibility),
        name=_clean_asset_name(name, stored.original_filename),
        mime_type=stored.mime_type,
        byte_size=stored.byte_size,
        checksum=stored.checksum,
        relative_path=stored.relative_path,
        original_filename=stored.original_filename,
        width=stored.width,
        height=stored.height,
        duration_ms=None,
        tags_json=json.dumps(_normalize_tags(tags)),
        created_at=now,
        updated_at=now,
    )
    db.add(asset)
    return asset


def _map_asset_url(asset_id: str) -> str:
    return f"/api/assets/{asset_id}/blob"


def _map_out(db: Session, campaign_map: CampaignMap) -> MapOut:
    asset = db.get(Asset, campaign_map.asset_id)
    return MapOut(
        id=campaign_map.id,
        campaign_id=campaign_map.campaign_id,
        asset_id=campaign_map.asset_id,
        asset_name=asset.name if asset else None,
        asset_visibility=asset.visibility if asset else None,
        asset_url=_map_asset_url(campaign_map.asset_id),
        name=campaign_map.name,
        width=campaign_map.width,
        height=campaign_map.height,
        grid_enabled=campaign_map.grid_enabled,
        grid_size_px=campaign_map.grid_size_px,
        grid_offset_x=campaign_map.grid_offset_x,
        grid_offset_y=campaign_map.grid_offset_y,
        grid_color=campaign_map.grid_color,
        grid_opacity=campaign_map.grid_opacity,
        created_at=campaign_map.created_at,
        updated_at=campaign_map.updated_at,
    )


def _bundled_grid_out(bundled_map: BundledMap) -> BundledGridOut:
    return BundledGridOut(
        cols=bundled_map.grid.cols,
        rows=bundled_map.grid.rows,
        feet_per_cell=bundled_map.grid.feet_per_cell,
        px_per_cell=bundled_map.grid.px_per_cell,
        offset_x=bundled_map.grid.offset_x,
        offset_y=bundled_map.grid.offset_y,
    )


def _bundled_map_out(pack_id: str, bundled_map: BundledMap) -> BundledMapOut:
    return BundledMapOut(
        id=bundled_map.id,
        pack_id=pack_id,
        title=bundled_map.title,
        collection=bundled_map.collection,
        group=bundled_map.group,
        category_key=bundled_map.category_key,
        category_label=bundled_map.category_label,
        width=bundled_map.width,
        height=bundled_map.height,
        tags=list(bundled_map.tags),
        grid=_bundled_grid_out(bundled_map),
    )


def _create_campaign_map_for_asset(
    db: Session,
    campaign_id: UUID | str,
    asset: Asset,
    *,
    name: str | None,
    map_id: str | None = None,
    grid_enabled: bool = False,
    grid_size_px: int = 70,
    grid_offset_x: float = 0,
    grid_offset_y: float = 0,
    grid_color: str = "#FFFFFF",
    grid_opacity: float = 0.35,
) -> tuple[CampaignMap, bool]:
    if asset.width is None or asset.height is None:
        raise api_error(400, "asset_missing_image_metadata", "Asset is missing image metadata")
    if map_id is not None:
        existing = db.get(CampaignMap, map_id)
        if existing is not None:
            return existing, False
    campaign_map = CampaignMap(
        id=map_id or _new_id(),
        campaign_id=str(campaign_id),
        asset_id=asset.id,
        name=_clean_asset_name(name, asset.name),
        width=asset.width,
        height=asset.height,
        grid_enabled=grid_enabled,
        grid_size_px=grid_size_px,
        grid_offset_x=grid_offset_x,
        grid_offset_y=grid_offset_y,
        grid_color=grid_color,
        grid_opacity=grid_opacity,
        created_at=utc_now_z(),
        updated_at=utc_now_z(),
    )
    db.add(campaign_map)
    return campaign_map, True


def _batch_error(filename: str, code: str, message: str) -> AssetBatchItemOut:
    return AssetBatchItemOut(filename=filename, error=AssetBatchErrorOut(code=code, message=message))


def _private_fog_mask_url(fog: SceneMapFogMask) -> str:
    return f"/api/scene-maps/{fog.scene_map_id}/fog/mask?revision={fog.revision}"


def _public_fog_mask_url(fog: SceneMapFogMask) -> str:
    return f"/api/player-display/fog/{fog.id}/mask?revision={fog.revision}"


def _fog_out(fog: SceneMapFogMask) -> FogMaskOut:
    return FogMaskOut(
        id=fog.id,
        campaign_id=fog.campaign_id,
        scene_id=fog.scene_id,
        scene_map_id=fog.scene_map_id,
        enabled=fog.enabled,
        revision=fog.revision,
        width=fog.width,
        height=fog.height,
        mask_url=_private_fog_mask_url(fog),
        updated_at=fog.updated_at,
    )


def _scene_map_out(db: Session, scene_map: SceneMap) -> SceneMapOut:
    campaign_map = _require_map(db, scene_map.map_id)
    return SceneMapOut(
        id=scene_map.id,
        campaign_id=scene_map.campaign_id,
        scene_id=scene_map.scene_id,
        map_id=scene_map.map_id,
        is_active=scene_map.is_active,
        player_fit_mode=scene_map.player_fit_mode,
        player_grid_visible=scene_map.player_grid_visible,
        map=_map_out(db, campaign_map),
        created_at=scene_map.created_at,
        updated_at=scene_map.updated_at,
    )


def _fog_for_scene_map(db: Session, scene_map_id: str) -> SceneMapFogMask | None:
    return db.scalars(select(SceneMapFogMask).where(SceneMapFogMask.scene_map_id == scene_map_id)).one_or_none()


def _tokens_for_scene_map(db: Session, scene_map_id: str) -> list[SceneMapToken]:
    return list(
        db.scalars(
            select(SceneMapToken)
            .where(SceneMapToken.scene_map_id == scene_map_id)
            .order_by(SceneMapToken.z_index, SceneMapToken.name, SceneMapToken.id)
        )
    )


def _validate_token_asset(db: Session, campaign_id: str, asset_id: UUID | str | None) -> Asset | None:
    if asset_id is None:
        return None
    asset = _require_asset(db, asset_id)
    if asset.campaign_id != campaign_id:
        raise api_error(400, "asset_campaign_mismatch", "Asset does not belong to campaign")
    if asset.kind not in IMAGE_ASSET_KINDS or not asset.mime_type.startswith("image/"):
        raise api_error(400, "asset_not_displayable_image", "Asset is not a displayable image")
    if asset.width is None or asset.height is None:
        raise api_error(400, "asset_missing_image_metadata", "Asset is missing image metadata")
    return asset


def _normalize_token_payload(data: dict[str, object], campaign_map: CampaignMap) -> dict[str, object]:
    normalized = dict(data)
    if "visibility" in normalized and normalized["visibility"] is not None:
        normalized["visibility"] = _require_token_visibility(str(normalized["visibility"]))
    if "label_visibility" in normalized and normalized["label_visibility"] is not None:
        normalized["label_visibility"] = _require_label_visibility(str(normalized["label_visibility"]))
    if "shape" in normalized and normalized["shape"] is not None:
        normalized["shape"] = _require_token_shape(str(normalized["shape"]))
    if "color" in normalized and normalized["color"] is not None:
        normalized["color"] = _normalize_token_color(str(normalized["color"]))
    if "border_color" in normalized and normalized["border_color"] is not None:
        normalized["border_color"] = _normalize_token_color(str(normalized["border_color"]))
    if "rotation" in normalized and normalized["rotation"] is not None:
        normalized["rotation"] = _normalize_rotation(float(normalized["rotation"]))
    if "x" in normalized and normalized["x"] is not None:
        x = _require_finite(float(normalized["x"]), "invalid_token_coordinates", "Token coordinates must be finite")
        normalized["x"] = _clamp(x, 0, campaign_map.width)
    if "y" in normalized and normalized["y"] is not None:
        y = _require_finite(float(normalized["y"]), "invalid_token_coordinates", "Token coordinates must be finite")
        normalized["y"] = _clamp(y, 0, campaign_map.height)
    if "width" in normalized and normalized["width"] is not None:
        normalized["width"] = _require_finite(float(normalized["width"]), "invalid_token_size", "Token size must be finite")
    if "height" in normalized and normalized["height"] is not None:
        normalized["height"] = _require_finite(float(normalized["height"]), "invalid_token_size", "Token size must be finite")
    return normalized


def _ensure_fog_mask(db: Session, settings, scene_map: SceneMap) -> SceneMapFogMask:  # noqa: ANN001
    campaign_map = _require_map(db, scene_map.map_id)
    fog = _fog_for_scene_map(db, scene_map.id)
    if fog is not None:
        if fog.width != campaign_map.width or fog.height != campaign_map.height:
            raise api_error(409, "fog_mask_dimension_mismatch", "Fog mask dimensions do not match map")
        fog.enabled = True
        fog.updated_at = utc_now_z()
        try:
            path = resolve_fog_path(settings, fog.relative_path)
            if not path.exists() or not path.is_file():
                create_hidden_mask(settings, fog.relative_path, fog.width, fog.height)
        except FogStoreError as error:
            raise api_error(error.status_code, error.code, error.message) from error
        return fog

    now = utc_now_z()
    fog = SceneMapFogMask(
        id=_new_id(),
        campaign_id=scene_map.campaign_id,
        scene_id=scene_map.scene_id,
        scene_map_id=scene_map.id,
        width=campaign_map.width,
        height=campaign_map.height,
        relative_path="",
        enabled=True,
        revision=1,
        created_at=now,
        updated_at=now,
    )
    fog.relative_path = fog_relative_path(fog.id)
    try:
        create_hidden_mask(settings, fog.relative_path, fog.width, fog.height)
    except FogStoreError as error:
        raise api_error(error.status_code, error.code, error.message) from error
    db.add(fog)
    db.flush()
    return fog


def _public_fog_payload(db: Session, scene_map: SceneMap) -> dict[str, object] | None:
    fog = _fog_for_scene_map(db, scene_map.id)
    if fog is None or not fog.enabled:
        return None
    campaign_map = _require_map(db, scene_map.map_id)
    if fog.width != campaign_map.width or fog.height != campaign_map.height:
        raise api_error(409, "fog_mask_dimension_mismatch", "Fog mask dimensions do not match map")
    return {
        "enabled": True,
        "mask_id": fog.id,
        "mask_url": _public_fog_mask_url(fog),
        "revision": fog.revision,
        "width": fog.width,
        "height": fog.height,
    }


def _load_visible_fog_mask(settings, fog: SceneMapFogMask | None, width: int, height: int):  # noqa: ANN001
    if fog is None or not fog.enabled:
        return None
    if fog.width != width or fog.height != height:
        raise api_error(409, "fog_mask_dimension_mismatch", "Fog mask dimensions do not match map")
    try:
        return load_mask(settings, fog.relative_path, fog.width, fog.height)
    except FogStoreError:
        return None


def _is_fog_point_visible(mask, x: float, y: float, width: int, height: int) -> bool:  # noqa: ANN001
    if mask is None or width <= 0 or height <= 0:
        return False
    sample_x = int(_clamp(round(x), 0, width - 1))
    sample_y = int(_clamp(round(y), 0, height - 1))
    return int(mask.getpixel((sample_x, sample_y))) >= 128


def _public_token_payload(
    db: Session,
    token: SceneMapToken,
    *,
    fog_mask,  # noqa: ANN001
    map_width: int,
    map_height: int,
) -> dict[str, object] | None:
    if token.visibility == "gm_only":
        return None
    if token.visibility == "hidden_until_revealed" and not _is_fog_point_visible(fog_mask, token.x, token.y, map_width, map_height):
        return None

    payload: dict[str, object] = {
        "id": token.id,
        "entity_id": token.entity_id,
        "name": token.name if token.label_visibility == "player_visible" else None,
        "x": token.x,
        "y": token.y,
        "width": token.width,
        "height": token.height,
        "rotation": token.rotation,
        "style": {
            "shape": token.shape,
            "color": token.color,
            "border_color": token.border_color,
            "opacity": token.opacity,
        },
        "status": _parse_json_list(token.status_json),
    }
    asset = db.get(Asset, token.asset_id) if token.asset_id else None
    if (
        asset is not None
        and asset.visibility == "public_displayable"
        and asset.kind in IMAGE_ASSET_KINDS
        and asset.mime_type.startswith("image/")
        and asset.width is not None
        and asset.height is not None
    ):
        payload["asset_id"] = asset.id
        payload["asset_url"] = f"/api/player-display/assets/{asset.id}/blob"
        payload["mime_type"] = asset.mime_type
        payload["asset_width"] = asset.width
        payload["asset_height"] = asset.height
    else:
        payload["asset_id"] = None
        payload["asset_url"] = None
    return payload


def _public_tokens_payload(db: Session, settings, scene_map: SceneMap, campaign_map: CampaignMap) -> list[dict[str, object]]:  # noqa: ANN001
    fog = _fog_for_scene_map(db, scene_map.id)
    fog_mask = _load_visible_fog_mask(settings, fog, campaign_map.width, campaign_map.height)
    public_tokens: list[dict[str, object]] = []
    for token in _tokens_for_scene_map(db, scene_map.id):
        payload = _public_token_payload(
            db,
            token,
            fog_mask=fog_mask,
            map_width=campaign_map.width,
            map_height=campaign_map.height,
        )
        if payload is not None:
            public_tokens.append(payload)
    return public_tokens


def _create_public_map_payload(db: Session, settings, scene_map: SceneMap) -> dict[str, object]:  # noqa: ANN001
    campaign_map = _require_map(db, scene_map.map_id)
    asset = _require_asset(db, campaign_map.asset_id)
    if asset.visibility != "public_displayable":
        raise api_error(400, "asset_not_public_displayable", "Asset is not public displayable")
    if asset.kind != "map_image" or not asset.mime_type.startswith("image/"):
        raise api_error(400, "asset_not_displayable_map", "Asset is not a displayable map")
    if asset.width is None or asset.height is None:
        raise api_error(400, "asset_missing_image_metadata", "Asset is missing image metadata")

    public_payload: dict[str, object] = {
        "type": "map",
        "scene_map_id": scene_map.id,
        "map_id": campaign_map.id,
        "asset_id": asset.id,
        "asset_url": f"/api/player-display/assets/{asset.id}/blob",
        "mime_type": asset.mime_type,
        "width": campaign_map.width,
        "height": campaign_map.height,
        "title": campaign_map.name,
        "fit_mode": scene_map.player_fit_mode,
        "grid": {
            "type": "square",
            "visible": scene_map.player_grid_visible and campaign_map.grid_enabled,
            "size_px": campaign_map.grid_size_px,
            "offset_x": campaign_map.grid_offset_x,
            "offset_y": campaign_map.grid_offset_y,
            "color": campaign_map.grid_color,
            "opacity": campaign_map.grid_opacity,
        },
        "tokens": _public_tokens_payload(db, settings, scene_map, campaign_map),
    }
    fog_payload = _public_fog_payload(db, scene_map)
    if fog_payload is not None:
        public_payload["fog"] = fog_payload
    return public_payload


def _canonical_json(value: dict[str, object]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _public_payload_before_token_mutation(db: Session, settings, scene_map: SceneMap) -> dict[str, object] | None:  # noqa: ANN001
    display = db.get(PlayerDisplayRuntime, PLAYER_DISPLAY_ID)
    payload = _parse_json_object(display.payload_json) if display else {}
    if display is None or display.mode != "map" or payload.get("scene_map_id") != scene_map.id:
        return None
    return _create_public_map_payload(db, settings, scene_map)


def _status_json(value: list[dict[str, object]] | None) -> str:
    return json.dumps(value or [])


def _apply_token_data(
    db: Session,
    token: SceneMapToken,
    campaign_map: CampaignMap,
    data: dict[str, object],
) -> None:
    normalized = _normalize_token_payload(data, campaign_map)
    if "asset_id" in data:
        asset_id = data["asset_id"]
        _validate_token_asset(db, token.campaign_id, asset_id if asset_id is not None else None)
        token.asset_id = str(asset_id) if asset_id is not None else None
    if "status" in normalized and normalized["status"] is not None:
        token.status_json = _status_json(normalized["status"])  # type: ignore[arg-type]
    if "entity_id" in normalized:
        entity_id = normalized["entity_id"] if normalized["entity_id"] is None else str(normalized["entity_id"])
        _validate_entity_reference(db, token.campaign_id, entity_id)
        token.entity_id = entity_id
    for key in (
        "name",
        "x",
        "y",
        "width",
        "height",
        "rotation",
        "z_index",
        "visibility",
        "label_visibility",
        "shape",
        "color",
        "border_color",
        "opacity",
    ):
        if key in normalized and normalized[key] is not None:
            setattr(token, key, normalized[key])
    token.updated_at = utc_now_z()


def _activate_scene_map(db: Session, scene_map: SceneMap) -> None:
    now = utc_now_z()
    db.execute(
        update(SceneMap)
        .where(SceneMap.scene_id == scene_map.scene_id, SceneMap.is_active.is_(True))
        .values(is_active=False, updated_at=now)
    )
    db.flush()
    scene_map.is_active = True
    scene_map.updated_at = now


def _runtime_row(db: Session) -> AppRuntime:
    runtime = db.get(AppRuntime, RUNTIME_ID)
    if runtime is None:
        runtime = AppRuntime(
            id=RUNTIME_ID,
            active_campaign_id=None,
            active_session_id=None,
            active_scene_id=None,
            updated_at=utc_now_z(),
        )
        db.add(runtime)
        db.flush()
    return runtime


def _runtime_response(db: Session) -> RuntimeOut:
    runtime = db.get(AppRuntime, RUNTIME_ID)
    if runtime is None:
        return RuntimeOut(
            active_campaign_id=None,
            active_campaign_name=None,
            active_session_id=None,
            active_session_title=None,
            active_scene_id=None,
            active_scene_title=None,
            updated_at=utc_now_z(),
        )

    campaign = db.get(Campaign, runtime.active_campaign_id) if runtime.active_campaign_id else None
    session = db.get(CampaignSession, runtime.active_session_id) if runtime.active_session_id else None
    scene = db.get(Scene, runtime.active_scene_id) if runtime.active_scene_id else None
    return RuntimeOut(
        active_campaign_id=runtime.active_campaign_id,
        active_campaign_name=campaign.name if campaign else None,
        active_session_id=runtime.active_session_id,
        active_session_title=session.title if session else None,
        active_scene_id=runtime.active_scene_id,
        active_scene_title=scene.title if scene else None,
        updated_at=runtime.updated_at,
    )


def _parse_json_object(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _player_display_row(db: Session) -> PlayerDisplayRuntime:
    runtime = db.get(PlayerDisplayRuntime, PLAYER_DISPLAY_ID)
    if runtime is None:
        runtime = PlayerDisplayRuntime(
            id=PLAYER_DISPLAY_ID,
            mode="blackout",
            active_campaign_id=None,
            active_session_id=None,
            active_scene_id=None,
            title=None,
            subtitle=None,
            payload_json="{}",
            revision=1,
            identify_revision=0,
            identify_until=None,
            updated_at=utc_now_z(),
        )
        db.add(runtime)
        db.flush()
    return runtime


def _player_display_response(db: Session) -> PlayerDisplayOut:
    display = db.get(PlayerDisplayRuntime, PLAYER_DISPLAY_ID)
    if display is None:
        return PlayerDisplayOut(
            mode="blackout",
            title=None,
            subtitle=None,
            active_campaign_id=None,
            active_campaign_name=None,
            active_session_id=None,
            active_session_title=None,
            active_scene_id=None,
            active_scene_title=None,
            payload={},
            revision=1,
            identify_revision=0,
            identify_until=None,
            updated_at=utc_now_z(),
        )

    campaign = db.get(Campaign, display.active_campaign_id) if display.active_campaign_id else None
    session = db.get(CampaignSession, display.active_session_id) if display.active_session_id else None
    scene = db.get(Scene, display.active_scene_id) if display.active_scene_id else None
    return PlayerDisplayOut(
        mode=display.mode,
        title=display.title,
        subtitle=display.subtitle,
        active_campaign_id=display.active_campaign_id,
        active_campaign_name=campaign.name if campaign else None,
        active_session_id=display.active_session_id,
        active_session_title=session.title if session else None,
        active_scene_id=display.active_scene_id,
        active_scene_title=scene.title if scene else None,
        payload=_parse_json_object(display.payload_json),
        revision=display.revision,
        identify_revision=display.identify_revision,
        identify_until=display.identify_until,
        updated_at=display.updated_at,
    )


def _display_subtitle(campaign: Campaign | None, session: CampaignSession | None) -> str | None:
    if session is not None:
        return session.title
    if campaign is not None:
        return campaign.name
    return None


def _apply_scene_title(display: PlayerDisplayRuntime, db: Session, scene: Scene) -> None:
    campaign = db.get(Campaign, scene.campaign_id)
    session = db.get(CampaignSession, scene.session_id) if scene.session_id else None
    display.mode = "scene_title"
    display.active_campaign_id = scene.campaign_id
    display.active_session_id = scene.session_id
    display.active_scene_id = scene.id
    display.title = scene.title
    display.subtitle = _display_subtitle(campaign, session)
    display.payload_json = "{}"
    display.revision += 1
    display.updated_at = utc_now_z()


def _apply_image_display(display: PlayerDisplayRuntime, db: Session, asset: Asset, payload: ShowImageIn) -> None:
    if asset.visibility != "public_displayable":
        raise api_error(400, "asset_not_public_displayable", "Asset is not public displayable")
    if asset.kind not in IMAGE_ASSET_KINDS or not asset.mime_type.startswith("image/"):
        raise api_error(400, "asset_not_displayable_image", "Asset is not a displayable image")
    if asset.width is None or asset.height is None:
        raise api_error(400, "asset_missing_image_metadata", "Asset is missing image metadata")
    if payload.fit_mode not in DISPLAY_FIT_MODES:
        raise api_error(400, "invalid_fit_mode", "Fit mode is invalid")

    campaign = db.get(Campaign, asset.campaign_id)
    title = payload.title or asset.name
    public_payload = {
        "type": "image",
        "asset_id": asset.id,
        "asset_url": f"/api/player-display/assets/{asset.id}/blob",
        "mime_type": asset.mime_type,
        "width": asset.width,
        "height": asset.height,
        "title": title,
        "caption": payload.caption,
        "fit_mode": payload.fit_mode,
    }
    display.mode = "image"
    display.active_campaign_id = asset.campaign_id
    display.active_session_id = None
    display.active_scene_id = None
    display.title = title
    display.subtitle = campaign.name if campaign else None
    display.payload_json = json.dumps(public_payload)
    display.revision += 1
    display.updated_at = utc_now_z()


def _ensure_blob_exists(settings, asset: Asset) -> None:  # noqa: ANN001
    try:
        path = resolve_asset_path(settings, asset.relative_path)
    except AssetImportError as error:
        raise api_error(error.status_code, error.code, error.message) from error
    if not path.exists() or not path.is_file():
        raise api_error(404, "asset_blob_not_found", "Asset blob not found")


def _apply_map_display(display: PlayerDisplayRuntime, db: Session, settings, scene_map: SceneMap) -> None:  # noqa: ANN001
    campaign_map = _require_map(db, scene_map.map_id)
    public_payload = _create_public_map_payload(db, settings, scene_map)
    display.mode = "map"
    display.active_campaign_id = scene_map.campaign_id
    display.active_session_id = None
    display.active_scene_id = scene_map.scene_id
    display.title = campaign_map.name
    display.subtitle = None
    display.payload_json = json.dumps(public_payload)
    display.revision += 1
    display.updated_at = utc_now_z()


def _publish_staged_scene_display(db: Session, settings, scene: Scene, context: SceneContext) -> None:  # noqa: ANN001
    display = _player_display_row(db)
    mode = context.staged_display_mode
    if mode == "none":
        raise api_error(400, "no_staged_display", "No staged display is configured")
    if mode == "blackout":
        display.mode = "blackout"
        display.title = None
        display.subtitle = None
        display.payload_json = "{}"
        display.revision += 1
        display.updated_at = utc_now_z()
        return
    if mode == "intermission":
        campaign = db.get(Campaign, scene.campaign_id)
        session = db.get(CampaignSession, scene.session_id) if scene.session_id else None
        display.mode = "intermission"
        display.active_campaign_id = scene.campaign_id
        display.active_session_id = scene.session_id
        display.active_scene_id = scene.id
        display.title = "Intermission"
        display.subtitle = _display_subtitle(campaign, session)
        display.payload_json = "{}"
        display.revision += 1
        display.updated_at = utc_now_z()
        return
    if mode == "scene_title":
        _apply_scene_title(display, db, scene)
        return
    if mode == "active_map":
        scene_map = _active_scene_map(db, scene.id)
        if scene_map is None:
            raise api_error(400, "active_scene_map_required", "Active scene map is required")
        campaign_map = _require_map(db, scene_map.map_id)
        asset = _require_asset(db, campaign_map.asset_id)
        _ensure_blob_exists(settings, asset)
        _apply_map_display(display, db, settings, scene_map)
        return
    if mode == "initiative":
        if context.active_encounter_id is None:
            raise api_error(400, "active_encounter_required", "Active encounter is required")
        encounter = _require_combat_encounter(db, context.active_encounter_id)
        if encounter.scene_id != scene.id or encounter.campaign_id != scene.campaign_id:
            raise api_error(400, "combat_encounter_scene_mismatch", "Combat encounter is not linked to this scene")
        _apply_initiative_display(display, db, encounter)
        return
    if mode == "public_snippet":
        if context.staged_public_snippet_id is None:
            raise api_error(400, "staged_public_snippet_required", "A staged public snippet is required")
        snippet = _require_public_snippet(db, context.staged_public_snippet_id)
        if snippet.campaign_id != scene.campaign_id:
            raise api_error(400, "public_snippet_campaign_mismatch", "Public snippet does not belong to scene campaign")
        if _scene_public_snippet_link(db, scene.id, snippet.id) is None:
            raise api_error(400, "public_snippet_not_linked_to_scene", "Public snippet is not linked to this scene")
        _apply_text_display(display, db, snippet)
        return
    raise api_error(400, "invalid_staged_display_mode", "Staged display mode is invalid")


def _apply_fog_operation_to_mask(mask, operation: FogOperationIn) -> None:  # noqa: ANN001
    operation_type = operation.type
    try:
        if operation_type in {"reveal_rect", "hide_rect"}:
            if operation.rect is None:
                raise api_error(400, "invalid_fog_operation", "Rectangle operation requires rect")
            apply_rect(
                mask,
                FogRect(
                    x=operation.rect.x,
                    y=operation.rect.y,
                    width=operation.rect.width,
                    height=operation.rect.height,
                ),
                reveal=operation_type == "reveal_rect",
            )
            return
        if operation_type in {"reveal_brush", "hide_brush"}:
            if operation.points is None or operation.radius is None:
                raise api_error(400, "invalid_fog_operation", "Brush operation requires points and radius")
            apply_brush(
                mask,
                [FogPoint(x=point.x, y=point.y) for point in operation.points],
                operation.radius,
                reveal=operation_type == "reveal_brush",
            )
            return
        if operation_type in {"reveal_all", "hide_all"}:
            apply_all(mask, reveal=operation_type == "reveal_all")
            return
    except FogStoreError as error:
        raise api_error(error.status_code, error.code, error.message) from error
    raise api_error(400, "invalid_fog_operation", "Fog operation type is invalid")


def _republish_scene_map_if_public_payload_changed(
    db: Session,
    settings,  # noqa: ANN001
    scene_map: SceneMap,
    before_payload: dict[str, object] | None = None,
) -> PlayerDisplayOut | None:
    display = db.get(PlayerDisplayRuntime, PLAYER_DISPLAY_ID)
    payload = _parse_json_object(display.payload_json) if display else {}
    if display is None or display.mode != "map" or payload.get("scene_map_id") != scene_map.id:
        return None
    next_payload = _create_public_map_payload(db, settings, scene_map)
    if before_payload is not None and _canonical_json(before_payload) == _canonical_json(next_payload):
        return None
    display.payload_json = json.dumps(next_payload)
    display.revision += 1
    display.updated_at = utc_now_z()
    return _player_display_response(db)


def _widget_out(widget: WorkspaceWidget) -> WorkspaceWidgetOut:
    return WorkspaceWidgetOut(
        id=widget.id,
        scope_type=widget.scope_type,
        scope_id=widget.scope_id,
        kind=widget.kind,
        title=widget.title,
        x=widget.x,
        y=widget.y,
        width=widget.width,
        height=widget.height,
        z_index=widget.z_index,
        locked=widget.locked,
        minimized=widget.minimized,
        config=_parse_json_object(widget.config_json),
        created_at=widget.created_at,
        updated_at=widget.updated_at,
    )


def _workspace_widgets(db: Session) -> list[WorkspaceWidget]:
    return list(
        db.scalars(
            select(WorkspaceWidget)
            .where(WorkspaceWidget.scope_type == "global", WorkspaceWidget.scope_id.is_(None))
            .order_by(WorkspaceWidget.z_index, WorkspaceWidget.title, WorkspaceWidget.id)
        )
    )


def _workspace_response(db: Session) -> WorkspaceWidgetsOut:
    widgets = _workspace_widgets(db)
    updated_at = max((widget.updated_at for widget in widgets), default=utc_now_z())
    return WorkspaceWidgetsOut(widgets=[_widget_out(widget) for widget in widgets], updated_at=updated_at)


def _require_workspace_widget(db: Session, widget_id: UUID | str) -> WorkspaceWidget:
    widget = db.get(WorkspaceWidget, str(widget_id))
    if widget is None:
        raise api_error(404, "workspace_widget_not_found", "Workspace widget not found")
    return widget


@router.get("/health")
def health(request: Request, db: DbSession) -> dict[str, str | None]:
    settings = request.app.state.settings
    status_value = "ok"
    db_status = "ok"
    try:
        assert_database_ok(settings)
    except Exception:
        status_value = "error"
        db_status = "error"
    return {
        "status": status_value,
        "db": db_status,
        "schema_version": get_schema_version(db),
        "db_path": settings.short_db_path(),
        "time": utc_now_z(),
    }


@router.get("/api/meta")
def meta(request: Request, db: DbSession) -> dict[str, str | None]:
    settings = request.app.state.settings
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "db_path": settings.short_db_path(),
        "schema_version": get_schema_version(db),
        "seed_version": get_app_meta(db, SEED_META_KEY) or None,
        "expected_seed_version": DEMO_SEED_VERSION,
    }


def _artifact_out(path: Path | None, *, download: bool = False) -> StorageArtifactOut | None:
    if path is None:
        return None
    return StorageArtifactOut(
        archive_name=path.name,
        byte_size=path.stat().st_size,
        created_at=iso_from_timestamp(path),
        download_url=f"/api/storage/exports/{path.name}" if download else None,
    )


@router.get("/api/storage/status", response_model=StorageStatusOut)
def storage_status(request: Request, db: DbSession) -> StorageStatusOut:
    settings = request.app.state.settings
    settings.ensure_directories()
    latest_backup_path = latest_file(settings.backup_dir, "*.sqlite3")
    latest_export_path = latest_file(settings.export_dir, "*.export.tar.gz")
    private_demo_name_map_active = (get_app_meta(db, "demo_private_name_map_active") or "").lower() == "true"
    return StorageStatusOut(
        profile=profile_hint(settings),
        db_path=settings.short_db_path(),
        asset_dir=settings.short_path(settings.asset_dir),
        backup_dir=settings.short_path(settings.backup_dir),
        export_dir=settings.short_path(settings.export_dir),
        db_size_bytes=settings.db_path.stat().st_size if settings.db_path.exists() else 0,
        asset_size_bytes=directory_size(settings.asset_dir, exclude_tmp=True),
        latest_backup=_artifact_out(latest_backup_path),
        latest_export=_artifact_out(latest_export_path, download=True),
        schema_version=get_schema_version(db),
        seed_version=get_app_meta(db, SEED_META_KEY) or None,
        expected_seed_version=DEMO_SEED_VERSION,
        private_demo_name_map_active=private_demo_name_map_active,
    )


@router.post("/api/storage/backup", response_model=StorageArtifactOut)
def create_storage_backup(request: Request) -> StorageArtifactOut:
    settings = request.app.state.settings
    backup_path = backup_database(settings)
    if backup_path is None:
        raise api_error(404, "database_not_found", "Database file does not exist")
    return _artifact_out(backup_path)  # type: ignore[return-value]


@router.post("/api/storage/export", response_model=StorageArtifactOut)
def create_storage_export(request: Request, include_llm_history: bool = False) -> StorageArtifactOut:
    try:
        artifact = create_export_archive(request.app.state.settings, include_llm_history=include_llm_history)
    except StorageExportError as error:
        raise api_error(error.status_code, error.code, error.message) from error
    return StorageArtifactOut(
        archive_name=artifact.archive_name,
        byte_size=artifact.byte_size,
        created_at=artifact.created_at,
        download_url=f"/api/storage/exports/{artifact.archive_name}",
    )


@router.get("/api/storage/exports/{archive_name}")
def download_storage_export(archive_name: str, request: Request) -> FileResponse:
    if "/" in archive_name or "\\" in archive_name or not archive_name.endswith(".export.tar.gz"):
        raise api_error(400, "invalid_export_name", "Invalid export archive name")
    settings = request.app.state.settings
    path = (settings.export_dir / archive_name).resolve()
    try:
        path.relative_to(settings.export_dir.resolve())
    except ValueError:
        raise api_error(400, "invalid_export_name", "Invalid export archive name") from None
    if not path.exists() or not path.is_file():
        raise api_error(404, "export_not_found", "Export archive not found")
    return FileResponse(path, media_type="application/gzip", filename=archive_name)


@router.get("/api/campaigns", response_model=list[CampaignOut])
def list_campaigns(db: DbSession) -> list[Campaign]:
    return list(db.scalars(select(Campaign).order_by(Campaign.name)))


@router.post("/api/campaigns", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(payload: CampaignCreate, db: DbSession) -> Campaign:
    now = utc_now_z()
    campaign = Campaign(
        id=_new_id(),
        name=payload.name,
        description=payload.description,
        created_at=now,
        updated_at=now,
    )
    with db.begin():
        db.add(campaign)
    return campaign


@router.get("/api/campaigns/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: UUID, db: DbSession) -> Campaign:
    return _require_campaign(db, campaign_id)


@router.get("/api/campaigns/{campaign_id}/assets", response_model=list[AssetOut])
def list_assets(campaign_id: UUID, db: DbSession) -> list[AssetOut]:
    _require_campaign(db, campaign_id)
    assets = db.scalars(select(Asset).where(Asset.campaign_id == str(campaign_id)).order_by(Asset.name, Asset.id))
    return [_asset_out(asset) for asset in assets]


@router.get("/api/assets/{asset_id}/blob")
def get_asset_blob(asset_id: UUID, request: Request, db: DbSession) -> FileResponse:
    asset = _require_asset(db, asset_id)
    try:
        path = resolve_asset_path(request.app.state.settings, asset.relative_path)
    except AssetImportError as error:
        raise api_error(error.status_code, error.code, error.message) from error
    if not path.exists() or not path.is_file():
        raise api_error(404, "asset_blob_not_found", "Asset blob not found")
    return FileResponse(path, media_type=asset.mime_type)


@router.post(
    "/api/campaigns/{campaign_id}/assets/upload",
    response_model=AssetOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_asset(
    campaign_id: UUID,
    request: Request,
    db: DbSession,
    file: UploadFile = File(...),
    kind: str = Form("handout_image"),
    visibility: str = Form("private"),
    name: str | None = Form(None),
    tags: str | None = Form(None),
) -> AssetOut:
    kind = _require_image_asset_kind(kind.strip())
    visibility = _require_asset_visibility(visibility.strip())
    with db.begin():
        _require_campaign(db, campaign_id)
    try:
        stored = store_image_stream(request.app.state.settings, file.file, file.filename)
    except AssetImportError as error:
        raise api_error(error.status_code, error.code, error.message) from error
    with db.begin():
        _require_campaign(db, campaign_id)
        asset = _create_asset_record(
            db,
            campaign_id,
            kind=kind,
            visibility=visibility,
            name=name,
            tags=tags,
            stored=stored,
        )
    return _asset_out(asset)


@router.post(
    "/api/campaigns/{campaign_id}/assets/upload-batch",
    response_model=AssetBatchUploadOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_asset_batch(
    campaign_id: UUID,
    request: Request,
    db: DbSession,
    files: list[UploadFile] = File(...),
    kind: str = Form("handout_image"),
    visibility: str = Form("private"),
    tags: str | None = Form(None),
    auto_create_maps: bool = Form(False),
) -> AssetBatchUploadOut:
    kind = _require_image_asset_kind(kind.strip())
    visibility = _require_asset_visibility(visibility.strip())
    should_create_maps = auto_create_maps and kind == "map_image"
    results: list[AssetBatchItemOut] = []
    with db.begin():
        _require_campaign(db, campaign_id)
    for upload in files:
        filename = upload.filename or "uploaded-image"
        try:
            stored = store_image_stream(request.app.state.settings, upload.file, upload.filename)
            with db.begin():
                _require_campaign(db, campaign_id)
                asset = _create_asset_record(
                    db,
                    campaign_id,
                    kind=kind,
                    visibility=visibility,
                    name=None,
                    tags=tags,
                    stored=stored,
                )
                campaign_map = None
                if should_create_maps:
                    campaign_map, _ = _create_campaign_map_for_asset(db, campaign_id, asset, name=asset.name)
            results.append(
                AssetBatchItemOut(
                    filename=filename,
                    asset=_asset_out(asset),
                    map=_map_out(db, campaign_map) if campaign_map is not None else None,
                )
            )
        except AssetImportError as error:
            results.append(_batch_error(filename, error.code, error.message))
    return AssetBatchUploadOut(results=results)


@router.get("/api/bundled-asset-packs", response_model=list[BundledPackOut])
def list_bundled_asset_packs(request: Request) -> list[BundledPackOut]:
    try:
        packs = load_bundled_packs(request.app.state.settings)
    except BundledAssetPackError as error:
        raise api_error(500, error.code, error.message) from error
    return [
        BundledPackOut(
            id=pack.id,
            title=pack.title,
            asset_count=pack.asset_count,
            category_count=pack.category_count,
            collections=list(pack.collections),
        )
        for pack in packs
    ]


@router.get("/api/bundled-asset-packs/{pack_id}/maps", response_model=list[BundledMapOut])
def list_bundled_asset_pack_maps(pack_id: str, request: Request) -> list[BundledMapOut]:
    try:
        for pack in load_bundled_packs(request.app.state.settings):
            if pack.id == pack_id:
                return [_bundled_map_out(pack.id, bundled_map) for bundled_map in pack.maps]
    except BundledAssetPackError as error:
        raise api_error(500, error.code, error.message) from error
    raise api_error(404, "bundled_pack_not_found", "Bundled asset pack not found")


@router.post(
    "/api/campaigns/{campaign_id}/bundled-maps",
    response_model=BundledMapCreateOut,
    status_code=status.HTTP_201_CREATED,
)
def add_bundled_map_to_campaign(campaign_id: UUID, payload: BundledMapCreate, request: Request, db: DbSession) -> BundledMapCreateOut:
    try:
        pack, bundled_map = find_bundled_map(request.app.state.settings, payload.pack_id, payload.asset_id)
    except BundledAssetPackError as error:
        status_code = 404 if error.code in {"bundled_pack_not_found", "bundled_asset_not_found"} else 500
        raise api_error(status_code, error.code, error.message) from error
    asset_id = deterministic_uuid(f"bundled-map-asset:{campaign_id}:{pack.id}:{bundled_map.id}")
    map_id = deterministic_uuid(f"bundled-map:{campaign_id}:{pack.id}:{bundled_map.id}")
    created_asset = False
    with db.begin():
        _require_campaign(db, campaign_id)
        asset = db.get(Asset, asset_id)
        if asset is None:
            try:
                stored = store_image_path(request.app.state.settings, bundled_map.path)
            except AssetImportError as error:
                raise api_error(error.status_code, error.code, error.message) from error
            asset = Asset(
                id=asset_id,
                campaign_id=str(campaign_id),
                kind="map_image",
                visibility="public_displayable",
                name=_clean_asset_name(payload.name, bundled_map.title),
                mime_type=stored.mime_type,
                byte_size=stored.byte_size,
                checksum=stored.checksum,
                relative_path=stored.relative_path,
                original_filename=stored.original_filename,
                width=stored.width,
                height=stored.height,
                duration_ms=None,
                tags_json=json.dumps(_normalize_tags([*bundled_map.tags, "bundled", pack.id, bundled_map.category_key])),
                created_at=utc_now_z(),
                updated_at=utc_now_z(),
            )
            db.add(asset)
            created_asset = True
        campaign_map, created_map = _create_campaign_map_for_asset(
            db,
            campaign_id,
            asset,
            name=payload.name or bundled_map.title,
            map_id=map_id,
            grid_enabled=True,
            grid_size_px=bundled_map.grid.px_per_cell,
            grid_offset_x=bundled_map.grid.offset_x,
            grid_offset_y=bundled_map.grid.offset_y,
        )
    return BundledMapCreateOut(asset=_asset_out(asset), map=_map_out(db, campaign_map), created_asset=created_asset, created_map=created_map)


@router.get("/api/campaigns/{campaign_id}/entities", response_model=EntitiesOut)
def list_entities(campaign_id: UUID, db: DbSession) -> EntitiesOut:
    _require_campaign(db, campaign_id)
    return _entities_response(db, str(campaign_id))


@router.post("/api/campaigns/{campaign_id}/entities", response_model=EntityOut, status_code=status.HTTP_201_CREATED)
def create_entity(campaign_id: UUID, payload: EntityCreate, db: DbSession) -> EntityOut:
    now = utc_now_z()
    with db.begin():
        _require_campaign(db, campaign_id)
        _validate_portrait_asset(db, str(campaign_id), payload.portrait_asset_id)
        entity = Entity(
            id=_new_id(),
            campaign_id=str(campaign_id),
            kind=_require_entity_kind(payload.kind),
            name=payload.name,
            display_name=payload.display_name,
            visibility=_require_entity_visibility(payload.visibility),
            portrait_asset_id=str(payload.portrait_asset_id) if payload.portrait_asset_id else None,
            tags_json=json.dumps(_normalize_tags(payload.tags)),
            notes=payload.notes,
            created_at=now,
            updated_at=now,
        )
        db.add(entity)
    return _entity_out(db, entity)


@router.get("/api/entities/{entity_id}", response_model=EntityOut)
def get_entity(entity_id: UUID, db: DbSession) -> EntityOut:
    return _entity_out(db, _require_entity(db, entity_id))


@router.patch("/api/entities/{entity_id}", response_model=EntityOut)
def patch_entity(entity_id: UUID, payload: EntityPatch, db: DbSession) -> EntityOut:
    with db.begin():
        entity = _require_entity(db, entity_id)
        data = payload.model_dump(exclude_unset=True)
        if "kind" in data and data["kind"] is not None:
            entity.kind = _require_entity_kind(str(data["kind"]))
        if "name" in data and data["name"] is not None:
            entity.name = str(data["name"])
        if "display_name" in data:
            entity.display_name = data["display_name"] if data["display_name"] is None else str(data["display_name"])
        if "visibility" in data and data["visibility"] is not None:
            entity.visibility = _require_entity_visibility(str(data["visibility"]))
        if "portrait_asset_id" in data:
            _validate_portrait_asset(db, entity.campaign_id, data["portrait_asset_id"])
            entity.portrait_asset_id = str(data["portrait_asset_id"]) if data["portrait_asset_id"] is not None else None
        if "tags" in data and data["tags"] is not None:
            entity.tags_json = json.dumps(_normalize_tags(data["tags"]))  # type: ignore[arg-type]
        if "notes" in data and data["notes"] is not None:
            entity.notes = str(data["notes"])
        entity.updated_at = utc_now_z()
    return _entity_out(db, entity)


@router.get("/api/campaigns/{campaign_id}/custom-fields", response_model=CustomFieldsOut)
def list_custom_fields(campaign_id: UUID, db: DbSession) -> CustomFieldsOut:
    _require_campaign(db, campaign_id)
    return _custom_fields_response(db, str(campaign_id))


@router.post("/api/campaigns/{campaign_id}/custom-fields", response_model=CustomFieldDefinitionOut, status_code=status.HTTP_201_CREATED)
def create_custom_field(campaign_id: UUID, payload: CustomFieldCreate, db: DbSession) -> CustomFieldDefinitionOut:
    now = utc_now_z()
    with db.begin():
        _require_campaign(db, campaign_id)
        key = _normalize_field_key(payload.key)
        if db.scalars(
            select(CustomFieldDefinition).where(
                CustomFieldDefinition.campaign_id == str(campaign_id),
                CustomFieldDefinition.key == key,
            )
        ).one_or_none() is not None:
            raise api_error(400, "custom_field_key_exists", "Custom field key already exists")
        field_type, applies_to, options, default_value = _validate_custom_field_definition_payload(
            db,
            str(campaign_id),
            field_type=payload.field_type,
            applies_to=payload.applies_to,
            options=payload.options,
            default_value=payload.default_value,
        )
        field = CustomFieldDefinition(
            id=_new_id(),
            campaign_id=str(campaign_id),
            key=key,
            label=payload.label,
            field_type=field_type,
            applies_to_json=json.dumps(applies_to),
            required=payload.required,
            default_value_json=json.dumps(default_value) if default_value is not None else None,
            options_json=json.dumps(options),
            public_by_default=payload.public_by_default,
            sort_order=payload.sort_order,
            created_at=now,
            updated_at=now,
        )
        db.add(field)
    return _field_out(field)


@router.patch("/api/custom-fields/{field_id}", response_model=CustomFieldDefinitionOut)
def patch_custom_field(field_id: UUID, payload: CustomFieldPatch, db: DbSession) -> CustomFieldDefinitionOut:
    with db.begin():
        field = _require_custom_field(db, field_id)
        data = payload.model_dump(exclude_unset=True)
        field_type = field.field_type
        applies_to = _field_applies_to(field)
        options = _field_options(field)
        default_value = _field_default_value(field)
        if "label" in data and data["label"] is not None:
            field.label = str(data["label"])
        if "applies_to" in data and data["applies_to"] is not None:
            applies_to = data["applies_to"]  # type: ignore[assignment]
        if "options" in data and data["options"] is not None:
            options = data["options"]  # type: ignore[assignment]
        if "default_value" in data:
            default_value = data["default_value"]
        field_type, applies_to, options, default_value = _validate_custom_field_definition_payload(
            db,
            field.campaign_id,
            field_type=field_type,
            applies_to=applies_to,
            options=options,
            default_value=default_value,
        )
        field.applies_to_json = json.dumps(applies_to)
        field.options_json = json.dumps(options)
        field.default_value_json = json.dumps(default_value) if default_value is not None else None
        if "required" in data and data["required"] is not None:
            field.required = bool(data["required"])
        if "public_by_default" in data and data["public_by_default"] is not None:
            field.public_by_default = bool(data["public_by_default"])
        if "sort_order" in data and data["sort_order"] is not None:
            field.sort_order = int(data["sort_order"])
        field.updated_at = utc_now_z()
    return _field_out(field)


@router.patch("/api/entities/{entity_id}/field-values", response_model=EntityOut)
def patch_entity_field_values(entity_id: UUID, payload: FieldValuesPatch, db: DbSession) -> EntityOut:
    with db.begin():
        entity = _require_entity(db, entity_id)
        fields_by_key = {
            field.key: field
            for field in db.scalars(select(CustomFieldDefinition).where(CustomFieldDefinition.campaign_id == entity.campaign_id))
        }
        now = utc_now_z()
        for key, raw_value in payload.values.items():
            normalized_key = _normalize_field_key(key)
            field = fields_by_key.get(normalized_key)
            if field is None:
                raise api_error(404, "custom_field_not_found", "Custom field not found")
            if entity.kind not in _field_applies_to(field):
                raise api_error(400, "custom_field_not_applicable", "Custom field does not apply to entity")
            existing = db.scalars(
                select(CustomFieldValue).where(
                    CustomFieldValue.entity_id == entity.id,
                    CustomFieldValue.field_definition_id == field.id,
                )
            ).one_or_none()
            if raw_value is None:
                if existing is not None:
                    db.delete(existing)
                continue
            value = _value_for_field(db, entity.campaign_id, field, raw_value)
            if existing is None:
                existing = CustomFieldValue(
                    id=_new_id(),
                    campaign_id=entity.campaign_id,
                    entity_id=entity.id,
                    field_definition_id=field.id,
                    value_json=json.dumps(value),
                    created_at=now,
                    updated_at=now,
                )
                db.add(existing)
            else:
                existing.value_json = json.dumps(value)
                existing.updated_at = now
        entity.updated_at = now
    return _entity_out(db, entity)


@router.get("/api/campaigns/{campaign_id}/party-tracker", response_model=PartyTrackerOut)
def get_party_tracker(campaign_id: UUID, db: DbSession) -> PartyTrackerOut:
    _require_campaign(db, campaign_id)
    return _party_tracker_out(db, str(campaign_id))


@router.patch("/api/campaigns/{campaign_id}/party-tracker", response_model=PartyTrackerOut)
def patch_party_tracker(campaign_id: UUID, payload: PartyTrackerPatch, db: DbSession) -> PartyTrackerOut:
    with db.begin():
        _require_campaign(db, campaign_id)
        config = _ensure_party_config(db, str(campaign_id))
        now = utc_now_z()
        if payload.layout is not None:
            config.layout = _require_party_layout(payload.layout)
        if payload.member_ids is not None:
            db.execute(delete(PartyTrackerMember).where(PartyTrackerMember.config_id == config.id))
            seen_members: set[str] = set()
            for index, entity_id in enumerate(payload.member_ids):
                entity = _require_entity(db, entity_id)
                if entity.campaign_id != str(campaign_id):
                    raise api_error(400, "entity_campaign_mismatch", "Entity does not belong to campaign")
                if entity.kind != "pc":
                    raise api_error(400, "party_member_must_be_pc", "Party roster accepts PC entities only")
                if entity.id in seen_members:
                    continue
                seen_members.add(entity.id)
                db.add(
                    PartyTrackerMember(
                        id=_new_id(),
                        config_id=config.id,
                        campaign_id=str(campaign_id),
                        entity_id=entity.id,
                        sort_order=index,
                        created_at=now,
                        updated_at=now,
                    )
                )
        if payload.fields is not None:
            db.execute(delete(PartyTrackerField).where(PartyTrackerField.config_id == config.id))
            seen_fields: set[str] = set()
            for index, field_payload in enumerate(payload.fields):
                field = _require_custom_field(db, field_payload.field_definition_id)
                if field.campaign_id != str(campaign_id):
                    raise api_error(400, "custom_field_campaign_mismatch", "Custom field does not belong to campaign")
                if field.id in seen_fields:
                    continue
                seen_fields.add(field.id)
                db.add(
                    PartyTrackerField(
                        id=_new_id(),
                        config_id=config.id,
                        campaign_id=str(campaign_id),
                        field_definition_id=field.id,
                        sort_order=index,
                        public_visible=field_payload.public_visible,
                        created_at=now,
                        updated_at=now,
                    )
                )
        config.updated_at = now
    return _party_tracker_out(db, str(campaign_id))


@router.get("/api/campaigns/{campaign_id}/combat-encounters", response_model=CombatEncountersOut)
def list_combat_encounters(campaign_id: UUID, db: DbSession) -> CombatEncountersOut:
    _require_campaign(db, campaign_id)
    return _combat_encounters_response(db, str(campaign_id))


@router.post(
    "/api/campaigns/{campaign_id}/combat-encounters",
    response_model=CombatEncounterOut,
    status_code=status.HTTP_201_CREATED,
)
def create_combat_encounter(campaign_id: UUID, payload: CombatEncounterCreate, db: DbSession) -> CombatEncounterOut:
    with db.begin():
        _require_campaign(db, campaign_id)
        session_id, scene_id = _validate_combat_links(db, str(campaign_id), session_id=payload.session_id, scene_id=payload.scene_id)
        now = utc_now_z()
        encounter = CombatEncounter(
            id=_new_id(),
            campaign_id=str(campaign_id),
            session_id=session_id,
            scene_id=scene_id,
            title=payload.title,
            status=_require_combat_status(payload.status),
            round=1,
            active_combatant_id=None,
            created_at=now,
            updated_at=now,
        )
        db.add(encounter)
        db.flush()
    return _combat_encounter_out(db, encounter)


@router.get("/api/combat-encounters/{encounter_id}", response_model=CombatEncounterOut)
def get_combat_encounter(encounter_id: UUID, db: DbSession) -> CombatEncounterOut:
    encounter = _require_combat_encounter(db, encounter_id)
    return _combat_encounter_out(db, encounter)


@router.patch("/api/combat-encounters/{encounter_id}", response_model=CombatEncounterOut)
def patch_combat_encounter(encounter_id: UUID, payload: CombatEncounterPatch, db: DbSession) -> CombatEncounterOut:
    with db.begin():
        encounter = _require_combat_encounter(db, encounter_id)
        data = payload.model_dump(exclude_unset=True)
        if "session_id" in data or "scene_id" in data:
            session_id, scene_id = _validate_combat_links(
                db,
                encounter.campaign_id,
                session_id=data.get("session_id", encounter.session_id),
                scene_id=data.get("scene_id", encounter.scene_id),
            )
            encounter.session_id = session_id
            encounter.scene_id = scene_id
        if "status" in data and data["status"] is not None:
            encounter.status = _require_combat_status(str(data["status"]))
        if "active_combatant_id" in data:
            if data["active_combatant_id"] is None:
                encounter.active_combatant_id = None
            else:
                combatant = _require_combatant(db, data["active_combatant_id"])
                if combatant.encounter_id != encounter.id:
                    raise api_error(400, "combatant_encounter_mismatch", "Combatant does not belong to encounter")
                encounter.active_combatant_id = combatant.id
        for key in ("title", "round"):
            if key in data and data[key] is not None:
                setattr(encounter, key, data[key])
        encounter.updated_at = utc_now_z()
    return _combat_encounter_out(db, encounter)


@router.post(
    "/api/combat-encounters/{encounter_id}/combatants",
    response_model=CombatEncounterOut,
    status_code=status.HTTP_201_CREATED,
)
def create_combatant(encounter_id: UUID, payload: CombatantCreate, db: DbSession) -> CombatEncounterOut:
    with db.begin():
        encounter = _require_combat_encounter(db, encounter_id)
        entity, token = _validate_combatant_refs(db, encounter.campaign_id, entity_id=payload.entity_id, token_id=payload.token_id)
        combatants = _combatants_for_encounter(db, encounter.id)
        now = utc_now_z()
        combatant = Combatant(
            id=_new_id(),
            campaign_id=encounter.campaign_id,
            encounter_id=encounter.id,
            entity_id=entity.id if entity else None,
            token_id=token.id if token else None,
            name=_default_combatant_name(entity, token, payload.name),
            disposition=_default_combatant_disposition(entity, payload.disposition),
            initiative=payload.initiative,
            order_index=len(combatants),
            armor_class=payload.armor_class,
            hp_current=payload.hp_current,
            hp_max=payload.hp_max,
            hp_temp=payload.hp_temp,
            conditions_json=json.dumps(payload.conditions),
            public_status_json=json.dumps(_normalize_public_status(payload.public_status)),
            notes=payload.notes,
            public_visible=_default_public_visible(entity, token, payload.public_visible),
            is_defeated=payload.is_defeated,
            created_at=now,
            updated_at=now,
        )
        db.add(combatant)
        if encounter.active_combatant_id is None and not combatant.is_defeated:
            encounter.active_combatant_id = combatant.id
        encounter.updated_at = now
        db.flush()
    return _combat_encounter_out(db, encounter)


@router.patch("/api/combatants/{combatant_id}", response_model=CombatEncounterOut)
def patch_combatant(combatant_id: UUID, payload: CombatantPatch, db: DbSession) -> CombatEncounterOut:
    with db.begin():
        combatant = _require_combatant(db, combatant_id)
        encounter = _require_combat_encounter(db, combatant.encounter_id)
        _apply_combatant_patch_data(db, combatant, payload.model_dump(exclude_unset=True))
        if encounter.active_combatant_id == combatant.id and combatant.is_defeated:
            encounter.active_combatant_id = None
        encounter.updated_at = utc_now_z()
    return _combat_encounter_out(db, encounter)


@router.delete("/api/combatants/{combatant_id}", response_model=CombatantDeleteOut)
def delete_combatant(combatant_id: UUID, db: DbSession) -> CombatantDeleteOut:
    deleted_id = str(combatant_id)
    with db.begin():
        combatant = _require_combatant(db, combatant_id)
        deleted_id = combatant.id
        encounter = _require_combat_encounter(db, combatant.encounter_id)
        if encounter.active_combatant_id == combatant.id:
            encounter.active_combatant_id = None
        encounter.updated_at = utc_now_z()
        db.delete(combatant)
        db.flush()
        remaining = _combatants_for_encounter(db, encounter.id)
        for index, row in enumerate(remaining):
            row.order_index = index
    return CombatantDeleteOut(deleted_combatant_id=deleted_id, encounter=_combat_encounter_out(db, encounter))


@router.post("/api/combat-encounters/{encounter_id}/reorder", response_model=CombatEncounterOut)
def reorder_combatants(encounter_id: UUID, payload: CombatReorderIn, db: DbSession) -> CombatEncounterOut:
    with db.begin():
        encounter = _require_combat_encounter(db, encounter_id)
        combatants = _combatants_for_encounter(db, encounter.id)
        by_id = {combatant.id: combatant for combatant in combatants}
        ordered_ids = [str(combatant_id) for combatant_id in payload.combatant_ids]
        if len(set(ordered_ids)) != len(ordered_ids) or set(ordered_ids) != set(by_id):
            raise api_error(400, "invalid_combatant_order", "Combatant order must contain every combatant exactly once")
        now = utc_now_z()
        for index, combatant_id in enumerate(ordered_ids):
            by_id[combatant_id].order_index = index
            by_id[combatant_id].updated_at = now
        encounter.updated_at = now
    return _combat_encounter_out(db, encounter)


@router.post("/api/combat-encounters/{encounter_id}/next-turn", response_model=CombatEncounterOut)
def next_combat_turn(encounter_id: UUID, db: DbSession) -> CombatEncounterOut:
    with db.begin():
        encounter = _require_combat_encounter(db, encounter_id)
        _advance_combat_turn(encounter, 1, _combatants_for_encounter(db, encounter.id))
    return _combat_encounter_out(db, encounter)


@router.post("/api/combat-encounters/{encounter_id}/previous-turn", response_model=CombatEncounterOut)
def previous_combat_turn(encounter_id: UUID, db: DbSession) -> CombatEncounterOut:
    with db.begin():
        encounter = _require_combat_encounter(db, encounter_id)
        _advance_combat_turn(encounter, -1, _combatants_for_encounter(db, encounter.id))
    return _combat_encounter_out(db, encounter)


@router.get("/api/campaigns/{campaign_id}/notes", response_model=NotesOut)
def list_notes(campaign_id: UUID, db: DbSession) -> NotesOut:
    _require_campaign(db, campaign_id)
    return _notes_response(db, str(campaign_id))


@router.post("/api/campaigns/{campaign_id}/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_note(campaign_id: UUID, payload: NoteCreate, db: DbSession) -> NoteOut:
    with db.begin():
        _require_campaign(db, campaign_id)
        note = _create_note_record(
            db,
            campaign_id=str(campaign_id),
            title=payload.title,
            private_body=payload.private_body,
            tags=payload.tags,
            session_id=payload.session_id,
            scene_id=payload.scene_id,
            asset_id=payload.asset_id,
            source_kind="internal",
            source_name="Internal Notes",
            source_label="Internal Notes",
        )
    return _note_out(note)


@router.get("/api/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: UUID, db: DbSession) -> NoteOut:
    return _note_out(_require_note(db, note_id))


@router.patch("/api/notes/{note_id}", response_model=NoteOut)
def patch_note(note_id: UUID, payload: NotePatch, db: DbSession) -> NoteOut:
    with db.begin():
        note = _require_note(db, note_id)
        data = payload.model_dump(exclude_unset=True)
        if "session_id" in data or "scene_id" in data or "asset_id" in data:
            session_id, scene_id, asset_id = _validate_note_links(
                db,
                note.campaign_id,
                session_id=data.get("session_id", note.session_id),
                scene_id=data.get("scene_id", note.scene_id),
                asset_id=data.get("asset_id", note.asset_id),
            )
            if "session_id" in data:
                note.session_id = session_id
            if "scene_id" in data:
                note.scene_id = scene_id
            if "asset_id" in data:
                note.asset_id = asset_id
        if "title" in data and data["title"] is not None:
            note.title = str(data["title"])
        if "private_body" in data and data["private_body"] is not None:
            note.private_body = str(data["private_body"])
        if "tags" in data and data["tags"] is not None:
            note.tags_json = json.dumps(_normalize_tags(data["tags"]))  # type: ignore[arg-type]
        note.updated_at = utc_now_z()
    return _note_out(note)


@router.post(
    "/api/campaigns/{campaign_id}/notes/import-upload",
    response_model=NoteOut,
    status_code=status.HTTP_201_CREATED,
)
def import_note_upload(
    campaign_id: UUID,
    db: DbSession,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    tags: str | None = Form(None),
    session_id: UUID | None = Form(None),
    scene_id: UUID | None = Form(None),
    asset_id: UUID | None = Form(None),
) -> NoteOut:
    filename = file.filename or "imported-note.md"
    _validate_markdown_suffix(filename)
    content = file.file.read(MAX_MARKDOWN_IMPORT_BYTES + 1)
    body = _decode_markdown_bytes(content)
    source_label = Path(filename).name
    note_title = _clean_asset_name(_trim_optional(title), source_label)
    with db.begin():
        _require_campaign(db, campaign_id)
        note = _create_note_record(
            db,
            campaign_id=str(campaign_id),
            title=note_title,
            private_body=body,
            tags=tags,
            session_id=session_id,
            scene_id=scene_id,
            asset_id=asset_id,
            source_kind="imported_markdown",
            source_name=f"Imported: {source_label}",
            source_label=source_label,
        )
    return _note_out(note)


@router.get("/api/campaigns/{campaign_id}/public-snippets", response_model=PublicSnippetsOut)
def list_public_snippets(campaign_id: UUID, db: DbSession) -> PublicSnippetsOut:
    _require_campaign(db, campaign_id)
    return _public_snippets_response(db, str(campaign_id))


@router.post(
    "/api/campaigns/{campaign_id}/public-snippets",
    response_model=PublicSnippetOut,
    status_code=status.HTTP_201_CREATED,
)
def create_public_snippet(campaign_id: UUID, payload: PublicSnippetCreate, db: DbSession) -> PublicSnippetOut:
    now = utc_now_z()
    with db.begin():
        _require_campaign(db, campaign_id)
        note_id = str(payload.note_id) if payload.note_id else None
        if note_id is not None:
            note = _require_note(db, note_id)
            if note.campaign_id != str(campaign_id):
                raise api_error(400, "note_campaign_mismatch", "Note does not belong to campaign")
        snippet = PublicSnippet(
            id=_new_id(),
            campaign_id=str(campaign_id),
            note_id=note_id,
            title=payload.title,
            body=payload.body,
            format=_require_snippet_format(payload.format),
            created_at=now,
            updated_at=now,
        )
        db.add(snippet)
    return _public_snippet_out(snippet)


@router.patch("/api/public-snippets/{snippet_id}", response_model=PublicSnippetOut)
def patch_public_snippet(snippet_id: UUID, payload: PublicSnippetPatch, db: DbSession) -> PublicSnippetOut:
    with db.begin():
        snippet = _require_public_snippet(db, snippet_id)
        data = payload.model_dump(exclude_unset=True)
        if "title" in data:
            snippet.title = data["title"] if data["title"] is None else str(data["title"])
        if "body" in data and data["body"] is not None:
            snippet.body = str(data["body"])
        if "format" in data and data["format"] is not None:
            snippet.format = _require_snippet_format(str(data["format"]))
        snippet.updated_at = utc_now_z()
    return _public_snippet_out(snippet)


@router.get("/api/campaigns/{campaign_id}/maps", response_model=list[MapOut])
def list_maps(campaign_id: UUID, db: DbSession) -> list[MapOut]:
    _require_campaign(db, campaign_id)
    maps = db.scalars(select(CampaignMap).where(CampaignMap.campaign_id == str(campaign_id)).order_by(CampaignMap.name, CampaignMap.id))
    return [_map_out(db, campaign_map) for campaign_map in maps]


@router.post(
    "/api/campaigns/{campaign_id}/maps",
    response_model=MapOut,
    status_code=status.HTTP_201_CREATED,
)
def create_map(campaign_id: UUID, payload: MapCreate, db: DbSession) -> MapOut:
    with db.begin():
        _require_campaign(db, campaign_id)
        asset = _require_asset(db, payload.asset_id)
        if asset.campaign_id != str(campaign_id):
            raise api_error(400, "asset_campaign_mismatch", "Asset does not belong to campaign")
        if asset.kind != "map_image":
            raise api_error(400, "asset_not_map_image", "Asset must be a map image")
        campaign_map, _ = _create_campaign_map_for_asset(db, campaign_id, asset, name=payload.name)
    return _map_out(db, campaign_map)


@router.get("/api/campaigns/{campaign_id}/scenes/{scene_id}/maps", response_model=list[SceneMapOut])
def list_scene_maps(campaign_id: UUID, scene_id: UUID, db: DbSession) -> list[SceneMapOut]:
    _require_campaign(db, campaign_id)
    scene = _require_scene(db, scene_id)
    if scene.campaign_id != str(campaign_id):
        raise api_error(400, "scene_campaign_mismatch", "Scene does not belong to campaign")
    scene_maps = db.scalars(
        select(SceneMap)
        .where(SceneMap.campaign_id == str(campaign_id), SceneMap.scene_id == str(scene_id))
        .order_by(SceneMap.is_active.desc(), SceneMap.created_at, SceneMap.id)
    )
    return [_scene_map_out(db, scene_map) for scene_map in scene_maps]


@router.post(
    "/api/campaigns/{campaign_id}/scenes/{scene_id}/maps",
    response_model=SceneMapOut,
    status_code=status.HTTP_201_CREATED,
)
def assign_scene_map(campaign_id: UUID, scene_id: UUID, payload: SceneMapCreate, db: DbSession) -> SceneMapOut:
    now = utc_now_z()
    fit_mode = _require_fit_mode(payload.player_fit_mode)
    with db.begin():
        _require_campaign(db, campaign_id)
        scene = _require_scene(db, scene_id)
        if scene.campaign_id != str(campaign_id):
            raise api_error(400, "scene_campaign_mismatch", "Scene does not belong to campaign")
        campaign_map = _require_map(db, payload.map_id)
        if campaign_map.campaign_id != str(campaign_id):
            raise api_error(400, "map_campaign_mismatch", "Map does not belong to campaign")
        scene_map = SceneMap(
            id=_new_id(),
            campaign_id=str(campaign_id),
            scene_id=str(scene_id),
            map_id=campaign_map.id,
            is_active=False,
            player_fit_mode=fit_mode,
            player_grid_visible=payload.player_grid_visible,
            created_at=now,
            updated_at=now,
        )
        db.add(scene_map)
        db.flush()
        if payload.is_active:
            _activate_scene_map(db, scene_map)
    return _scene_map_out(db, scene_map)


@router.patch("/api/maps/{map_id}/grid", response_model=MapOut)
def patch_map_grid(map_id: UUID, payload: MapGridPatch, db: DbSession) -> MapOut:
    with db.begin():
        campaign_map = _require_map(db, map_id)
        data = payload.model_dump(exclude_unset=True)
        if "grid_offset_x" in data and data["grid_offset_x"] is not None:
            data["grid_offset_x"] = _require_finite(float(data["grid_offset_x"]), "invalid_grid_offset", "Grid offset must be finite")
        if "grid_offset_y" in data and data["grid_offset_y"] is not None:
            data["grid_offset_y"] = _require_finite(float(data["grid_offset_y"]), "invalid_grid_offset", "Grid offset must be finite")
        if "grid_color" in data and data["grid_color"] is not None:
            data["grid_color"] = _normalize_hex_color(str(data["grid_color"]))
        for key, value in data.items():
            setattr(campaign_map, key, value)
        campaign_map.updated_at = utc_now_z()
    return _map_out(db, campaign_map)


@router.patch("/api/scene-maps/{scene_map_id}", response_model=SceneMapOut)
def patch_scene_map(scene_map_id: UUID, payload: SceneMapPatch, db: DbSession) -> SceneMapOut:
    with db.begin():
        scene_map = _require_scene_map(db, scene_map_id)
        data = payload.model_dump(exclude_unset=True)
        if "player_fit_mode" in data and data["player_fit_mode"] is not None:
            data["player_fit_mode"] = _require_fit_mode(str(data["player_fit_mode"]))
        for key, value in data.items():
            setattr(scene_map, key, value)
        scene_map.updated_at = utc_now_z()
    return _scene_map_out(db, scene_map)


@router.post("/api/scene-maps/{scene_map_id}/activate", response_model=SceneMapOut)
def activate_scene_map(scene_map_id: UUID, db: DbSession) -> SceneMapOut:
    with db.begin():
        scene_map = _require_scene_map(db, scene_map_id)
        _activate_scene_map(db, scene_map)
    return _scene_map_out(db, scene_map)


@router.get("/api/scene-maps/{scene_map_id}/fog", response_model=FogMaskOut | None)
def get_scene_map_fog(scene_map_id: UUID, db: DbSession) -> FogMaskOut | None:
    _require_scene_map(db, scene_map_id)
    fog = _fog_for_scene_map(db, str(scene_map_id))
    return _fog_out(fog) if fog else None


@router.post("/api/scene-maps/{scene_map_id}/fog/enable", response_model=FogMaskOut)
def enable_scene_map_fog(scene_map_id: UUID, request: Request, db: DbSession) -> FogMaskOut:
    with db.begin():
        scene_map = _require_scene_map(db, scene_map_id)
        fog = _ensure_fog_mask(db, request.app.state.settings, scene_map)
    return _fog_out(fog)


@router.post("/api/scene-maps/{scene_map_id}/fog/operations", response_model=FogOperationResultOut)
def apply_scene_map_fog_operations(
    scene_map_id: UUID,
    payload: FogOperationsIn,
    request: Request,
    db: DbSession,
) -> FogOperationResultOut:
    with db.begin():
        scene_map = _require_scene_map(db, scene_map_id)
        fog = _ensure_fog_mask(db, request.app.state.settings, scene_map)
        try:
            mask = load_mask(request.app.state.settings, fog.relative_path, fog.width, fog.height)
            for operation in payload.operations:
                _apply_fog_operation_to_mask(mask, operation)
            save_mask_atomic(request.app.state.settings, fog.relative_path, mask)
        except FogStoreError as error:
            raise api_error(error.status_code, error.code, error.message) from error
        fog.revision += 1
        fog.updated_at = utc_now_z()
        player_display = _republish_scene_map_if_public_payload_changed(db, request.app.state.settings, scene_map)
    return FogOperationResultOut(fog=_fog_out(fog), player_display=player_display)


@router.get("/api/scene-maps/{scene_map_id}/fog/mask")
def get_scene_map_fog_mask(scene_map_id: UUID, request: Request, db: DbSession) -> FileResponse:
    _require_scene_map(db, scene_map_id)
    fog = _fog_for_scene_map(db, str(scene_map_id))
    if fog is None:
        raise api_error(404, "fog_mask_not_found", "Fog mask not found")
    try:
        path = resolve_fog_path(request.app.state.settings, fog.relative_path)
    except FogStoreError as error:
        raise api_error(error.status_code, error.code, error.message) from error
    if not path.exists() or not path.is_file():
        raise api_error(404, "fog_mask_blob_not_found", "Fog mask blob not found")
    return FileResponse(path, media_type="image/png")


@router.get("/api/scene-maps/{scene_map_id}/tokens", response_model=TokensOut)
def list_scene_map_tokens(scene_map_id: UUID, db: DbSession) -> TokensOut:
    _require_scene_map(db, scene_map_id)
    return _tokens_response(db, str(scene_map_id))


@router.post(
    "/api/scene-maps/{scene_map_id}/tokens",
    response_model=TokenMutationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_scene_map_token(
    scene_map_id: UUID,
    payload: TokenCreate,
    request: Request,
    db: DbSession,
) -> TokenMutationOut:
    with db.begin():
        scene_map = _require_scene_map(db, scene_map_id)
        campaign_map = _require_map(db, scene_map.map_id)
        before_payload = _public_payload_before_token_mutation(db, request.app.state.settings, scene_map)
        data = payload.model_dump()
        if data["x"] is None:
            data["x"] = campaign_map.width / 2
        if data["y"] is None:
            data["y"] = campaign_map.height / 2
        normalized = _normalize_token_payload(data, campaign_map)
        _validate_token_asset(db, scene_map.campaign_id, payload.asset_id)
        _validate_entity_reference(db, scene_map.campaign_id, payload.entity_id)
        now = utc_now_z()
        token = SceneMapToken(
            id=_new_id(),
            campaign_id=scene_map.campaign_id,
            scene_id=scene_map.scene_id,
            scene_map_id=scene_map.id,
            entity_id=payload.entity_id,
            asset_id=str(payload.asset_id) if payload.asset_id else None,
            name=str(normalized["name"]),
            x=float(normalized["x"]),
            y=float(normalized["y"]),
            width=float(normalized["width"]),
            height=float(normalized["height"]),
            rotation=float(normalized["rotation"]),
            z_index=int(normalized["z_index"]),
            visibility=str(normalized["visibility"]),
            label_visibility=str(normalized["label_visibility"]),
            shape=str(normalized["shape"]),
            color=str(normalized["color"]),
            border_color=str(normalized["border_color"]),
            opacity=float(normalized["opacity"]),
            status_json=_status_json(payload.status),
            created_at=now,
            updated_at=now,
        )
        db.add(token)
        db.flush()
        player_display = _republish_scene_map_if_public_payload_changed(
            db,
            request.app.state.settings,
            scene_map,
            before_payload,
        )
    return TokenMutationOut(token=_token_out(db, token), player_display=player_display)


@router.patch("/api/tokens/{token_id}", response_model=TokenMutationOut)
def patch_token(token_id: UUID, payload: TokenPatch, request: Request, db: DbSession) -> TokenMutationOut:
    with db.begin():
        token = _require_token(db, token_id)
        scene_map = _require_scene_map(db, token.scene_map_id)
        campaign_map = _require_map(db, scene_map.map_id)
        before_payload = _public_payload_before_token_mutation(db, request.app.state.settings, scene_map)
        _apply_token_data(db, token, campaign_map, payload.model_dump(exclude_unset=True))
        player_display = _republish_scene_map_if_public_payload_changed(
            db,
            request.app.state.settings,
            scene_map,
            before_payload,
        )
    return TokenMutationOut(token=_token_out(db, token), player_display=player_display)


@router.delete("/api/tokens/{token_id}", response_model=TokenDeleteOut)
def delete_token(token_id: UUID, request: Request, db: DbSession) -> TokenDeleteOut:
    deleted_token_id = str(token_id)
    with db.begin():
        token = _require_token(db, token_id)
        deleted_token_id = token.id
        scene_map = _require_scene_map(db, token.scene_map_id)
        before_payload = _public_payload_before_token_mutation(db, request.app.state.settings, scene_map)
        db.delete(token)
        db.flush()
        player_display = _republish_scene_map_if_public_payload_changed(
            db,
            request.app.state.settings,
            scene_map,
            before_payload,
        )
    return TokenDeleteOut(deleted_token_id=deleted_token_id, player_display=player_display)


@router.get("/api/campaigns/{campaign_id}/sessions", response_model=list[SessionOut])
def list_sessions(campaign_id: UUID, db: DbSession) -> list[CampaignSession]:
    _require_campaign(db, campaign_id)
    return list(
        db.scalars(
            select(CampaignSession)
            .where(CampaignSession.campaign_id == str(campaign_id))
            .order_by(CampaignSession.title)
        )
    )


@router.post(
    "/api/campaigns/{campaign_id}/sessions",
    response_model=SessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_session(campaign_id: UUID, payload: SessionCreate, db: DbSession) -> CampaignSession:
    now = utc_now_z()
    session = CampaignSession(
        id=_new_id(),
        campaign_id=str(campaign_id),
        title=payload.title,
        starts_at=None,
        ended_at=None,
        created_at=now,
        updated_at=now,
    )
    with db.begin():
        _require_campaign(db, campaign_id)
        db.add(session)
    return session


@router.get("/api/campaigns/{campaign_id}/scenes", response_model=list[SceneOut])
def list_scenes(campaign_id: UUID, db: DbSession) -> list[Scene]:
    _require_campaign(db, campaign_id)
    return list(db.scalars(select(Scene).where(Scene.campaign_id == str(campaign_id)).order_by(Scene.title)))


@router.post(
    "/api/campaigns/{campaign_id}/scenes",
    response_model=SceneOut,
    status_code=status.HTTP_201_CREATED,
)
def create_scene(campaign_id: UUID, payload: SceneCreate, db: DbSession) -> Scene:
    now = utc_now_z()
    session_id = str(payload.session_id) if payload.session_id else None
    scene = Scene(
        id=_new_id(),
        campaign_id=str(campaign_id),
        session_id=session_id,
        title=payload.title,
        summary=payload.summary,
        created_at=now,
        updated_at=now,
    )
    with db.begin():
        _require_campaign(db, campaign_id)
        if session_id is not None:
            session = _require_session(db, session_id)
            if session.campaign_id != str(campaign_id):
                raise api_error(400, "session_campaign_mismatch", "Session does not belong to campaign")
        db.add(scene)
    return scene


@router.get("/api/scenes/{scene_id}/context", response_model=SceneContextOut)
def get_scene_context(scene_id: UUID, db: DbSession) -> SceneContextOut:
    with db.begin():
        scene = _require_scene(db, scene_id)
        return _scene_context_response(db, scene)


@router.patch("/api/scenes/{scene_id}/context", response_model=SceneContextOut)
def patch_scene_context(scene_id: UUID, payload: SceneContextPatch, db: DbSession) -> SceneContextOut:
    with db.begin():
        scene = _require_scene(db, scene_id)
        context = _ensure_scene_context(db, scene)
        _validate_scene_context_patch(db, scene, context, payload.model_dump(exclude_unset=True))
        return _scene_context_response(db, scene)


@router.post("/api/scenes/{scene_id}/entity-links", response_model=SceneContextOut, status_code=status.HTTP_201_CREATED)
def link_scene_entity(scene_id: UUID, payload: SceneEntityLinkCreate, db: DbSession) -> SceneContextOut:
    with db.begin():
        scene = _require_scene(db, scene_id)
        entity = _require_entity(db, payload.entity_id)
        if entity.campaign_id != scene.campaign_id:
            raise api_error(400, "entity_campaign_mismatch", "Entity does not belong to scene campaign")
        role = _require_scene_entity_role(payload.role)
        now = utc_now_z()
        existing = db.scalars(
            select(SceneEntityLink).where(SceneEntityLink.scene_id == scene.id, SceneEntityLink.entity_id == entity.id)
        ).one_or_none()
        if existing is None:
            db.add(
                SceneEntityLink(
                    id=_new_id(),
                    campaign_id=scene.campaign_id,
                    scene_id=scene.id,
                    entity_id=entity.id,
                    role=role,
                    sort_order=payload.sort_order,
                    notes=payload.notes,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            existing.role = role
            existing.sort_order = payload.sort_order
            existing.notes = payload.notes
            existing.updated_at = now
        context = _ensure_scene_context(db, scene)
        context.updated_at = now
        db.flush()
        return _scene_context_response(db, scene)


@router.delete("/api/scene-entity-links/{link_id}", response_model=SceneContextOut)
def unlink_scene_entity(link_id: UUID, db: DbSession) -> SceneContextOut:
    with db.begin():
        link = _require_scene_entity_link(db, link_id)
        scene = _require_scene(db, link.scene_id)
        db.delete(link)
        context = _ensure_scene_context(db, scene)
        context.updated_at = utc_now_z()
        db.flush()
        return _scene_context_response(db, scene)


@router.post(
    "/api/scenes/{scene_id}/public-snippet-links",
    response_model=SceneContextOut,
    status_code=status.HTTP_201_CREATED,
)
def link_scene_public_snippet(scene_id: UUID, payload: ScenePublicSnippetLinkCreate, db: DbSession) -> SceneContextOut:
    with db.begin():
        scene = _require_scene(db, scene_id)
        snippet = _require_public_snippet(db, payload.public_snippet_id)
        if snippet.campaign_id != scene.campaign_id:
            raise api_error(400, "public_snippet_campaign_mismatch", "Public snippet does not belong to scene campaign")
        now = utc_now_z()
        existing = _scene_public_snippet_link(db, scene.id, snippet.id)
        if existing is None:
            db.add(
                ScenePublicSnippetLink(
                    id=_new_id(),
                    campaign_id=scene.campaign_id,
                    scene_id=scene.id,
                    public_snippet_id=snippet.id,
                    sort_order=payload.sort_order,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            existing.sort_order = payload.sort_order
            existing.updated_at = now
        context = _ensure_scene_context(db, scene)
        context.updated_at = now
        db.flush()
        return _scene_context_response(db, scene)


@router.delete("/api/scene-public-snippet-links/{link_id}", response_model=SceneContextOut)
def unlink_scene_public_snippet(link_id: UUID, db: DbSession) -> SceneContextOut:
    with db.begin():
        link = _require_scene_public_snippet_link(db, link_id)
        scene = _require_scene(db, link.scene_id)
        context = _ensure_scene_context(db, scene)
        if context.staged_public_snippet_id == link.public_snippet_id:
            context.staged_public_snippet_id = None
        context.updated_at = utc_now_z()
        db.delete(link)
        db.flush()
        return _scene_context_response(db, scene)


@router.post("/api/scenes/{scene_id}/publish-staged-display", response_model=PlayerDisplayOut)
def publish_staged_scene_display(scene_id: UUID, request: Request, db: DbSession) -> PlayerDisplayOut:
    with db.begin():
        scene = _require_scene(db, scene_id)
        context = _ensure_scene_context(db, scene)
        _publish_staged_scene_display(db, request.app.state.settings, scene, context)
    return _player_display_response(db)


@router.get("/api/runtime", response_model=RuntimeOut)
def get_runtime(db: DbSession) -> RuntimeOut:
    with db.begin():
        _runtime_row(db)
    return _runtime_response(db)


@router.post("/api/runtime/activate-campaign", response_model=RuntimeOut)
def activate_campaign(payload: ActivateCampaignIn, db: DbSession) -> RuntimeOut:
    with db.begin():
        campaign = _require_campaign(db, payload.campaign_id)
        runtime = _runtime_row(db)
        runtime.active_campaign_id = campaign.id

        if runtime.active_session_id is not None:
            active_session = db.get(CampaignSession, runtime.active_session_id)
            if active_session is None or active_session.campaign_id != campaign.id:
                runtime.active_session_id = None
                runtime.active_scene_id = None

        if runtime.active_scene_id is not None:
            active_scene = db.get(Scene, runtime.active_scene_id)
            if active_scene is None or active_scene.campaign_id != campaign.id:
                runtime.active_scene_id = None

        runtime.updated_at = utc_now_z()
    return _runtime_response(db)


@router.post("/api/runtime/activate-session", response_model=RuntimeOut)
def activate_session(payload: ActivateSessionIn, db: DbSession) -> RuntimeOut:
    with db.begin():
        session = _require_session(db, payload.session_id)
        runtime = _runtime_row(db)
        runtime.active_campaign_id = session.campaign_id
        runtime.active_session_id = session.id

        if runtime.active_scene_id is not None:
            active_scene = db.get(Scene, runtime.active_scene_id)
            if active_scene is None or active_scene.session_id != session.id:
                runtime.active_scene_id = None

        runtime.updated_at = utc_now_z()
    return _runtime_response(db)


@router.post("/api/runtime/activate-scene", response_model=RuntimeOut)
def activate_scene(payload: ActivateSceneIn, db: DbSession) -> RuntimeOut:
    with db.begin():
        scene = _require_scene(db, payload.scene_id)
        runtime = _runtime_row(db)
        runtime.active_campaign_id = scene.campaign_id
        runtime.active_session_id = scene.session_id
        runtime.active_scene_id = scene.id
        runtime.updated_at = utc_now_z()
    return _runtime_response(db)


@router.post("/api/runtime/clear", response_model=RuntimeOut)
def clear_runtime(db: DbSession) -> RuntimeOut:
    with db.begin():
        runtime = _runtime_row(db)
        runtime.active_campaign_id = None
        runtime.active_session_id = None
        runtime.active_scene_id = None
        runtime.updated_at = utc_now_z()
    return _runtime_response(db)


@router.get("/api/player-display", response_model=PlayerDisplayOut)
def get_player_display(db: DbSession) -> PlayerDisplayOut:
    with db.begin():
        _player_display_row(db)
    return _player_display_response(db)


@router.post("/api/player-display/blackout", response_model=PlayerDisplayOut)
def blackout_player_display(db: DbSession) -> PlayerDisplayOut:
    with db.begin():
        display = _player_display_row(db)
        display.mode = "blackout"
        display.title = None
        display.subtitle = None
        display.payload_json = "{}"
        display.revision += 1
        display.updated_at = utc_now_z()
    return _player_display_response(db)


@router.post("/api/player-display/intermission", response_model=PlayerDisplayOut)
def intermission_player_display(db: DbSession) -> PlayerDisplayOut:
    with db.begin():
        display = _player_display_row(db)
        runtime = _runtime_response(db)
        display.mode = "intermission"
        display.active_campaign_id = runtime.active_campaign_id
        display.active_session_id = runtime.active_session_id
        display.active_scene_id = runtime.active_scene_id
        display.title = "Intermission"
        display.subtitle = runtime.active_session_title or runtime.active_campaign_name
        display.payload_json = "{}"
        display.revision += 1
        display.updated_at = utc_now_z()
    return _player_display_response(db)


@router.post("/api/player-display/show-scene-title", response_model=PlayerDisplayOut)
def show_scene_title_player_display(db: DbSession, payload: ShowSceneTitleIn | None = None) -> PlayerDisplayOut:
    with db.begin():
        scene_id = str(payload.scene_id) if payload and payload.scene_id else None
        if scene_id is None:
            runtime = db.get(AppRuntime, RUNTIME_ID)
            scene_id = runtime.active_scene_id if runtime else None
        if scene_id is None:
            raise api_error(400, "active_scene_required", "Active scene is required")
        scene = _require_scene(db, scene_id)
        display = _player_display_row(db)
        _apply_scene_title(display, db, scene)
    return _player_display_response(db)


@router.post("/api/player-display/show-image", response_model=PlayerDisplayOut)
def show_image_player_display(payload: ShowImageIn, db: DbSession) -> PlayerDisplayOut:
    with db.begin():
        asset = _require_asset(db, payload.asset_id)
        display = _player_display_row(db)
        _apply_image_display(display, db, asset, payload)
    return _player_display_response(db)


@router.post("/api/player-display/show-map", response_model=PlayerDisplayOut)
def show_map_player_display(request: Request, db: DbSession, payload: ShowMapIn | None = None) -> PlayerDisplayOut:
    with db.begin():
        scene_map_id = str(payload.scene_map_id) if payload and payload.scene_map_id else None
        if scene_map_id is None:
            runtime = db.get(AppRuntime, RUNTIME_ID)
            scene_id = runtime.active_scene_id if runtime else None
            if scene_id is None:
                raise api_error(400, "active_scene_required", "Active scene is required")
            scene_map = db.scalars(
                select(SceneMap).where(SceneMap.scene_id == scene_id, SceneMap.is_active.is_(True))
            ).one_or_none()
            if scene_map is None:
                raise api_error(400, "active_scene_map_required", "Active scene map is required")
        else:
            scene_map = _require_scene_map(db, scene_map_id)
        campaign_map = _require_map(db, scene_map.map_id)
        asset = _require_asset(db, campaign_map.asset_id)
        _ensure_blob_exists(request.app.state.settings, asset)
        display = _player_display_row(db)
        _apply_map_display(display, db, request.app.state.settings, scene_map)
    return _player_display_response(db)


@router.post("/api/player-display/show-snippet", response_model=PlayerDisplayOut)
def show_snippet_player_display(payload: ShowSnippetIn, db: DbSession) -> PlayerDisplayOut:
    with db.begin():
        snippet = _require_public_snippet(db, payload.snippet_id)
        display = _player_display_row(db)
        _apply_text_display(display, db, snippet)
    return _player_display_response(db)


@router.post("/api/player-display/show-party", response_model=PlayerDisplayOut)
def show_party_player_display(payload: ShowPartyIn, db: DbSession) -> PlayerDisplayOut:
    with db.begin():
        campaign_id = str(payload.campaign_id) if payload.campaign_id else None
        if campaign_id is None:
            runtime = _runtime_row(db)
            campaign_id = runtime.active_campaign_id
        if campaign_id is None:
            raise api_error(400, "active_campaign_required", "A campaign is required to show the party")
        display = _player_display_row(db)
        _apply_party_display(display, db, campaign_id)
    return _player_display_response(db)


@router.post("/api/player-display/show-initiative", response_model=PlayerDisplayOut)
def show_initiative_player_display(payload: ShowInitiativeIn, db: DbSession) -> PlayerDisplayOut:
    with db.begin():
        encounter = _require_combat_encounter(db, payload.encounter_id)
        display = _player_display_row(db)
        _apply_initiative_display(display, db, encounter)
    return _player_display_response(db)


@router.get("/api/player-display/assets/{asset_id}/blob")
def get_player_display_asset_blob(asset_id: UUID, request: Request, db: DbSession) -> FileResponse:
    display = db.get(PlayerDisplayRuntime, PLAYER_DISPLAY_ID)
    payload = _parse_json_object(display.payload_json) if display else {}
    token_asset_ids: set[str] = set()
    party_asset_ids: set[str] = set()
    initiative_asset_ids: set[str] = set()
    if display is not None and display.mode == "map" and isinstance(payload.get("tokens"), list):
        for token_payload in payload["tokens"]:  # type: ignore[index]
            if isinstance(token_payload, dict) and isinstance(token_payload.get("asset_id"), str):
                token_asset_ids.add(str(token_payload["asset_id"]))
    if display is not None and display.mode == "party" and isinstance(payload.get("cards"), list):
        for card_payload in payload["cards"]:  # type: ignore[index]
            if isinstance(card_payload, dict) and isinstance(card_payload.get("portrait_asset_id"), str):
                party_asset_ids.add(str(card_payload["portrait_asset_id"]))
            if isinstance(card_payload, dict) and isinstance(card_payload.get("fields"), list):
                for field_payload in card_payload["fields"]:  # type: ignore[index]
                    if not isinstance(field_payload, dict):
                        continue
                    value_payload = field_payload.get("value")
                    if isinstance(value_payload, dict) and isinstance(value_payload.get("asset_id"), str):
                        party_asset_ids.add(str(value_payload["asset_id"]))
    if display is not None and display.mode == "initiative" and isinstance(payload.get("combatants"), list):
        for combatant_payload in payload["combatants"]:  # type: ignore[index]
            if isinstance(combatant_payload, dict) and isinstance(combatant_payload.get("portrait_asset_id"), str):
                initiative_asset_ids.add(str(combatant_payload["portrait_asset_id"]))
    is_active_map_or_image_asset = payload.get("asset_id") == str(asset_id)
    is_active_token_asset = str(asset_id) in token_asset_ids
    is_active_party_asset = str(asset_id) in party_asset_ids
    is_active_initiative_asset = str(asset_id) in initiative_asset_ids
    if display is None or display.mode not in {"image", "map", "party", "initiative"} or not (
        is_active_map_or_image_asset or is_active_token_asset or is_active_party_asset or is_active_initiative_asset
    ):
        raise api_error(404, "player_display_asset_not_active", "Player display asset not found")

    asset = db.get(Asset, str(asset_id))
    if (
        asset is None
        or asset.visibility != "public_displayable"
        or (display.mode == "image" and asset.kind not in IMAGE_ASSET_KINDS)
        or (display.mode == "map" and is_active_map_or_image_asset and asset.kind != "map_image")
        or (display.mode == "map" and is_active_token_asset and asset.kind not in IMAGE_ASSET_KINDS)
        or (display.mode == "party" and is_active_party_asset and asset.kind not in IMAGE_ASSET_KINDS)
        or (display.mode == "initiative" and is_active_initiative_asset and asset.kind not in IMAGE_ASSET_KINDS)
        or not asset.mime_type.startswith("image/")
    ):
        raise api_error(404, "player_display_asset_not_found", "Player display asset not found")

    try:
        path = resolve_asset_path(request.app.state.settings, asset.relative_path)
    except AssetImportError as error:
        raise api_error(error.status_code, error.code, error.message) from error
    if not path.exists() or not path.is_file():
        raise api_error(404, "asset_blob_not_found", "Asset blob not found")
    return FileResponse(path, media_type=asset.mime_type)


@router.get("/api/player-display/fog/{fog_mask_id}/mask")
def get_player_display_fog_mask(fog_mask_id: UUID, request: Request, db: DbSession) -> FileResponse:
    display = db.get(PlayerDisplayRuntime, PLAYER_DISPLAY_ID)
    payload = _parse_json_object(display.payload_json) if display else {}
    fog_payload = payload.get("fog") if isinstance(payload.get("fog"), dict) else {}
    if (
        display is None
        or display.mode != "map"
        or not fog_payload.get("enabled")
        or fog_payload.get("mask_id") != str(fog_mask_id)
    ):
        raise api_error(404, "player_display_fog_not_active", "Player display fog mask not found")

    fog = _require_fog_mask(db, fog_mask_id)
    if not fog.enabled:
        raise api_error(404, "player_display_fog_not_found", "Player display fog mask not found")
    try:
        path = resolve_fog_path(request.app.state.settings, fog.relative_path)
    except FogStoreError as error:
        raise api_error(error.status_code, error.code, error.message) from error
    if not path.exists() or not path.is_file():
        raise api_error(404, "fog_mask_blob_not_found", "Fog mask blob not found")
    return FileResponse(path, media_type="image/png")


@router.post("/api/player-display/identify", response_model=PlayerDisplayOut)
def identify_player_display(db: DbSession) -> PlayerDisplayOut:
    with db.begin():
        display = _player_display_row(db)
        display.identify_revision += 1
        display.identify_until = to_utc_z(utc_now() + timedelta(seconds=3))
        display.updated_at = utc_now_z()
    return _player_display_response(db)


@router.get("/api/workspace/widgets", response_model=WorkspaceWidgetsOut)
def list_workspace_widgets(db: DbSession) -> WorkspaceWidgetsOut:
    return _workspace_response(db)


@router.patch("/api/workspace/widgets/{widget_id}", response_model=WorkspaceWidgetOut)
def patch_workspace_widget(
    widget_id: UUID,
    payload: WorkspaceWidgetPatch,
    db: DbSession,
) -> WorkspaceWidgetOut:
    with db.begin():
        widget = _require_workspace_widget(db, widget_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(widget, key, value)
        widget.updated_at = utc_now_z()
    return _widget_out(widget)


@router.post("/api/workspace/widgets/reset", response_model=WorkspaceWidgetsOut)
def reset_workspace_widgets(db: DbSession) -> WorkspaceWidgetsOut:
    now = utc_now_z()
    with db.begin():
        for default in DEFAULT_WORKSPACE_WIDGETS:
            widget = db.get(WorkspaceWidget, default.id)
            if widget is None:
                widget = WorkspaceWidget(
                    id=default.id,
                    scope_type="global",
                    scope_id=None,
                    kind=default.kind,
                    title=default.title,
                    x=default.x,
                    y=default.y,
                    width=default.width,
                    height=default.height,
                    z_index=default.z_index,
                    locked=False,
                    minimized=False,
                    config_json=json.dumps(default.config),
                    created_at=now,
                    updated_at=now,
                )
                db.add(widget)
                continue
            if widget.id in DEFAULT_WIDGET_IDS:
                widget.scope_type = "global"
                widget.scope_id = None
                widget.kind = default.kind
                widget.title = default.title
                widget.x = default.x
                widget.y = default.y
                widget.width = default.width
                widget.height = default.height
                widget.z_index = default.z_index
                widget.locked = False
                widget.minimized = False
                widget.config_json = json.dumps(default.config)
                widget.updated_at = now
    return _workspace_response(db)
