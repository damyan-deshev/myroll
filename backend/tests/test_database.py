from __future__ import annotations

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

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
    WorkspaceWidget,
)
from backend.app.db.seed import (
    DEMO_CAMPAIGN_ID,
    DEMO_SEED_VERSION,
    PLAYER_DISPLAY_ID,
    RUNTIME_ID,
    SEED_META_KEY,
    seed_demo_data,
)
from backend.app.time import utc_now_z
from backend.app.workspace_defaults import DEFAULT_WORKSPACE_WIDGETS


def test_sqlite_pragmas_are_applied_on_connection(test_settings):
    engine = get_engine(test_settings)
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one().lower() == "wal"
        assert connection.exec_driver_sql("PRAGMA synchronous").scalar_one() == 1
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 5000


def test_app_runtime_is_constrained_singleton(migrated_settings):
    engine = get_engine(migrated_settings)
    with engine.begin() as connection:
        sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'app_runtime'"
        ).scalar_one()
        assert "ck_app_runtime_singleton" in sql
        assert "id = 'runtime'" in sql
        with pytest.raises(IntegrityError):
            connection.execute(insert(AppRuntime).values(id="other", updated_at=utc_now_z()))


def test_player_display_runtime_is_constrained_singleton_and_mode(migrated_settings):
    engine = get_engine(migrated_settings)
    with engine.begin() as connection:
        sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'player_display_runtime'"
        ).scalar_one()
        assert "ck_player_display_runtime_singleton" in sql
        assert "id = 'player_display'" in sql
        assert "ck_player_display_runtime_mode" in sql
        assert "blackout" in sql
        assert "image" in sql
        assert "map" in sql
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(PlayerDisplayRuntime).values(
                    id="other",
                    mode="blackout",
                    payload_json="{}",
                    revision=1,
                    identify_revision=0,
                    updated_at=utc_now_z(),
                )
            )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(PlayerDisplayRuntime).values(
                    id=PLAYER_DISPLAY_ID,
                    mode="map_but_not_really",
                    payload_json="{}",
                    revision=1,
                    identify_revision=0,
                    updated_at=utc_now_z(),
                )
            )


def test_assets_have_metadata_and_visibility_constraints(migrated_settings):
    engine = get_engine(migrated_settings)
    now = utc_now_z()
    with engine.begin() as connection:
        sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'assets'"
        ).scalar_one()
        assert "ck_assets_kind" in sql
        assert "ck_assets_visibility" in sql
        assert "name" in sql
        assert "visibility" in sql
        assert "tags_json" in sql

        connection.execute(
            insert(Campaign).values(
                id=DEMO_CAMPAIGN_ID,
                name="Demo",
                description=None,
                created_at=now,
                updated_at=now,
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(Asset).values(
                    id="376d584d-f14e-4f53-a020-8ecbbf8f2357",
                    campaign_id=DEMO_CAMPAIGN_ID,
                    kind="mystery",
                    visibility="private",
                    name="Bad Kind",
                    mime_type="image/png",
                    byte_size=10,
                    checksum="abc",
                    relative_path="ab/abc.png",
                    width=1,
                    height=1,
                    tags_json="[]",
                    created_at=now,
                    updated_at=now,
                )
            )


def test_maps_and_scene_maps_schema_enforce_active_scene_map_invariant(migrated_settings):
    engine = get_engine(migrated_settings)
    now = utc_now_z()
    campaign_id = "c95dc136-3c37-4180-b04b-2d31c9c272b5"
    scene_id = "c2b82df1-29fd-4879-b9fb-ac1dce1de1e6"
    asset_a_id = "79780a44-637d-40a3-9f73-28dd2c65a248"
    asset_b_id = "4ca8bdf7-8e20-4939-a6bb-a1a88fe17f1c"
    map_a_id = "936daaa4-5a0a-491b-8232-f95048907397"
    map_b_id = "cc0a81f1-a706-4c86-b9b6-8f59f89109cf"

    with engine.begin() as connection:
        maps_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'maps'"
        ).scalar_one()
        scene_maps_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'scene_maps'"
        ).scalar_one()
        index_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'uq_scene_maps_one_active_per_scene'"
        ).scalar_one()
        assert "ck_maps_grid_size" in maps_sql
        assert "ck_maps_grid_opacity" in maps_sql
        assert "ck_scene_maps_player_fit_mode" in scene_maps_sql
        assert "WHERE is_active = 1" in index_sql

        connection.execute(
            insert(Campaign).values(
                id=campaign_id,
                name="Map Campaign",
                description=None,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(Scene).values(
                id=scene_id,
                campaign_id=campaign_id,
                session_id=None,
                title="Map Scene",
                summary=None,
                created_at=now,
                updated_at=now,
            )
        )
        for asset_id, checksum in [(asset_a_id, "aaa"), (asset_b_id, "bbb")]:
            connection.execute(
                insert(Asset).values(
                    id=asset_id,
                    campaign_id=campaign_id,
                    kind="map_image",
                    visibility="public_displayable",
                    name=f"Asset {checksum}",
                    mime_type="image/png",
                    byte_size=10,
                    checksum=checksum,
                    relative_path=f"{checksum}/{checksum}.png",
                    original_filename=f"{checksum}.png",
                    width=10,
                    height=10,
                    duration_ms=None,
                    tags_json="[]",
                    created_at=now,
                    updated_at=now,
                )
            )
        for map_id, asset_id in [(map_a_id, asset_a_id), (map_b_id, asset_b_id)]:
            connection.execute(
                insert(CampaignMap).values(
                    id=map_id,
                    campaign_id=campaign_id,
                    asset_id=asset_id,
                    name=f"Map {asset_id}",
                    width=10,
                    height=10,
                    grid_enabled=False,
                    grid_size_px=70,
                    grid_offset_x=0,
                    grid_offset_y=0,
                    grid_color="#FFFFFF",
                    grid_opacity=0.35,
                    created_at=now,
                    updated_at=now,
                )
            )
        connection.execute(
            insert(SceneMap).values(
                id="539d05cc-c49a-48b2-bae3-d8f9134352e8",
                campaign_id=campaign_id,
                scene_id=scene_id,
                map_id=map_a_id,
                is_active=True,
                player_fit_mode="fit",
                player_grid_visible=True,
                created_at=now,
                updated_at=now,
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(SceneMap).values(
                    id="ce1b7c86-05f0-4508-828f-72c0122d96d8",
                    campaign_id=campaign_id,
                    scene_id=scene_id,
                    map_id=map_b_id,
                    is_active=True,
                    player_fit_mode="fit",
                    player_grid_visible=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(Asset).values(
                    id="edff1d9b-e161-463f-a95a-5696d65ed0b3",
                    campaign_id=DEMO_CAMPAIGN_ID,
                    kind="handout_image",
                    visibility="everyone",
                    name="Bad Visibility",
                    mime_type="image/png",
                    byte_size=10,
                    checksum="def",
                    relative_path="de/def.png",
                    width=1,
                    height=1,
                    tags_json="[]",
                    created_at=now,
                    updated_at=now,
                )
            )


def test_scene_map_fog_masks_schema_enforces_one_mask_per_scene_map(migrated_settings):
    engine = get_engine(migrated_settings)
    now = utc_now_z()
    campaign_id = "4b9c631e-0039-44b1-a611-1ed5401aeedc"
    scene_id = "38e6d8b8-b621-4d96-9c6d-dc891fdb8024"
    asset_id = "43ce5700-16e9-4b10-a5d3-64a1a0516d67"
    map_id = "e7947f9b-ae2d-4c66-893b-b77a7f9bdd7d"
    scene_map_id = "78e352f3-4a8c-42fb-a5c0-9cde5b697c49"

    with engine.begin() as connection:
        sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'scene_map_fog_masks'"
        ).scalar_one()
        assert "ck_scene_map_fog_masks_width_positive" in sql
        assert "ck_scene_map_fog_masks_height_positive" in sql
        assert "ck_scene_map_fog_masks_revision_positive" in sql
        assert "uq_scene_map_fog_masks_scene_map_id" in sql

        connection.execute(
            insert(Campaign).values(
                id=campaign_id,
                name="Fog Campaign",
                description=None,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(Scene).values(
                id=scene_id,
                campaign_id=campaign_id,
                session_id=None,
                title="Fog Scene",
                summary=None,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(Asset).values(
                id=asset_id,
                campaign_id=campaign_id,
                kind="map_image",
                visibility="public_displayable",
                name="Fog Asset",
                mime_type="image/png",
                byte_size=10,
                checksum="fog",
                relative_path="fo/fog.png",
                original_filename="fog.png",
                width=10,
                height=10,
                duration_ms=None,
                tags_json="[]",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(CampaignMap).values(
                id=map_id,
                campaign_id=campaign_id,
                asset_id=asset_id,
                name="Fog Map",
                width=10,
                height=10,
                grid_enabled=False,
                grid_size_px=70,
                grid_offset_x=0,
                grid_offset_y=0,
                grid_color="#FFFFFF",
                grid_opacity=0.35,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(SceneMap).values(
                id=scene_map_id,
                campaign_id=campaign_id,
                scene_id=scene_id,
                map_id=map_id,
                is_active=True,
                player_fit_mode="fit",
                player_grid_visible=True,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(SceneMapFogMask).values(
                id="8076043a-1f02-4510-8aee-8fab421708ef",
                campaign_id=campaign_id,
                scene_id=scene_id,
                scene_map_id=scene_map_id,
                width=10,
                height=10,
                relative_path="fog/8076043a-1f02-4510-8aee-8fab421708ef.png",
                enabled=True,
                revision=1,
                created_at=now,
                updated_at=now,
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(SceneMapFogMask).values(
                    id="026bd1e6-e272-4f23-af74-9ca005b0516d",
                    campaign_id=campaign_id,
                    scene_id=scene_id,
                    scene_map_id=scene_map_id,
                    width=10,
                    height=10,
                    relative_path="fog/026bd1e6-e272-4f23-af74-9ca005b0516d.png",
                    enabled=True,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                )
            )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(SceneMapFogMask).values(
                    id="82c4f26d-6a0a-427a-8746-1bf31a3a6328",
                    campaign_id=campaign_id,
                    scene_id=scene_id,
                    scene_map_id="539d05cc-c49a-48b2-bae3-d8f9134352e8",
                    width=0,
                    height=10,
                    relative_path="fog/82c4f26d-6a0a-427a-8746-1bf31a3a6328.png",
                    enabled=True,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                )
            )


def test_scene_map_tokens_schema_enforces_visibility_shape_and_geometry(migrated_settings):
    engine = get_engine(migrated_settings)
    now = utc_now_z()
    campaign_id = "97ace7f8-8fb0-4f48-82bc-c248030710b8"
    scene_id = "34f5ce6a-1da1-4453-b47b-53886c62e3a5"
    asset_id = "e55f07f4-7e04-4ccb-bc3f-15d9a1c3904f"
    map_id = "cce22ecf-11d5-40cc-a0c7-f42c7685ffcc"
    scene_map_id = "edb6001c-3f94-43a0-8b3f-94486e0fca1a"

    with engine.begin() as connection:
        sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'scene_map_tokens'"
        ).scalar_one()
        assert "ck_scene_map_tokens_visibility" in sql
        assert "hidden_until_revealed" in sql
        assert "ck_scene_map_tokens_label_visibility" in sql
        assert "ck_scene_map_tokens_shape" in sql
        assert "ck_scene_map_tokens_rotation" in sql

        connection.execute(
            insert(Campaign).values(
                id=campaign_id,
                name="Token Campaign",
                description=None,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(Scene).values(
                id=scene_id,
                campaign_id=campaign_id,
                session_id=None,
                title="Token Scene",
                summary=None,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(Asset).values(
                id=asset_id,
                campaign_id=campaign_id,
                kind="map_image",
                visibility="public_displayable",
                name="Token Asset",
                mime_type="image/png",
                byte_size=10,
                checksum="tok",
                relative_path="to/tok.png",
                original_filename="tok.png",
                width=10,
                height=10,
                duration_ms=None,
                tags_json="[]",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(CampaignMap).values(
                id=map_id,
                campaign_id=campaign_id,
                asset_id=asset_id,
                name="Token Map",
                width=10,
                height=10,
                grid_enabled=False,
                grid_size_px=70,
                grid_offset_x=0,
                grid_offset_y=0,
                grid_color="#FFFFFF",
                grid_opacity=0.35,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(SceneMap).values(
                id=scene_map_id,
                campaign_id=campaign_id,
                scene_id=scene_id,
                map_id=map_id,
                is_active=True,
                player_fit_mode="fit",
                player_grid_visible=True,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(SceneMapToken).values(
                id="92ca5a46-851f-4c22-876b-c5518661b2cb",
                campaign_id=campaign_id,
                scene_id=scene_id,
                scene_map_id=scene_map_id,
                name="Visible Token",
                x=5,
                y=5,
                width=2,
                height=2,
                rotation=0,
                z_index=0,
                visibility="player_visible",
                label_visibility="player_visible",
                shape="circle",
                color="#D94841",
                border_color="#FFFFFF",
                opacity=1,
                status_json="[]",
                created_at=now,
                updated_at=now,
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(SceneMapToken).values(
                    id="262f3293-b2b9-450b-b621-01b5ccff3331",
                    campaign_id=campaign_id,
                    scene_id=scene_id,
                    scene_map_id=scene_map_id,
                    name="Bad Token",
                    x=5,
                    y=5,
                    width=2,
                    height=2,
                    rotation=360,
                    z_index=0,
                    visibility="everyone",
                    label_visibility="player_visible",
                    shape="circle",
                    color="#D94841",
                    border_color="#FFFFFF",
                    opacity=1,
                    status_json="[]",
                    created_at=now,
                    updated_at=now,
                )
            )


def test_notes_public_snippets_schema_and_text_display_mode(migrated_settings):
    engine = get_engine(migrated_settings)
    now = utc_now_z()
    campaign_id = "26920fee-bd61-461b-8155-49ec4a012c93"
    source_id = "684c0919-ebd6-4f33-9d70-1028321917c7"
    note_id = "ff20a18a-eb45-4d24-a985-610be98f416a"

    with engine.begin() as connection:
        notes_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'notes'"
        ).scalar_one()
        snippets_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'public_snippets'"
        ).scalar_one()
        display_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'player_display_runtime'"
        ).scalar_one()
        assert "private_body" in notes_sql
        assert "ck_public_snippets_format" in snippets_sql
        assert "'text'" in display_sql

        connection.execute(
            insert(Campaign).values(
                id=campaign_id,
                name="Notes Campaign",
                description=None,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(NoteSource).values(
                id=source_id,
                campaign_id=campaign_id,
                kind="internal",
                name="Internal Notes",
                readonly=False,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(Note).values(
                id=note_id,
                campaign_id=campaign_id,
                source_id=source_id,
                session_id=None,
                scene_id=None,
                asset_id=None,
                title="Private Note",
                private_body="Secret body",
                tags_json="[]",
                source_label="Internal Notes",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(PublicSnippet).values(
                id="cdf0f35b-b8fd-474f-8a95-6c6a1d74a914",
                campaign_id=campaign_id,
                note_id=note_id,
                title="Public",
                body="Public body",
                format="markdown",
                created_at=now,
                updated_at=now,
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(PublicSnippet).values(
                    id="5204e54e-c508-43ef-b4ce-613d5997bc9e",
                    campaign_id=campaign_id,
                    note_id=note_id,
                    title="Bad",
                    body="Bad body",
                    format="html",
                    created_at=now,
                    updated_at=now,
                )
            )


def test_entities_party_tracker_schema_and_party_display_mode(migrated_settings):
    engine = get_engine(migrated_settings)
    now = utc_now_z()
    campaign_id = "80dd2a4c-e2ac-47b6-a9e8-bf4939efb100"
    entity_id = "6ba1ca2d-70ff-421d-a31f-29eb71761d19"
    field_id = "9111f2a4-0f5f-42d8-a92f-f905652f6cc2"
    config_id = "1f393e76-6456-43e5-b1f9-7ccbe29b1176"

    with engine.begin() as connection:
        entities_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'entities'"
        ).scalar_one()
        fields_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'custom_field_definitions'"
        ).scalar_one()
        party_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'party_tracker_configs'"
        ).scalar_one()
        display_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'player_display_runtime'"
        ).scalar_one()
        assert "ck_entities_kind" in entities_sql
        assert "ck_custom_field_definitions_field_type" in fields_sql
        assert "ck_party_tracker_configs_layout" in party_sql
        assert "'party'" in display_sql

        connection.execute(
            insert(Campaign).values(
                id=campaign_id,
                name="Entity Campaign",
                description=None,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(Entity).values(
                id=entity_id,
                campaign_id=campaign_id,
                kind="pc",
                name="Aria",
                display_name="Aria",
                visibility="public_known",
                portrait_asset_id=None,
                tags_json="[]",
                notes="Private notes",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(CustomFieldDefinition).values(
                id=field_id,
                campaign_id=campaign_id,
                key="level",
                label="Level",
                field_type="number",
                applies_to_json='["pc"]',
                required=False,
                default_value_json=None,
                options_json="[]",
                public_by_default=True,
                sort_order=0,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(CustomFieldValue).values(
                id="8d1b7b64-3fe7-4f0f-92a2-217af3d89110",
                campaign_id=campaign_id,
                entity_id=entity_id,
                field_definition_id=field_id,
                value_json="5",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(PartyTrackerConfig).values(
                id=config_id,
                campaign_id=campaign_id,
                layout="standard",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(PartyTrackerMember).values(
                id="7183c19b-b186-4033-b613-25885df0b0cc",
                config_id=config_id,
                campaign_id=campaign_id,
                entity_id=entity_id,
                sort_order=0,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(PartyTrackerField).values(
                id="6f3858ec-a324-4d21-81e0-21eb8097e78c",
                config_id=config_id,
                campaign_id=campaign_id,
                field_definition_id=field_id,
                sort_order=0,
                public_visible=True,
                created_at=now,
                updated_at=now,
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(Entity).values(
                    id="f353ee76-0cc6-4c7b-9db9-97e72c602f70",
                    campaign_id=campaign_id,
                    kind="not_real",
                    name="Bad",
                    display_name=None,
                    visibility="private",
                    portrait_asset_id=None,
                    tags_json="[]",
                    notes="",
                    created_at=now,
                    updated_at=now,
                )
            )


def test_combat_tracker_schema_and_initiative_display_mode(migrated_settings):
    engine = get_engine(migrated_settings)
    with engine.begin() as connection:
        encounters_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'combat_encounters'"
        ).scalar_one()
        combatants_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'combatants'"
        ).scalar_one()
        display_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'player_display_runtime'"
        ).scalar_one()
        assert "ck_combat_encounters_status" in encounters_sql
        assert "ck_combatants_disposition" in combatants_sql
        assert "ck_combatants_hp_current" in combatants_sql
        assert "'initiative'" in display_sql


def test_scene_orchestration_schema_constraints_and_indexes(migrated_settings):
    engine = get_engine(migrated_settings)
    now = utc_now_z()
    campaign_id = "395ec140-59d1-4848-b13c-fbe7f33d05fb"
    scene_id = "8eab8ddb-4e29-466c-93a2-18efc11058e8"
    entity_id = "b6caad6b-5411-4628-bfe1-9d0df61a0f98"
    source_id = "6f4d46ff-101d-4f46-a26c-a9ce26462fdb"
    note_id = "0575dcc5-807e-40cd-8fd4-0bb76adfd920"
    snippet_id = "2efc6c4b-a67e-44fa-82e1-d5eb50bb3347"
    encounter_id = "45cc57a9-37cd-457c-9e79-f7d7180b9071"

    with engine.begin() as connection:
        context_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'scene_contexts'"
        ).scalar_one()
        entity_link_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'scene_entity_links'"
        ).scalar_one()
        snippet_link_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'scene_public_snippet_links'"
        ).scalar_one()
        assert "ck_scene_contexts_staged_display_mode" in context_sql
        assert "active_map" in context_sql
        assert "ck_scene_entity_links_role" in entity_link_sql
        assert "public_snippet_id" in snippet_link_sql
        assert connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'uq_scene_contexts_scene_id'"
        ).scalar_one()
        assert connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'uq_scene_entity_links_scene_entity'"
        ).scalar_one()
        assert connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'uq_scene_public_snippet_links_scene_snippet'"
        ).scalar_one()

        connection.execute(insert(Campaign).values(id=campaign_id, name="Scene Campaign", description=None, created_at=now, updated_at=now))
        connection.execute(
            insert(Scene).values(
                id=scene_id,
                campaign_id=campaign_id,
                session_id=None,
                title="Scene Context",
                summary=None,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(Entity).values(
                id=entity_id,
                campaign_id=campaign_id,
                kind="npc",
                name="Dockmaster",
                display_name=None,
                visibility="private",
                portrait_asset_id=None,
                tags_json="[]",
                notes="Private",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(NoteSource).values(
                id=source_id,
                campaign_id=campaign_id,
                kind="internal",
                name="Internal",
                readonly=False,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(Note).values(
                id=note_id,
                campaign_id=campaign_id,
                source_id=source_id,
                session_id=None,
                scene_id=scene_id,
                asset_id=None,
                title="Scene Note",
                private_body="Secret",
                tags_json="[]",
                source_label="Internal",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(PublicSnippet).values(
                id=snippet_id,
                campaign_id=campaign_id,
                note_id=note_id,
                title="Public",
                body="Safe",
                format="markdown",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(CombatEncounter).values(
                id=encounter_id,
                campaign_id=campaign_id,
                session_id=None,
                scene_id=scene_id,
                title="Encounter",
                status="active",
                round=1,
                active_combatant_id=None,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(SceneContext).values(
                id="23af7f21-9bed-4d57-8ae0-bfe04fc79c99",
                campaign_id=campaign_id,
                scene_id=scene_id,
                active_encounter_id=encounter_id,
                staged_display_mode="public_snippet",
                staged_public_snippet_id=snippet_id,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(SceneEntityLink).values(
                id="52643b75-6182-4f32-8c81-d663943a3435",
                campaign_id=campaign_id,
                scene_id=scene_id,
                entity_id=entity_id,
                role="featured",
                sort_order=0,
                notes="Focus",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(ScenePublicSnippetLink).values(
                id="05f8f73a-6cfd-43dd-9138-d1bd66b04922",
                campaign_id=campaign_id,
                scene_id=scene_id,
                public_snippet_id=snippet_id,
                sort_order=0,
                created_at=now,
                updated_at=now,
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(SceneContext).values(
                    id="98bfa4f8-945d-45db-8210-f574ff868ad9",
                    campaign_id=campaign_id,
                    scene_id=scene_id,
                    active_encounter_id=None,
                    staged_display_mode="none",
                    staged_public_snippet_id=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(SceneEntityLink).values(
                    id="e99181d2-369c-49ef-9646-e7465a720b93",
                    campaign_id=campaign_id,
                    scene_id=scene_id,
                    entity_id=entity_id,
                    role="supporting",
                    sort_order=1,
                    notes="Duplicate",
                    created_at=now,
                    updated_at=now,
                )
            )
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(SceneContext).values(
                    id="d51d6098-ea73-46a2-9cf3-390abedcf679",
                    campaign_id=campaign_id,
                    scene_id=scene_id,
                    active_encounter_id=None,
                    staged_display_mode="auto_reveal_everything",
                    staged_public_snippet_id=None,
                    created_at=now,
                    updated_at=now,
                )
            )


def test_seed_is_idempotent_and_uses_deterministic_campaign_id(migrated_settings):
    first = seed_demo_data(migrated_settings)
    second = seed_demo_data(migrated_settings)
    engine = get_engine(migrated_settings)
    with engine.connect() as connection:
        campaign_count = connection.execute(select(func.count()).select_from(Campaign)).scalar_one()
        runtime_count = connection.execute(select(func.count()).select_from(AppRuntime)).scalar_one()
        display_count = connection.execute(select(func.count()).select_from(PlayerDisplayRuntime)).scalar_one()
        widget_count = connection.execute(select(func.count()).select_from(WorkspaceWidget)).scalar_one()
        note_count = connection.execute(select(func.count()).select_from(Note)).scalar_one()
        snippet_count = connection.execute(select(func.count()).select_from(PublicSnippet)).scalar_one()
        entity_count = connection.execute(select(func.count()).select_from(Entity)).scalar_one()
        field_count = connection.execute(select(func.count()).select_from(CustomFieldDefinition)).scalar_one()
        value_count = connection.execute(select(func.count()).select_from(CustomFieldValue)).scalar_one()
        party_config_count = connection.execute(select(func.count()).select_from(PartyTrackerConfig)).scalar_one()
        party_member_count = connection.execute(select(func.count()).select_from(PartyTrackerMember)).scalar_one()
        party_field_count = connection.execute(select(func.count()).select_from(PartyTrackerField)).scalar_one()
        encounter_count = connection.execute(select(func.count()).select_from(CombatEncounter)).scalar_one()
        combatant_count = connection.execute(select(func.count()).select_from(Combatant)).scalar_one()
        scene_context_count = connection.execute(select(func.count()).select_from(SceneContext)).scalar_one()
        scene_entity_link_count = connection.execute(select(func.count()).select_from(SceneEntityLink)).scalar_one()
        scene_snippet_link_count = connection.execute(select(func.count()).select_from(ScenePublicSnippetLink)).scalar_one()
        campaign_id = connection.execute(select(Campaign.id)).scalar_one()
        display_mode = connection.execute(select(PlayerDisplayRuntime.mode)).scalar_one()
        seed_version = connection.execute(
            select(AppMeta.value).where(AppMeta.key == SEED_META_KEY)
        ).scalar_one()
    assert first.applied is True
    assert second.applied is False
    assert first.seed_version == DEMO_SEED_VERSION
    assert campaign_count == 1
    assert runtime_count == 1
    assert display_count == 1
    assert widget_count == len(DEFAULT_WORKSPACE_WIDGETS)
    assert note_count == 1
    assert snippet_count == 1
    assert entity_count == 2
    assert field_count == 4
    assert value_count == 7
    assert party_config_count == 1
    assert party_member_count == 2
    assert party_field_count == 3
    assert encounter_count == 1
    assert combatant_count == 3
    assert scene_context_count == 1
    assert scene_entity_link_count == 2
    assert scene_snippet_link_count == 1
    assert campaign_id == DEMO_CAMPAIGN_ID
    assert display_mode == "blackout"
    assert seed_version == DEMO_SEED_VERSION


def test_seed_upgrades_v1_marker_without_duplicate_demo_records(migrated_settings):
    seed_demo_data(migrated_settings)
    engine = get_engine(migrated_settings)
    with engine.begin() as connection:
        connection.execute(
            AppMeta.__table__.update()
            .where(AppMeta.key == SEED_META_KEY)
            .values(value="2026-04-27-v1", updated_at=utc_now_z())
        )

    result = seed_demo_data(migrated_settings)

    with engine.connect() as connection:
        campaign_count = connection.execute(select(func.count()).select_from(Campaign)).scalar_one()
        runtime_count = connection.execute(select(func.count()).select_from(AppRuntime)).scalar_one()
        display_count = connection.execute(select(func.count()).select_from(PlayerDisplayRuntime)).scalar_one()
        widget_count = connection.execute(select(func.count()).select_from(WorkspaceWidget)).scalar_one()
        note_count = connection.execute(select(func.count()).select_from(Note)).scalar_one()
        snippet_count = connection.execute(select(func.count()).select_from(PublicSnippet)).scalar_one()
        entity_count = connection.execute(select(func.count()).select_from(Entity)).scalar_one()
        field_count = connection.execute(select(func.count()).select_from(CustomFieldDefinition)).scalar_one()
        value_count = connection.execute(select(func.count()).select_from(CustomFieldValue)).scalar_one()
        party_config_count = connection.execute(select(func.count()).select_from(PartyTrackerConfig)).scalar_one()
        party_member_count = connection.execute(select(func.count()).select_from(PartyTrackerMember)).scalar_one()
        party_field_count = connection.execute(select(func.count()).select_from(PartyTrackerField)).scalar_one()
        encounter_count = connection.execute(select(func.count()).select_from(CombatEncounter)).scalar_one()
        combatant_count = connection.execute(select(func.count()).select_from(Combatant)).scalar_one()
        scene_context_count = connection.execute(select(func.count()).select_from(SceneContext)).scalar_one()
        scene_entity_link_count = connection.execute(select(func.count()).select_from(SceneEntityLink)).scalar_one()
        scene_snippet_link_count = connection.execute(select(func.count()).select_from(ScenePublicSnippetLink)).scalar_one()
        seed_version = connection.execute(
            select(AppMeta.value).where(AppMeta.key == SEED_META_KEY)
        ).scalar_one()
    assert result.applied is True
    assert campaign_count == 1
    assert runtime_count == 1
    assert display_count == 1
    assert widget_count == len(DEFAULT_WORKSPACE_WIDGETS)
    assert note_count == 1
    assert snippet_count == 1
    assert entity_count == 2
    assert field_count == 4
    assert value_count == 7
    assert party_config_count == 1
    assert party_member_count == 2
    assert party_field_count == 3
    assert encounter_count == 1
    assert combatant_count == 3
    assert scene_context_count == 1
    assert scene_entity_link_count == 2
    assert scene_snippet_link_count == 1
    assert seed_version == DEMO_SEED_VERSION


def test_seed_does_not_overwrite_non_empty_runtime(migrated_settings):
    engine = get_engine(migrated_settings)
    now = utc_now_z()
    alternate_campaign_id = "9a328a0e-a685-4a55-beb3-a23ce714f2e9"
    with engine.begin() as connection:
        connection.execute(
            insert(Campaign).values(
                id=alternate_campaign_id,
                name="User Campaign",
                description=None,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            insert(AppRuntime).values(
                id=RUNTIME_ID,
                active_campaign_id=alternate_campaign_id,
                active_session_id=None,
                active_scene_id=None,
                updated_at=now,
            )
        )
        connection.execute(
            insert(AppMeta).values(key=SEED_META_KEY, value="2026-04-27-v1", updated_at=now)
        )

    seed_demo_data(migrated_settings)

    with engine.connect() as connection:
        active_campaign_id = connection.execute(select(AppRuntime.active_campaign_id)).scalar_one()
        campaign_count = connection.execute(select(func.count()).select_from(Campaign)).scalar_one()
    assert active_campaign_id == alternate_campaign_id
    assert campaign_count == 2


def test_seed_does_not_overwrite_moved_workspace_widget(migrated_settings):
    seed_demo_data(migrated_settings)
    engine = get_engine(migrated_settings)
    first_widget = DEFAULT_WORKSPACE_WIDGETS[0]
    with engine.begin() as connection:
        connection.execute(
            WorkspaceWidget.__table__.update()
            .where(WorkspaceWidget.id == first_widget.id)
            .values(x=999, y=888, updated_at=utc_now_z())
        )
        connection.execute(
            AppMeta.__table__.update()
            .where(AppMeta.key == SEED_META_KEY)
            .values(value="2026-04-27-v2", updated_at=utc_now_z())
        )

    seed_demo_data(migrated_settings)

    with engine.connect() as connection:
        row = connection.execute(
            select(WorkspaceWidget.x, WorkspaceWidget.y).where(WorkspaceWidget.id == first_widget.id)
        ).one()
    assert row.x == 999
    assert row.y == 888


def test_seed_does_not_overwrite_demo_note_or_snippet(migrated_settings):
    seed_demo_data(migrated_settings)
    engine = get_engine(migrated_settings)
    with engine.begin() as connection:
        note_id = connection.execute(select(Note.id)).scalar_one()
        snippet_id = connection.execute(select(PublicSnippet.id)).scalar_one()
        connection.execute(
            Note.__table__.update()
            .where(Note.id == note_id)
            .values(private_body="User edited private body", updated_at=utc_now_z())
        )
        connection.execute(
            PublicSnippet.__table__.update()
            .where(PublicSnippet.id == snippet_id)
            .values(body="User edited public body", updated_at=utc_now_z())
        )
        connection.execute(
            AppMeta.__table__.update()
            .where(AppMeta.key == SEED_META_KEY)
            .values(value="2026-04-27-v8", updated_at=utc_now_z())
        )

    seed_demo_data(migrated_settings)

    with engine.connect() as connection:
        note_body = connection.execute(select(Note.private_body).where(Note.id == note_id)).scalar_one()
        snippet_body = connection.execute(select(PublicSnippet.body).where(PublicSnippet.id == snippet_id)).scalar_one()
    assert note_body == "User edited private body"
    assert snippet_body == "User edited public body"


def test_seed_does_not_overwrite_demo_entities_fields_or_party_config(migrated_settings):
    seed_demo_data(migrated_settings)
    engine = get_engine(migrated_settings)
    with engine.begin() as connection:
        entity_id = connection.execute(select(Entity.id).where(Entity.name == "Aria Vell")).scalar_one()
        field_id = connection.execute(select(CustomFieldDefinition.id).where(CustomFieldDefinition.key == "role")).scalar_one()
        config_id = connection.execute(select(PartyTrackerConfig.id)).scalar_one()
        connection.execute(
            Entity.__table__.update()
            .where(Entity.id == entity_id)
            .values(display_name="User Aria", notes="User edited entity note", updated_at=utc_now_z())
        )
        connection.execute(
            CustomFieldDefinition.__table__.update()
            .where(CustomFieldDefinition.id == field_id)
            .values(label="User Role", public_by_default=False, updated_at=utc_now_z())
        )
        connection.execute(
            PartyTrackerConfig.__table__.update()
            .where(PartyTrackerConfig.id == config_id)
            .values(layout="wide", updated_at=utc_now_z())
        )
        connection.execute(
            AppMeta.__table__.update()
            .where(AppMeta.key == SEED_META_KEY)
            .values(value="2026-04-27-v9", updated_at=utc_now_z())
        )

    seed_demo_data(migrated_settings)

    with engine.connect() as connection:
        entity_row = connection.execute(select(Entity.display_name, Entity.notes).where(Entity.id == entity_id)).one()
        field_row = connection.execute(
            select(CustomFieldDefinition.label, CustomFieldDefinition.public_by_default).where(CustomFieldDefinition.id == field_id)
        ).one()
        layout = connection.execute(select(PartyTrackerConfig.layout).where(PartyTrackerConfig.id == config_id)).scalar_one()
    assert entity_row.display_name == "User Aria"
    assert entity_row.notes == "User edited entity note"
    assert field_row.label == "User Role"
    assert field_row.public_by_default is False
    assert layout == "wide"


def test_seed_does_not_overwrite_demo_combat_state(migrated_settings):
    seed_demo_data(migrated_settings)
    engine = get_engine(migrated_settings)
    with engine.begin() as connection:
        encounter_id = connection.execute(select(CombatEncounter.id)).scalar_one()
        combatant_id = connection.execute(select(Combatant.id).where(Combatant.name == "Aria")).scalar_one()
        connection.execute(
            CombatEncounter.__table__.update()
            .where(CombatEncounter.id == encounter_id)
            .values(title="User Combat", round=4, updated_at=utc_now_z())
        )
        connection.execute(
            Combatant.__table__.update()
            .where(Combatant.id == combatant_id)
            .values(name="User Aria Combat", hp_current=3, updated_at=utc_now_z())
        )
        connection.execute(
            AppMeta.__table__.update()
            .where(AppMeta.key == SEED_META_KEY)
            .values(value="2026-04-27-v10", updated_at=utc_now_z())
        )

    seed_demo_data(migrated_settings)

    with engine.connect() as connection:
        encounter = connection.execute(select(CombatEncounter.title, CombatEncounter.round).where(CombatEncounter.id == encounter_id)).one()
        combatant = connection.execute(select(Combatant.name, Combatant.hp_current).where(Combatant.id == combatant_id)).one()
    assert encounter.title == "User Combat"
    assert encounter.round == 4
    assert combatant.name == "User Aria Combat"
    assert combatant.hp_current == 3


def test_seed_does_not_overwrite_demo_scene_context(migrated_settings):
    seed_demo_data(migrated_settings)
    engine = get_engine(migrated_settings)
    with engine.begin() as connection:
        context_id = connection.execute(select(SceneContext.id)).scalar_one()
        connection.execute(
            SceneContext.__table__.update()
            .where(SceneContext.id == context_id)
            .values(
                active_encounter_id=None,
                staged_display_mode="public_snippet",
                staged_public_snippet_id=None,
                updated_at=utc_now_z(),
            )
        )
        connection.execute(
            AppMeta.__table__.update()
            .where(AppMeta.key == SEED_META_KEY)
            .values(value="2026-04-27-v11", updated_at=utc_now_z())
        )

    seed_demo_data(migrated_settings)

    with engine.connect() as connection:
        row = connection.execute(
            select(
                SceneContext.active_encounter_id,
                SceneContext.staged_display_mode,
                SceneContext.staged_public_snippet_id,
            ).where(SceneContext.id == context_id)
        ).one()
    assert row.active_encounter_id is None
    assert row.staged_display_mode == "public_snippet"
    assert row.staged_public_snippet_id is None


def test_seed_does_not_overwrite_non_empty_player_display_runtime(migrated_settings):
    engine = get_engine(migrated_settings)
    now = utc_now_z()
    with engine.begin() as connection:
        connection.execute(
            insert(PlayerDisplayRuntime).values(
                id=PLAYER_DISPLAY_ID,
                mode="intermission",
                active_campaign_id=None,
                active_session_id=None,
                active_scene_id=None,
                title="User Intermission",
                subtitle="Keep this",
                payload_json="{}",
                revision=7,
                identify_revision=2,
                identify_until=None,
                updated_at=now,
            )
        )
        connection.execute(
            insert(AppMeta).values(key=SEED_META_KEY, value="2026-04-27-v3", updated_at=now)
        )

    seed_demo_data(migrated_settings)

    with engine.connect() as connection:
        row = connection.execute(
            select(
                PlayerDisplayRuntime.mode,
                PlayerDisplayRuntime.title,
                PlayerDisplayRuntime.revision,
                PlayerDisplayRuntime.identify_revision,
            )
        ).one()
    assert row.mode == "intermission"
    assert row.title == "User Intermission"
    assert row.revision == 7
    assert row.identify_revision == 2


def test_seed_rolls_back_when_marker_write_fails(migrated_settings, monkeypatch):
    from backend.app.db import seed

    def fail_marker(connection, now):  # noqa: ANN001
        raise RuntimeError("marker write failed")

    monkeypatch.setattr(seed, "_set_seed_marker", fail_marker)
    with pytest.raises(RuntimeError, match="marker write failed"):
        seed.seed_demo_data(migrated_settings)

    engine = get_engine(migrated_settings)
    with engine.connect() as connection:
        campaign_count = connection.execute(select(func.count()).select_from(Campaign)).scalar_one()
        runtime_count = connection.execute(select(func.count()).select_from(AppRuntime)).scalar_one()
        display_count = connection.execute(select(func.count()).select_from(PlayerDisplayRuntime)).scalar_one()
        widget_count = connection.execute(select(func.count()).select_from(WorkspaceWidget)).scalar_one()
        note_count = connection.execute(select(func.count()).select_from(Note)).scalar_one()
        snippet_count = connection.execute(select(func.count()).select_from(PublicSnippet)).scalar_one()
        entity_count = connection.execute(select(func.count()).select_from(Entity)).scalar_one()
        field_count = connection.execute(select(func.count()).select_from(CustomFieldDefinition)).scalar_one()
        value_count = connection.execute(select(func.count()).select_from(CustomFieldValue)).scalar_one()
        party_config_count = connection.execute(select(func.count()).select_from(PartyTrackerConfig)).scalar_one()
        party_member_count = connection.execute(select(func.count()).select_from(PartyTrackerMember)).scalar_one()
        party_field_count = connection.execute(select(func.count()).select_from(PartyTrackerField)).scalar_one()
        encounter_count = connection.execute(select(func.count()).select_from(CombatEncounter)).scalar_one()
        combatant_count = connection.execute(select(func.count()).select_from(Combatant)).scalar_one()
        scene_context_count = connection.execute(select(func.count()).select_from(SceneContext)).scalar_one()
        scene_entity_link_count = connection.execute(select(func.count()).select_from(SceneEntityLink)).scalar_one()
        scene_snippet_link_count = connection.execute(select(func.count()).select_from(ScenePublicSnippetLink)).scalar_one()
    assert campaign_count == 0
    assert runtime_count == 0
    assert display_count == 0
    assert widget_count == 0
    assert note_count == 0
    assert snippet_count == 0
    assert entity_count == 0
    assert field_count == 0
    assert value_count == 0
    assert party_config_count == 0
    assert party_member_count == 0
    assert party_field_count == 0
    assert encounter_count == 0
    assert combatant_count == 0
    assert scene_context_count == 0
    assert scene_entity_link_count == 0
    assert scene_snippet_link_count == 0
