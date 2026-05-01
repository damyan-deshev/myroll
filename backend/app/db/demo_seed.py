from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from backend.app.asset_store import store_image_path
from backend.app.db.engine import get_engine
from backend.app.db.models import (
    AppMeta,
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
    Session,
    WorkspaceWidget,
)
from backend.app.db.seed import DEMO_SEED_VERSION, PLAYER_DISPLAY_ID, RUNTIME_ID, SEED_META_KEY
from backend.app.db.seed_ids import deterministic_uuid
from backend.app.fog_store import FogRect, apply_rect, create_hidden_mask, fog_relative_path, load_mask, save_mask_atomic
from backend.app.settings import Settings, get_settings
from backend.app.time import utc_now_z
from backend.app.workspace_defaults import DEFAULT_WORKSPACE_WIDGETS


DEMO_PROFILE = "lantern_vale_chronicle"
DEMO_PROFILE_META_KEY = "demo_profile"
DEMO_PRIVATE_NAMES_META_KEY = "demo_private_name_map_active"
DEMO_ASSET_DIR = Path("demo/assets/generated/lantern_vale_chronicle")
DEMO_ASSET_MANIFEST = DEMO_ASSET_DIR / "manifest.json"


@dataclass(frozen=True)
class DemoSeedResult:
    campaign_id: str
    private_name_map_active: bool


def demo_id(key: str) -> str:
    return deterministic_uuid(f"demo:{DEMO_PROFILE}:{key}")


def _load_name_map(settings: Settings) -> dict[str, str]:
    path = settings.demo_name_map_path
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if isinstance(value, str)}


def _name(names: dict[str, str], key: str, fallback: str) -> str:
    return names.get(key, fallback)


def _add_if_missing(db: OrmSession, model: type, row: Any) -> Any:
    existing = db.get(model, row.id)
    if existing is not None:
        return existing
    db.add(row)
    return row


def _asset_name_from_key(key: str, fallback: str, names: dict[str, str]) -> str:
    return _name(names, key, fallback)


def _import_asset(db: OrmSession, settings: Settings, campaign_id: str, item: dict[str, Any], names: dict[str, str], now: str) -> Asset:
    asset_id = demo_id(item["key"])
    existing = db.get(Asset, asset_id)
    if existing is not None:
        return existing
    source = settings.project_root / DEMO_ASSET_DIR / str(item["filename"])
    stored = store_image_path(settings, source)
    asset = Asset(
        id=asset_id,
        campaign_id=campaign_id,
        kind=str(item["role"]),
        visibility=str(item["default_visibility"]),
        name=_asset_name_from_key(str(item["key"]), Path(str(item["filename"])).stem.replace("-", " ").title(), names),
        mime_type=stored.mime_type,
        byte_size=stored.byte_size,
        checksum=stored.checksum,
        relative_path=stored.relative_path,
        original_filename=stored.original_filename,
        width=stored.width,
        height=stored.height,
        duration_ms=None,
        tags_json=json.dumps(["demo", DEMO_PROFILE]),
        created_at=now,
        updated_at=now,
    )
    db.add(asset)
    return asset


def _asset_manifest(settings: Settings) -> list[dict[str, Any]]:
    path = settings.project_root / DEMO_ASSET_MANIFEST
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return list(data["assets"])


def _seed_widgets(db: OrmSession, now: str) -> None:
    for widget in DEFAULT_WORKSPACE_WIDGETS:
        _add_if_missing(
            db,
            WorkspaceWidget,
            WorkspaceWidget(
                id=widget.id,
                scope_type="global",
                scope_id=None,
                kind=widget.kind,
                title=widget.title,
                x=widget.x,
                y=widget.y,
                width=widget.width,
                height=widget.height,
                z_index=widget.z_index,
                locked=False,
                minimized=False,
                config_json=json.dumps(widget.config),
                created_at=now,
                updated_at=now,
            ),
        )


def _set_meta(db: OrmSession, key: str, value: str, now: str) -> None:
    meta = db.get(AppMeta, key)
    if meta is None:
        db.add(AppMeta(key=key, value=value, updated_at=now))
    else:
        meta.value = value
        meta.updated_at = now


def seed_demo_profile(settings: Settings | None = None) -> DemoSeedResult:
    resolved = settings or get_settings()
    resolved.ensure_directories()
    names = _load_name_map(resolved)
    now = utc_now_z()
    SessionFactory = sessionmaker(bind=get_engine(resolved), autoflush=False, expire_on_commit=False)

    campaign_id = demo_id("campaign.lantern_vale_chronicle")
    session_id = demo_id("session.current")
    scene_last_horn_id = demo_id("scene.last_horn_lake")
    scene_blue_road_id = demo_id("scene.blue_forest_road")
    scene_loom_id = demo_id("scene.crooked_loom_house")
    scene_workshop_id = demo_id("scene.stolen_time_workshop")

    with SessionFactory() as db, db.begin():
        _seed_widgets(db, now)
        _set_meta(db, SEED_META_KEY, DEMO_SEED_VERSION, now)
        _set_meta(db, DEMO_PROFILE_META_KEY, DEMO_PROFILE, now)
        _set_meta(db, DEMO_PRIVATE_NAMES_META_KEY, "true" if names else "false", now)

        _add_if_missing(
            db,
            Campaign,
            Campaign(
                id=campaign_id,
                name=_name(names, "campaign.lantern_vale_chronicle", "Chronicle of the Lantern Vale"),
                description="An original dark-fairytale demo campaign focused on private GM context, public reveals, maps, fog, tokens, party cards, and initiative.",
                created_at=now,
                updated_at=now,
            ),
        )
        _add_if_missing(
            db,
            Session,
            Session(id=session_id, campaign_id=campaign_id, title="Current Session", starts_at=None, ended_at=None, created_at=now, updated_at=now),
        )
        db.flush()

        scenes = [
            (scene_last_horn_id, "scene.last_horn_lake", "Lake of the Last Horn", "The mourning unicorn keeps vigil beside a moonlit lake."),
            (scene_blue_road_id, "scene.blue_forest_road", "The Blue Forest Road", "A blue road through whispering trees and unlit lanterns."),
            (scene_loom_id, "scene.crooked_loom_house", "The Crooked Loom House", "The child-time thief waits in a warped house of toys and thread."),
            (scene_workshop_id, "scene.stolen_time_workshop", "Workshop of Stolen Time", "The active demo scene: a workshop of stolen childhood, fog, tokens, and staged public display."),
        ]
        for scene_id, key, title, summary in scenes:
            _add_if_missing(
                db,
                Scene,
                Scene(id=scene_id, campaign_id=campaign_id, session_id=session_id, title=_name(names, key, title), summary=summary, created_at=now, updated_at=now),
            )
        db.flush()

        assets: dict[str, Asset] = {}
        for item in _asset_manifest(resolved):
            assets[str(item["key"])] = _import_asset(db, resolved, campaign_id, item, names, now)
        db.flush()

        entity_specs = [
            ("entity.errin", "pc", "Errin", "Oathbound knight", "public_known", "asset.fallen_carnival_paladin", ["party"]),
            ("entity.drew", "pc", "Drew", "Exiled glamour bard", "public_known", "asset.redeemed_shadow_assassin", ["party"]),
            ("entity.datt", "pc", "Datt", "Wandering artificer heir", "public_known", "asset.goldsmith_cursed_hands", ["party"]),
            ("entity.harold", "pc", "Harold", "Archer with missing memory", "public_known", "asset.lantern_children_procession", ["party"]),
            ("entity.granny_scrap", "npc", "Granny Scrap", "Child-time thief", "private", None, ["threat"]),
            ("entity.wylan", "npc", "Wylan", "Rebel forest youth", "public_known", None, ["ally"]),
            ("entity.sloan", "npc", "Sloan", "Forest ally", "public_known", None, ["ally"]),
            ("entity.illy", "npc", "Illy", "Stolen child", "public_known", None, ["clue"]),
            ("entity.lamora", "creature", "Lamora", "Mourning unicorn", "public_known", "asset.mourning_unicorn_lake", ["ally"]),
            ("entity.aureon", "npc", "Aureon", "Cursed goldsmith", "public_known", "asset.goldsmith_cursed_hands", ["witness"]),
            ("entity.isolde", "npc", "Isolde", "Fallen carnival paladin", "private", "asset.fallen_carnival_paladin", ["future"]),
            ("entity.nastrond", "npc", "Nastrond", "Redeemed shadow assassin", "private", "asset.redeemed_shadow_assassin", ["future"]),
            ("entity.lady_glass_hour", "npc", "Lady of the Glass Hour", "Sealed clockglass tyrant", "private", "asset.glass_hour_tyrant", ["secret"]),
        ]
        entities: dict[str, Entity] = {}
        for key, kind, fallback_name, display, visibility, portrait_key, tags in entity_specs:
            entity = Entity(
                id=demo_id(key),
                campaign_id=campaign_id,
                kind=kind,
                name=_name(names, key, fallback_name),
                display_name=display,
                visibility=visibility,
                portrait_asset_id=assets[portrait_key].id if portrait_key else None,
                tags_json=json.dumps(["demo", *tags]),
                notes=f"Private demo note for {fallback_name}: keep GM-only context out of player display.",
                created_at=now,
                updated_at=now,
            )
            entities[key] = _add_if_missing(db, Entity, entity)
        db.flush()

        fields = [
            ("field.level", "level", "Level", "number", ["pc"], 10, True),
            ("field.role", "role", "Party Role", "short_text", ["pc"], 20, True),
            ("field.hp", "hp", "HP", "resource", ["pc"], 30, True),
            ("field.secret", "secret", "Private Burden", "long_text", ["pc", "npc"], 90, False),
        ]
        field_rows: dict[str, CustomFieldDefinition] = {}
        for key, slug, label, field_type, applies_to, order, public in fields:
            field = CustomFieldDefinition(
                id=demo_id(key),
                campaign_id=campaign_id,
                key=slug,
                label=label,
                field_type=field_type,
                applies_to_json=json.dumps(applies_to),
                required=False,
                default_value_json=None,
                options_json="[]",
                public_by_default=public,
                sort_order=order,
                created_at=now,
                updated_at=now,
            )
            field_rows[key] = _add_if_missing(db, CustomFieldDefinition, field)
        db.flush()

        value_specs = [
            ("entity.errin", "field.level", 9),
            ("entity.errin", "field.role", "Paladin / oathbound shield"),
            ("entity.errin", "field.hp", {"current": 1, "max": 74}),
            ("entity.errin", "field.secret", "She fears losing control of her oath again."),
            ("entity.drew", "field.level", 9),
            ("entity.drew", "field.role", "Glamour bard / public face"),
            ("entity.drew", "field.hp", {"current": 31, "max": 52}),
            ("entity.datt", "field.level", 9),
            ("entity.datt", "field.role", "Artificer / system thinker"),
            ("entity.datt", "field.hp", {"current": 44, "max": 59}),
            ("entity.harold", "field.level", 9),
            ("entity.harold", "field.role", "Archer / memory wound"),
            ("entity.harold", "field.hp", {"current": 38, "max": 64}),
        ]
        for entity_key, field_key, value in value_specs:
            _add_if_missing(
                db,
                CustomFieldValue,
                CustomFieldValue(
                    id=demo_id(f"value.{entity_key}.{field_key}"),
                    campaign_id=campaign_id,
                    entity_id=entities[entity_key].id,
                    field_definition_id=field_rows[field_key].id,
                    value_json=json.dumps(value),
                    created_at=now,
                    updated_at=now,
                ),
            )

        party_config = _add_if_missing(
            db,
            PartyTrackerConfig,
            PartyTrackerConfig(id=demo_id("party.config"), campaign_id=campaign_id, layout="standard", created_at=now, updated_at=now),
        )
        db.flush()
        for index, entity_key in enumerate(["entity.errin", "entity.drew", "entity.datt", "entity.harold"]):
            _add_if_missing(
                db,
                PartyTrackerMember,
                PartyTrackerMember(id=demo_id(f"party.member.{entity_key}"), config_id=party_config.id, campaign_id=campaign_id, entity_id=entities[entity_key].id, sort_order=index * 10, created_at=now, updated_at=now),
            )
        for index, field_key in enumerate(["field.level", "field.role", "field.hp"]):
            _add_if_missing(
                db,
                PartyTrackerField,
                PartyTrackerField(id=demo_id(f"party.field.{field_key}"), config_id=party_config.id, campaign_id=campaign_id, field_definition_id=field_rows[field_key].id, sort_order=index * 10, public_visible=True, created_at=now, updated_at=now),
            )

        note_source = _add_if_missing(
            db,
            NoteSource,
            NoteSource(id=demo_id("note_source.internal"), campaign_id=campaign_id, kind="internal", name="Demo notes", readonly=False, created_at=now, updated_at=now),
        )
        db.flush()
        note = _add_if_missing(
            db,
            Note,
            Note(
                id=demo_id("note.private.skra"),
                campaign_id=campaign_id,
                source_id=note_source.id,
                session_id=session_id,
                scene_id=scene_workshop_id,
                asset_id=None,
                title="GM Secret: The Glass Hour",
                private_body="PRIVATE SECRET: The Lady of the Glass Hour caused the coven's first wound. Do not reveal this in public snippets.",
                tags_json=json.dumps(["demo", "secret"]),
                source_label=None,
                created_at=now,
                updated_at=now,
            ),
        )
        db.flush()
        snippet = _add_if_missing(
            db,
            PublicSnippet,
            PublicSnippet(
                id=demo_id("snippet.public.lanterns"),
                campaign_id=campaign_id,
                note_id=note.id,
                title="The Lantern Children",
                body="The road is lined with children carrying unlit lanterns. When one lantern is kindled, a fragment of stolen time returns to the forest.",
                format="markdown",
                created_at=now,
                updated_at=now,
            ),
        )
        db.flush()

        blue_map_asset = assets["asset.blue_forest_road_map"]
        workshop_map_asset = assets["asset.crooked_loom_house_map"]
        blue_map = _add_if_missing(
            db,
            CampaignMap,
            CampaignMap(id=demo_id("map.blue_forest_road"), campaign_id=campaign_id, asset_id=blue_map_asset.id, name=_name(names, "asset.blue_forest_road_map", "Blue Forest Road Map"), width=blue_map_asset.width or 1200, height=blue_map_asset.height or 675, grid_enabled=True, grid_size_px=80, grid_offset_x=0, grid_offset_y=0, grid_color="#C7F9FF", grid_opacity=0.25, created_at=now, updated_at=now),
        )
        workshop_map = _add_if_missing(
            db,
            CampaignMap,
            CampaignMap(id=demo_id("map.crooked_loom_house"), campaign_id=campaign_id, asset_id=workshop_map_asset.id, name=_name(names, "asset.crooked_loom_house_map", "Crooked Loom House Map"), width=workshop_map_asset.width or 1200, height=workshop_map_asset.height or 900, grid_enabled=True, grid_size_px=75, grid_offset_x=10, grid_offset_y=10, grid_color="#F8F3D1", grid_opacity=0.32, created_at=now, updated_at=now),
        )
        db.flush()
        _add_if_missing(
            db,
            SceneMap,
            SceneMap(id=demo_id("scene_map.blue_road"), campaign_id=campaign_id, scene_id=scene_blue_road_id, map_id=blue_map.id, is_active=True, player_fit_mode="fit", player_grid_visible=True, created_at=now, updated_at=now),
        )
        workshop_scene_map = _add_if_missing(
            db,
            SceneMap,
            SceneMap(id=demo_id("scene_map.workshop"), campaign_id=campaign_id, scene_id=scene_workshop_id, map_id=workshop_map.id, is_active=True, player_fit_mode="fit", player_grid_visible=True, created_at=now, updated_at=now),
        )
        db.flush()
        fog_id = demo_id("fog.workshop")
        fog = _add_if_missing(
            db,
            SceneMapFogMask,
            SceneMapFogMask(id=fog_id, campaign_id=campaign_id, scene_id=scene_workshop_id, scene_map_id=workshop_scene_map.id, width=workshop_map.width, height=workshop_map.height, relative_path=fog_relative_path(fog_id), enabled=True, revision=1, created_at=now, updated_at=now),
        )
        create_hidden_mask(resolved, fog.relative_path, fog.width, fog.height)
        mask = load_mask(resolved, fog.relative_path, fog.width, fog.height)
        apply_rect(mask, FogRect(x=fog.width * 0.08, y=fog.height * 0.12, width=fog.width * 0.62, height=fog.height * 0.58), reveal=True)
        save_mask_atomic(resolved, fog.relative_path, mask)

        token_specs = [
            (
                "token.errin",
                "entity.errin",
                "Errin",
                "asset.fallen_carnival_paladin",
                workshop_map.width * 0.25,
                workshop_map.height * 0.35,
                "player_visible",
                "player_visible",
                "#F8F3D1",
            ),
            (
                "token.harold",
                "entity.harold",
                "Harold",
                "asset.redeemed_shadow_assassin",
                workshop_map.width * 0.38,
                workshop_map.height * 0.46,
                "player_visible",
                "player_visible",
                "#8FD3FF",
            ),
            (
                "token.granny_scrap",
                "entity.granny_scrap",
                "Granny Scrap",
                "asset.gray_figure_swamp",
                workshop_map.width * 0.84,
                workshop_map.height * 0.42,
                "hidden_until_revealed",
                "gm_only",
                "#D94841",
            ),
            (
                "token.illy",
                "entity.illy",
                "Illy",
                "asset.lantern_children_procession",
                workshop_map.width * 0.55,
                workshop_map.height * 0.63,
                "gm_only",
                "gm_only",
                "#F8D477",
            ),
        ]
        for index, (key, entity_key, fallback_name, asset_key, x, y, visibility, label_visibility, border_color) in enumerate(token_specs):
            _add_if_missing(
                db,
                SceneMapToken,
                SceneMapToken(id=demo_id(key), campaign_id=campaign_id, scene_id=scene_workshop_id, scene_map_id=workshop_scene_map.id, entity_id=entities[entity_key].id, asset_id=assets[asset_key].id, name=_name(names, entity_key, fallback_name), x=x, y=y, width=96, height=96, rotation=0, z_index=index * 10, visibility=visibility, label_visibility=label_visibility, shape="portrait", color="#1F2529", border_color=border_color, opacity=1, status_json="[]", created_at=now, updated_at=now),
            )

        encounter = _add_if_missing(
            db,
            CombatEncounter,
            CombatEncounter(id=demo_id("combat.workshop"), campaign_id=campaign_id, session_id=session_id, scene_id=scene_workshop_id, title="The Stolen Time Workshop", status="active", round=1, active_combatant_id=None, created_at=now, updated_at=now),
        )
        db.flush()
        combatants = [
            ("combatant.errin", "entity.errin", "Errin", "pc", 18, 0, True, ["Blessed"], ""),
            ("combatant.granny_scrap", "entity.granny_scrap", "Granny Scrap", "enemy", 14, 1, False, [], "PRIVATE CONDITION: knows Harold's missing brother."),
            ("combatant.wylan", "entity.wylan", "Wylan", "ally", 12, 2, True, ["Guarding the children"], ""),
        ]
        for key, entity_key, fallback_name, disposition, initiative, order, public_visible, public_status, notes in combatants:
            combatant = _add_if_missing(
                db,
                Combatant,
                Combatant(id=demo_id(key), campaign_id=campaign_id, encounter_id=encounter.id, entity_id=entities[entity_key].id, token_id=None, name=_name(names, entity_key, fallback_name), disposition=disposition, initiative=initiative, order_index=order, armor_class=15 if disposition == "pc" else 13, hp_current=22, hp_max=44, hp_temp=0, conditions_json=json.dumps(["PRIVATE_CONDITION"]), public_status_json=json.dumps(public_status), notes=notes, public_visible=public_visible, is_defeated=False, created_at=now, updated_at=now),
            )
            if order == 0:
                encounter.active_combatant_id = combatant.id

        context = _add_if_missing(
            db,
            SceneContext,
            SceneContext(id=demo_id("scene_context.workshop"), campaign_id=campaign_id, scene_id=scene_workshop_id, active_encounter_id=encounter.id, staged_display_mode="active_map", staged_public_snippet_id=snippet.id, created_at=now, updated_at=now),
        )
        context.active_encounter_id = encounter.id
        context.staged_display_mode = "active_map"
        context.staged_public_snippet_id = snippet.id
        for index, entity_key in enumerate(["entity.granny_scrap", "entity.illy", "entity.aureon", "entity.harold"]):
            _add_if_missing(
                db,
                SceneEntityLink,
                SceneEntityLink(id=demo_id(f"scene_entity_link.workshop.{entity_key}"), campaign_id=campaign_id, scene_id=scene_workshop_id, entity_id=entities[entity_key].id, role="featured" if index < 2 else "clue", sort_order=index * 10, notes="GM-only scene relevance.", created_at=now, updated_at=now),
            )
        _add_if_missing(
            db,
            ScenePublicSnippetLink,
            ScenePublicSnippetLink(id=demo_id("scene_snippet_link.workshop.lanterns"), campaign_id=campaign_id, scene_id=scene_workshop_id, public_snippet_id=snippet.id, sort_order=0, created_at=now, updated_at=now),
        )

        runtime = db.get(AppRuntime, RUNTIME_ID)
        if runtime is None:
            db.add(AppRuntime(id=RUNTIME_ID, active_campaign_id=campaign_id, active_session_id=session_id, active_scene_id=scene_workshop_id, updated_at=now))
        else:
            runtime.active_campaign_id = campaign_id
            runtime.active_session_id = session_id
            runtime.active_scene_id = scene_workshop_id
            runtime.updated_at = now

        display = db.get(PlayerDisplayRuntime, PLAYER_DISPLAY_ID)
        if display is None:
            db.add(PlayerDisplayRuntime(id=PLAYER_DISPLAY_ID, mode="blackout", active_campaign_id=None, active_session_id=None, active_scene_id=None, title=None, subtitle=None, payload_json="{}", revision=1, identify_revision=0, identify_until=None, updated_at=now))

    return DemoSeedResult(campaign_id=campaign_id, private_name_map_active=bool(names))


def main() -> None:
    result = seed_demo_profile()
    suffix = " with local demo override map" if result.private_name_map_active else ""
    print(f"Seeded demo profile {DEMO_PROFILE}{suffix}: {result.campaign_id}")


if __name__ == "__main__":
    main()
