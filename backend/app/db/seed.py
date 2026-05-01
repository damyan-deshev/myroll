from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.app.db.engine import get_engine
from backend.app.db.models import (
    AppMeta,
    AppRuntime,
    Campaign,
    CombatEncounter,
    Combatant,
    CustomFieldDefinition,
    CustomFieldValue,
    DisplayState,
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
    ScenePublicSnippetLink,
    Session,
    WorkspaceWidget,
)
from backend.app.db.seed_ids import deterministic_uuid
from backend.app.settings import Settings, get_settings
from backend.app.time import utc_now_z
from backend.app.workspace_defaults import DEFAULT_WORKSPACE_WIDGETS


DEMO_SEED_VERSION = "2026-04-27-v12"
SEED_META_KEY = "dev_seed_version"
RUNTIME_ID = "runtime"
PLAYER_DISPLAY_ID = "player_display"


DEMO_CAMPAIGN_ID = deterministic_uuid("demo-campaign:ship-ambush")
DEMO_SESSION_ID = deterministic_uuid("demo-session:session-001")
DEMO_SCENE_ID = deterministic_uuid("demo-scene:ship-ambush")
DEMO_DISPLAY_STATE_ID = deterministic_uuid("demo-display-state:blackout")
DEMO_NOTE_SOURCE_ID = deterministic_uuid("demo-note-source:internal")
DEMO_NOTE_ID = deterministic_uuid("demo-note:ship-ambush")
DEMO_PUBLIC_SNIPPET_ID = deterministic_uuid("demo-public-snippet:ship-ambush")
DEMO_PC_ARIA_ID = deterministic_uuid("demo-entity:pc:aria")
DEMO_PC_BRAM_ID = deterministic_uuid("demo-entity:pc:bram")
DEMO_FIELD_LEVEL_ID = deterministic_uuid("demo-custom-field:level")
DEMO_FIELD_HP_ID = deterministic_uuid("demo-custom-field:hp")
DEMO_FIELD_ROLE_ID = deterministic_uuid("demo-custom-field:role")
DEMO_FIELD_SECRET_ID = deterministic_uuid("demo-custom-field:secret")
DEMO_ARIA_LEVEL_VALUE_ID = deterministic_uuid("demo-field-value:aria:level")
DEMO_ARIA_HP_VALUE_ID = deterministic_uuid("demo-field-value:aria:hp")
DEMO_ARIA_ROLE_VALUE_ID = deterministic_uuid("demo-field-value:aria:role")
DEMO_ARIA_SECRET_VALUE_ID = deterministic_uuid("demo-field-value:aria:secret")
DEMO_BRAM_LEVEL_VALUE_ID = deterministic_uuid("demo-field-value:bram:level")
DEMO_BRAM_HP_VALUE_ID = deterministic_uuid("demo-field-value:bram:hp")
DEMO_BRAM_ROLE_VALUE_ID = deterministic_uuid("demo-field-value:bram:role")
DEMO_PARTY_CONFIG_ID = deterministic_uuid("demo-party-tracker:ship-ambush")
DEMO_PARTY_MEMBER_ARIA_ID = deterministic_uuid("demo-party-member:aria")
DEMO_PARTY_MEMBER_BRAM_ID = deterministic_uuid("demo-party-member:bram")
DEMO_PARTY_FIELD_LEVEL_ID = deterministic_uuid("demo-party-field:level")
DEMO_PARTY_FIELD_HP_ID = deterministic_uuid("demo-party-field:hp")
DEMO_PARTY_FIELD_ROLE_ID = deterministic_uuid("demo-party-field:role")
DEMO_COMBAT_ENCOUNTER_ID = deterministic_uuid("demo-combat-encounter:deck-skirmish")
DEMO_COMBATANT_ARIA_ID = deterministic_uuid("demo-combatant:aria")
DEMO_COMBATANT_FIRST_MATE_ID = deterministic_uuid("demo-combatant:first-mate")
DEMO_COMBATANT_BRAM_ID = deterministic_uuid("demo-combatant:bram")
DEMO_SCENE_CONTEXT_ID = deterministic_uuid("demo-scene-context:ship-ambush")
DEMO_SCENE_ENTITY_LINK_ARIA_ID = deterministic_uuid("demo-scene-entity-link:ship-ambush:aria")
DEMO_SCENE_ENTITY_LINK_BRAM_ID = deterministic_uuid("demo-scene-entity-link:ship-ambush:bram")
DEMO_SCENE_PUBLIC_SNIPPET_LINK_ID = deterministic_uuid("demo-scene-snippet-link:ship-ambush:clue")


@dataclass(frozen=True)
class SeedResult:
    applied: bool
    seed_version: str


def _upsert_row(connection, table, values: dict, key: str = "id") -> None:  # noqa: ANN001
    statement = sqlite_insert(table).values(**values)
    update_values = {column: value for column, value in values.items() if column != key}
    statement = statement.on_conflict_do_update(index_elements=[key], set_=update_values)
    connection.execute(statement)


def _set_seed_marker(connection, now: str) -> None:  # noqa: ANN001
    _upsert_row(
        connection,
        AppMeta.__table__,
        {"key": SEED_META_KEY, "value": DEMO_SEED_VERSION, "updated_at": now},
        key="key",
    )


def _insert_runtime_if_missing(connection, now: str) -> None:  # noqa: ANN001
    statement = sqlite_insert(AppRuntime.__table__).values(
        id=RUNTIME_ID,
        active_campaign_id=None,
        active_session_id=None,
        active_scene_id=None,
        updated_at=now,
    )
    connection.execute(statement.on_conflict_do_nothing(index_elements=["id"]))


def _insert_default_widgets_if_missing(connection, now: str) -> None:  # noqa: ANN001
    for widget in DEFAULT_WORKSPACE_WIDGETS:
        statement = sqlite_insert(WorkspaceWidget.__table__).values(
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
        )
        connection.execute(statement.on_conflict_do_nothing(index_elements=["id"]))


def _insert_player_display_if_missing(connection, now: str) -> None:  # noqa: ANN001
    statement = sqlite_insert(PlayerDisplayRuntime.__table__).values(
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
        updated_at=now,
    )
    connection.execute(statement.on_conflict_do_nothing(index_elements=["id"]))


def _insert_demo_notes_if_missing(connection, now: str) -> None:  # noqa: ANN001
    source_statement = sqlite_insert(NoteSource.__table__).values(
        id=DEMO_NOTE_SOURCE_ID,
        campaign_id=DEMO_CAMPAIGN_ID,
        kind="internal",
        name="Demo Notes",
        readonly=False,
        created_at=now,
        updated_at=now,
    )
    connection.execute(source_statement.on_conflict_do_nothing(index_elements=["id"]))

    note_statement = sqlite_insert(Note.__table__).values(
        id=DEMO_NOTE_ID,
        campaign_id=DEMO_CAMPAIGN_ID,
        source_id=DEMO_NOTE_SOURCE_ID,
        session_id=DEMO_SESSION_ID,
        scene_id=DEMO_SCENE_ID,
        asset_id=None,
        title="Ship Ambush GM Notes",
        private_body=(
            "# Ship Ambush\n\n"
            "Private GM note: the first mate is hiding the real cargo manifest.\n\n"
            "Public clue: Salt-stained boot prints lead toward the sealed hold."
        ),
        tags_json=json.dumps(["demo", "scene"]),
        source_label="Demo Notes",
        created_at=now,
        updated_at=now,
    )
    connection.execute(note_statement.on_conflict_do_nothing(index_elements=["id"]))

    snippet_statement = sqlite_insert(PublicSnippet.__table__).values(
        id=DEMO_PUBLIC_SNIPPET_ID,
        campaign_id=DEMO_CAMPAIGN_ID,
        note_id=DEMO_NOTE_ID,
        title="A clue on the deck",
        body="Salt-stained boot prints lead toward the sealed hold.",
        format="markdown",
        created_at=now,
        updated_at=now,
    )
    connection.execute(snippet_statement.on_conflict_do_nothing(index_elements=["id"]))


def _insert_demo_entities_if_missing(connection, now: str) -> None:  # noqa: ANN001
    for values in (
        {
            "id": DEMO_PC_ARIA_ID,
            "campaign_id": DEMO_CAMPAIGN_ID,
            "kind": "pc",
            "name": "Aria Vell",
            "display_name": "Aria",
            "visibility": "public_known",
            "portrait_asset_id": None,
            "tags_json": json.dumps(["demo", "party"]),
            "notes": "Private demo note: Aria suspects the first mate.",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": DEMO_PC_BRAM_ID,
            "campaign_id": DEMO_CAMPAIGN_ID,
            "kind": "pc",
            "name": "Bram Kest",
            "display_name": "Bram",
            "visibility": "public_known",
            "portrait_asset_id": None,
            "tags_json": json.dumps(["demo", "party"]),
            "notes": "Private demo note: Bram is watching the rigging.",
            "created_at": now,
            "updated_at": now,
        },
    ):
        connection.execute(sqlite_insert(Entity.__table__).values(**values).on_conflict_do_nothing(index_elements=["id"]))

    for values in (
        {
            "id": DEMO_FIELD_LEVEL_ID,
            "campaign_id": DEMO_CAMPAIGN_ID,
            "key": "level",
            "label": "Level",
            "field_type": "number",
            "applies_to_json": json.dumps(["pc"]),
            "required": False,
            "default_value_json": None,
            "options_json": json.dumps([]),
            "public_by_default": True,
            "sort_order": 10,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": DEMO_FIELD_HP_ID,
            "campaign_id": DEMO_CAMPAIGN_ID,
            "key": "hp",
            "label": "HP",
            "field_type": "resource",
            "applies_to_json": json.dumps(["pc"]),
            "required": False,
            "default_value_json": None,
            "options_json": json.dumps([]),
            "public_by_default": True,
            "sort_order": 20,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": DEMO_FIELD_ROLE_ID,
            "campaign_id": DEMO_CAMPAIGN_ID,
            "key": "role",
            "label": "Role",
            "field_type": "select",
            "applies_to_json": json.dumps(["pc"]),
            "required": False,
            "default_value_json": None,
            "options_json": json.dumps(["Striker", "Support", "Face"]),
            "public_by_default": True,
            "sort_order": 30,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": DEMO_FIELD_SECRET_ID,
            "campaign_id": DEMO_CAMPAIGN_ID,
            "key": "secret",
            "label": "Secret",
            "field_type": "long_text",
            "applies_to_json": json.dumps(["pc"]),
            "required": False,
            "default_value_json": None,
            "options_json": json.dumps([]),
            "public_by_default": False,
            "sort_order": 99,
            "created_at": now,
            "updated_at": now,
        },
    ):
        connection.execute(sqlite_insert(CustomFieldDefinition.__table__).values(**values).on_conflict_do_nothing(index_elements=["id"]))

    for values in (
        (DEMO_ARIA_LEVEL_VALUE_ID, DEMO_PC_ARIA_ID, DEMO_FIELD_LEVEL_ID, 5),
        (DEMO_ARIA_HP_VALUE_ID, DEMO_PC_ARIA_ID, DEMO_FIELD_HP_ID, {"current": 22, "max": 31}),
        (DEMO_ARIA_ROLE_VALUE_ID, DEMO_PC_ARIA_ID, DEMO_FIELD_ROLE_ID, "Face"),
        (DEMO_ARIA_SECRET_VALUE_ID, DEMO_PC_ARIA_ID, DEMO_FIELD_SECRET_ID, "Secret phrase: demo private field"),
        (DEMO_BRAM_LEVEL_VALUE_ID, DEMO_PC_BRAM_ID, DEMO_FIELD_LEVEL_ID, 4),
        (DEMO_BRAM_HP_VALUE_ID, DEMO_PC_BRAM_ID, DEMO_FIELD_HP_ID, {"current": 28, "max": 28}),
        (DEMO_BRAM_ROLE_VALUE_ID, DEMO_PC_BRAM_ID, DEMO_FIELD_ROLE_ID, "Striker"),
    ):
        value_id, entity_id, field_id, value = values
        connection.execute(
            sqlite_insert(CustomFieldValue.__table__)
            .values(
                id=value_id,
                campaign_id=DEMO_CAMPAIGN_ID,
                entity_id=entity_id,
                field_definition_id=field_id,
                value_json=json.dumps(value),
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )

    connection.execute(
        sqlite_insert(PartyTrackerConfig.__table__)
        .values(
            id=DEMO_PARTY_CONFIG_ID,
            campaign_id=DEMO_CAMPAIGN_ID,
            layout="standard",
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["campaign_id"])
    )
    for values in (
        (DEMO_PARTY_MEMBER_ARIA_ID, DEMO_PC_ARIA_ID, 0),
        (DEMO_PARTY_MEMBER_BRAM_ID, DEMO_PC_BRAM_ID, 1),
    ):
        member_id, entity_id, sort_order = values
        connection.execute(
            sqlite_insert(PartyTrackerMember.__table__)
            .values(
                id=member_id,
                config_id=DEMO_PARTY_CONFIG_ID,
                campaign_id=DEMO_CAMPAIGN_ID,
                entity_id=entity_id,
                sort_order=sort_order,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
    for values in (
        (DEMO_PARTY_FIELD_LEVEL_ID, DEMO_FIELD_LEVEL_ID, 0, True),
        (DEMO_PARTY_FIELD_HP_ID, DEMO_FIELD_HP_ID, 1, True),
        (DEMO_PARTY_FIELD_ROLE_ID, DEMO_FIELD_ROLE_ID, 2, True),
    ):
        party_field_id, field_id, sort_order, public_visible = values
        connection.execute(
            sqlite_insert(PartyTrackerField.__table__)
            .values(
                id=party_field_id,
                config_id=DEMO_PARTY_CONFIG_ID,
                campaign_id=DEMO_CAMPAIGN_ID,
                field_definition_id=field_id,
                sort_order=sort_order,
                public_visible=public_visible,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )


def _insert_demo_combat_if_missing(connection, now: str) -> None:  # noqa: ANN001
    connection.execute(
        sqlite_insert(CombatEncounter.__table__)
        .values(
            id=DEMO_COMBAT_ENCOUNTER_ID,
            campaign_id=DEMO_CAMPAIGN_ID,
            session_id=DEMO_SESSION_ID,
            scene_id=DEMO_SCENE_ID,
            title="Deck Skirmish",
            status="active",
            round=1,
            active_combatant_id=DEMO_COMBATANT_ARIA_ID,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    for values in (
        {
            "id": DEMO_COMBATANT_ARIA_ID,
            "campaign_id": DEMO_CAMPAIGN_ID,
            "encounter_id": DEMO_COMBAT_ENCOUNTER_ID,
            "entity_id": DEMO_PC_ARIA_ID,
            "token_id": None,
            "name": "Aria",
            "disposition": "pc",
            "initiative": 18,
            "order_index": 0,
            "armor_class": 15,
            "hp_current": 22,
            "hp_max": 31,
            "hp_temp": 0,
            "conditions_json": json.dumps([{"label": "Privately watching the first mate"}]),
            "public_status_json": json.dumps(["Ready"]),
            "notes": "Private combat note: Aria wants the first mate alive.",
            "public_visible": True,
            "is_defeated": False,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": DEMO_COMBATANT_FIRST_MATE_ID,
            "campaign_id": DEMO_CAMPAIGN_ID,
            "encounter_id": DEMO_COMBAT_ENCOUNTER_ID,
            "entity_id": None,
            "token_id": None,
            "name": "First Mate",
            "disposition": "enemy",
            "initiative": 14,
            "order_index": 1,
            "armor_class": 13,
            "hp_current": 18,
            "hp_max": 18,
            "hp_temp": 0,
            "conditions_json": json.dumps([{"label": "Secretly stalling"}]),
            "public_status_json": json.dumps([]),
            "notes": "Private combat note: knows the cargo manifest location.",
            "public_visible": False,
            "is_defeated": False,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": DEMO_COMBATANT_BRAM_ID,
            "campaign_id": DEMO_CAMPAIGN_ID,
            "encounter_id": DEMO_COMBAT_ENCOUNTER_ID,
            "entity_id": DEMO_PC_BRAM_ID,
            "token_id": None,
            "name": "Bram",
            "disposition": "pc",
            "initiative": 12,
            "order_index": 2,
            "armor_class": 16,
            "hp_current": 28,
            "hp_max": 28,
            "hp_temp": 0,
            "conditions_json": json.dumps([]),
            "public_status_json": json.dumps([{"label": "Guarding"}]),
            "notes": "Private combat note: Bram is watching the rigging.",
            "public_visible": True,
            "is_defeated": False,
            "created_at": now,
            "updated_at": now,
        },
    ):
        connection.execute(sqlite_insert(Combatant.__table__).values(**values).on_conflict_do_nothing(index_elements=["id"]))


def _insert_demo_scene_context_if_missing(connection, now: str) -> None:  # noqa: ANN001
    connection.execute(
        sqlite_insert(SceneContext.__table__)
        .values(
            id=DEMO_SCENE_CONTEXT_ID,
            campaign_id=DEMO_CAMPAIGN_ID,
            scene_id=DEMO_SCENE_ID,
            active_encounter_id=DEMO_COMBAT_ENCOUNTER_ID,
            staged_display_mode="scene_title",
            staged_public_snippet_id=None,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["scene_id"])
    )
    for values in (
        {
            "id": DEMO_SCENE_ENTITY_LINK_ARIA_ID,
            "campaign_id": DEMO_CAMPAIGN_ID,
            "scene_id": DEMO_SCENE_ID,
            "entity_id": DEMO_PC_ARIA_ID,
            "role": "featured",
            "sort_order": 0,
            "notes": "Demo scene focus PC.",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": DEMO_SCENE_ENTITY_LINK_BRAM_ID,
            "campaign_id": DEMO_CAMPAIGN_ID,
            "scene_id": DEMO_SCENE_ID,
            "entity_id": DEMO_PC_BRAM_ID,
            "role": "supporting",
            "sort_order": 1,
            "notes": "Demo scene supporting PC.",
            "created_at": now,
            "updated_at": now,
        },
    ):
        connection.execute(
            sqlite_insert(SceneEntityLink.__table__)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["scene_id", "entity_id"])
        )
    connection.execute(
        sqlite_insert(ScenePublicSnippetLink.__table__)
        .values(
            id=DEMO_SCENE_PUBLIC_SNIPPET_LINK_ID,
            campaign_id=DEMO_CAMPAIGN_ID,
            scene_id=DEMO_SCENE_ID,
            public_snippet_id=DEMO_PUBLIC_SNIPPET_ID,
            sort_order=0,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["scene_id", "public_snippet_id"])
    )


def seed_demo_data(settings: Settings | None = None) -> SeedResult:
    resolved = settings or get_settings()
    engine = get_engine(resolved)
    with engine.begin() as connection:
        current = connection.execute(
            select(AppMeta.value).where(AppMeta.key == SEED_META_KEY)
        ).scalar_one_or_none()
        if current == DEMO_SEED_VERSION:
            return SeedResult(applied=False, seed_version=DEMO_SEED_VERSION)

        now = utc_now_z()
        _upsert_row(
            connection,
            Campaign.__table__,
            {
                "id": DEMO_CAMPAIGN_ID,
                "name": "Demo Campaign: Ship Ambush",
                "description": "Seeded local demo campaign for backend smoke tests and future UI demos.",
                "created_at": now,
                "updated_at": now,
            },
        )
        _upsert_row(
            connection,
            Session.__table__,
            {
                "id": DEMO_SESSION_ID,
                "campaign_id": DEMO_CAMPAIGN_ID,
                "title": "Session 001: Cold Open",
                "starts_at": None,
                "ended_at": None,
                "created_at": now,
                "updated_at": now,
            },
        )
        _upsert_row(
            connection,
            Scene.__table__,
            {
                "id": DEMO_SCENE_ID,
                "campaign_id": DEMO_CAMPAIGN_ID,
                "session_id": DEMO_SESSION_ID,
                "title": "Ship Ambush",
                "summary": "A compact demo scene for validating campaign and scene reads.",
                "created_at": now,
                "updated_at": now,
            },
        )
        _upsert_row(
            connection,
            DisplayState.__table__,
            {
                "id": DEMO_DISPLAY_STATE_ID,
                "campaign_id": DEMO_CAMPAIGN_ID,
                "scene_id": DEMO_SCENE_ID,
                "mode": "blackout",
                "payload_json": json.dumps({"type": "blackout", "message": "Demo display is private."}),
                "created_at": now,
                "updated_at": now,
            },
        )
        _insert_runtime_if_missing(connection, now)
        _insert_player_display_if_missing(connection, now)
        _insert_default_widgets_if_missing(connection, now)
        _insert_demo_notes_if_missing(connection, now)
        _insert_demo_entities_if_missing(connection, now)
        _insert_demo_combat_if_missing(connection, now)
        _insert_demo_scene_context_if_missing(connection, now)
        _set_seed_marker(connection, now)
        return SeedResult(applied=True, seed_version=DEMO_SEED_VERSION)


def main() -> None:
    result = seed_demo_data()
    if result.applied:
        print(f"Applied demo seed {result.seed_version}.")
    else:
        print(f"Demo seed {result.seed_version} already applied.")


if __name__ == "__main__":
    main()
