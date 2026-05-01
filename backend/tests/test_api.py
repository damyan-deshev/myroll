from __future__ import annotations

import hashlib
import io
import json
import uuid

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from backend.app.db.engine import get_engine
from backend.app.db.models import (
    Asset,
    CampaignMap,
    CustomFieldDefinition,
    CustomFieldValue,
    Entity,
    Note,
    PartyTrackerConfig,
    PartyTrackerField,
    PartyTrackerMember,
    PlayerDisplayRuntime,
    PublicSnippet,
    SceneMap,
    SceneMapFogMask,
    SceneMapToken,
    WorkspaceWidget,
)
from backend.app.db.seed import DEMO_CAMPAIGN_ID, DEMO_SCENE_ID, DEMO_SEED_VERSION
from backend.app.factory import create_app
from backend.app.time import utc_now_z
from backend.app.workspace_defaults import DEFAULT_WORKSPACE_WIDGETS


def _client(settings) -> TestClient:  # noqa: ANN001
    return TestClient(create_app(settings), base_url="http://127.0.0.1:8000")


def _create_campaign(client: TestClient, name: str = "Night Roads") -> dict:
    response = client.post("/api/campaigns", json={"name": name, "description": "A test campaign"})
    assert response.status_code == 201
    return response.json()


def _create_session(client: TestClient, campaign_id: str, title: str = "Session Alpha") -> dict:
    response = client.post(f"/api/campaigns/{campaign_id}/sessions", json={"title": title})
    assert response.status_code == 201
    return response.json()


def _create_scene(
    client: TestClient,
    campaign_id: str,
    title: str = "Dockside Ambush",
    session_id: str | None = None,
) -> dict:
    payload = {"title": title, "summary": "A test scene"}
    if session_id is not None:
        payload["session_id"] = session_id
    response = client.post(f"/api/campaigns/{campaign_id}/scenes", json=payload)
    assert response.status_code == 201
    return response.json()


def _image_bytes(fmt: str = "PNG", size: tuple[int, int] = (64, 40)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(80, 130, 170)).save(buffer, format=fmt)
    return buffer.getvalue()


def _upload_image(
    client: TestClient,
    campaign_id: str,
    *,
    filename: str = "handout.png",
    content: bytes | None = None,
    content_type: str = "image/png",
    kind: str = "handout_image",
    visibility: str = "public_displayable",
    name: str = "Storm Gate",
) -> dict:
    response = client.post(
        f"/api/campaigns/{campaign_id}/assets/upload",
        data={
            "kind": kind,
            "visibility": visibility,
            "name": name,
            "tags": "clue, gate",
        },
        files={"file": (filename, content or _image_bytes(), content_type)},
    )
    assert response.status_code == 201
    return response.json()


def _create_map(client: TestClient, campaign_id: str, asset_id: str, name: str = "Ship Deck") -> dict:
    response = client.post(f"/api/campaigns/{campaign_id}/maps", json={"asset_id": asset_id, "name": name})
    assert response.status_code == 201
    return response.json()


def _assign_scene_map(
    client: TestClient,
    campaign_id: str,
    scene_id: str,
    map_id: str,
    *,
    is_active: bool = False,
) -> dict:
    response = client.post(
        f"/api/campaigns/{campaign_id}/scenes/{scene_id}/maps",
        json={"map_id": map_id, "is_active": is_active, "player_fit_mode": "fit", "player_grid_visible": True},
    )
    assert response.status_code == 201
    return response.json()


def test_health_reports_db_ok_and_z_timestamp(seeded_settings):
    response = _client(seeded_settings).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["schema_version"] == "20260427_0012"
    assert body["db_path"].endswith("myroll.test.sqlite3")
    assert not body["db_path"].startswith("/")
    assert body["time"].endswith("Z")


def test_local_request_boundary_rejects_bad_host_and_cross_site_unsafe_requests(seeded_settings):
    client = _client(seeded_settings)

    assert client.get("/health").status_code == 200

    bad_host = client.get("/health", headers={"host": "evil.test"})
    assert bad_host.status_code == 400

    cross_site = client.post(
        "/api/player-display/blackout",
        headers={"origin": "https://evil.test", "sec-fetch-site": "cross-site"},
    )
    assert cross_site.status_code == 403
    assert cross_site.json()["error"]["code"] == "cross_site_request_rejected"

    no_browser_headers = client.post("/api/player-display/blackout")
    assert no_browser_headers.status_code == 200

    vite_origin = client.post(
        "/api/player-display/blackout",
        headers={"origin": "http://127.0.0.1:5173", "sec-fetch-site": "same-site"},
    )
    assert vite_origin.status_code == 200


def test_meta_reports_seed_and_schema(seeded_settings):
    response = _client(seeded_settings).get("/api/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["app"] == "myroll"
    assert body["version"] == "dev"
    assert body["schema_version"] == "20260427_0012"
    assert body["seed_version"] == DEMO_SEED_VERSION
    assert body["db_path"].endswith("myroll.test.sqlite3")
    assert not body["db_path"].startswith("/")


def test_storage_status_reports_shortened_paths_and_artifacts(seeded_settings):
    client = _client(seeded_settings)
    backup = client.post("/api/storage/backup")
    assert backup.status_code == 200
    export = client.post("/api/storage/export")
    assert export.status_code == 200

    response = client.get("/api/storage/status")

    assert response.status_code == 200
    body = response.json()
    assert body["profile"] in {"dev", "demo"}
    assert body["db_path"].endswith("myroll.test.sqlite3")
    assert body["asset_dir"].endswith("assets")
    assert body["backup_dir"].endswith("backups")
    assert body["export_dir"].endswith("exports")
    assert not body["db_path"].startswith("/")
    assert body["db_size_bytes"] > 0
    assert body["latest_backup"]["archive_name"].endswith(".sqlite3")
    assert body["latest_backup"]["created_at"].endswith("Z")
    assert body["latest_export"]["archive_name"].endswith(".export.tar.gz")
    assert body["latest_export"]["download_url"].startswith("/api/storage/exports/")
    assert body["schema_version"] == "20260427_0012"
    assert body["seed_version"] == DEMO_SEED_VERSION
    assert body["private_demo_name_map_active"] is False


def test_storage_export_download_uses_safe_archive_names(seeded_settings):
    client = _client(seeded_settings)
    artifact = client.post("/api/storage/export").json()

    response = client.get(artifact["download_url"])
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/gzip")

    invalid = client.get("/api/storage/exports/../myroll.bad.export.tar.gz")
    assert invalid.status_code == 404


def test_campaigns_and_scenes_read_seeded_data(seeded_settings):
    client = _client(seeded_settings)
    campaigns = client.get("/api/campaigns")
    assert campaigns.status_code == 200
    assert len(campaigns.json()) == 1
    assert campaigns.json()[0]["id"] == DEMO_CAMPAIGN_ID
    assert campaigns.json()[0]["created_at"].endswith("Z")

    campaign = client.get(f"/api/campaigns/{DEMO_CAMPAIGN_ID}")
    assert campaign.status_code == 200
    assert campaign.json()["name"] == "Demo Campaign: Ship Ambush"

    scenes = client.get(f"/api/campaigns/{DEMO_CAMPAIGN_ID}/scenes")
    assert scenes.status_code == 200
    assert len(scenes.json()) == 1
    assert scenes.json()[0]["title"] == "Ship Ambush"
    assert scenes.json()[0]["created_at"].endswith("Z")


def test_create_campaign_session_and_scene_returns_created_resources(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "  Witchlight Gothic Trauma Edition  ")
    assert campaign["name"] == "Witchlight Gothic Trauma Edition"
    assert campaign["created_at"].endswith("Z")

    session = _create_session(client, campaign["id"], "  Opening Night  ")
    assert session["campaign_id"] == campaign["id"]
    assert session["title"] == "Opening Night"
    assert session["created_at"].endswith("Z")

    scene = _create_scene(client, campaign["id"], "  Lantern Bridge  ", session["id"])
    assert scene["campaign_id"] == campaign["id"]
    assert scene["session_id"] == session["id"]
    assert scene["title"] == "Lantern Bridge"
    assert scene["created_at"].endswith("Z")

    sessions = client.get(f"/api/campaigns/{campaign['id']}/sessions")
    assert sessions.status_code == 200
    assert sessions.json()[0]["id"] == session["id"]


def test_scene_creation_rejects_session_from_another_campaign(seeded_settings):
    client = _client(seeded_settings)
    campaign_a = _create_campaign(client, "Campaign A")
    campaign_b = _create_campaign(client, "Campaign B")
    session = _create_session(client, campaign_a["id"])

    response = client.post(
        f"/api/campaigns/{campaign_b['id']}/scenes",
        json={"title": "Wrong Home", "session_id": session["id"]},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "session_campaign_mismatch"


def test_runtime_activation_endpoints_return_current_runtime(seeded_settings):
    client = _client(seeded_settings)

    initial = client.get("/api/runtime")
    assert initial.status_code == 200
    assert initial.json()["active_campaign_id"] is None

    campaign = client.post(
        "/api/runtime/activate-campaign",
        json={"campaign_id": DEMO_CAMPAIGN_ID},
    )
    assert campaign.status_code == 200
    assert campaign.json()["active_campaign_id"] == DEMO_CAMPAIGN_ID
    assert campaign.json()["active_campaign_name"] == "Demo Campaign: Ship Ambush"
    assert campaign.json()["updated_at"].endswith("Z")

    scene = client.post("/api/runtime/activate-scene", json={"scene_id": DEMO_SCENE_ID})
    assert scene.status_code == 200
    assert scene.json()["active_campaign_id"] == DEMO_CAMPAIGN_ID
    assert scene.json()["active_scene_id"] == DEMO_SCENE_ID
    assert scene.json()["active_scene_title"] == "Ship Ambush"
    assert scene.json()["active_session_title"] == "Session 001: Cold Open"


def test_activate_session_preserves_scene_only_for_same_session(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client)
    session_a = _create_session(client, campaign["id"], "Session A")
    session_b = _create_session(client, campaign["id"], "Session B")
    scene = _create_scene(client, campaign["id"], "Scene A", session_a["id"])

    activated_scene = client.post("/api/runtime/activate-scene", json={"scene_id": scene["id"]})
    assert activated_scene.status_code == 200
    assert activated_scene.json()["active_scene_id"] == scene["id"]

    same_session = client.post("/api/runtime/activate-session", json={"session_id": session_a["id"]})
    assert same_session.status_code == 200
    assert same_session.json()["active_scene_id"] == scene["id"]

    other_session = client.post("/api/runtime/activate-session", json={"session_id": session_b["id"]})
    assert other_session.status_code == 200
    assert other_session.json()["active_session_id"] == session_b["id"]
    assert other_session.json()["active_scene_id"] is None


def test_invalid_activate_scene_does_not_partially_mutate_runtime(seeded_settings):
    client = _client(seeded_settings)
    before = client.post("/api/runtime/activate-campaign", json={"campaign_id": DEMO_CAMPAIGN_ID}).json()

    response = client.post("/api/runtime/activate-scene", json={"scene_id": str(uuid.uuid4())})
    after = client.get("/api/runtime").json()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "scene_not_found"
    assert after == before


def test_clear_runtime_nulls_ids_and_returns_runtime(seeded_settings):
    client = _client(seeded_settings)
    client.post("/api/runtime/activate-scene", json={"scene_id": DEMO_SCENE_ID})

    response = client.post("/api/runtime/clear")

    assert response.status_code == 200
    body = response.json()
    assert body["active_campaign_id"] is None
    assert body["active_session_id"] is None
    assert body["active_scene_id"] is None
    assert body["updated_at"].endswith("Z")


def test_player_display_default_state_and_blackout(seeded_settings):
    client = _client(seeded_settings)

    initial = client.get("/api/player-display")
    assert initial.status_code == 200
    body = initial.json()
    assert body["mode"] == "blackout"
    assert body["title"] is None
    assert body["payload"] == {}
    assert body["revision"] == 1
    assert body["identify_revision"] == 0
    assert body["updated_at"].endswith("Z")

    blackout = client.post("/api/player-display/blackout")
    assert blackout.status_code == 200
    assert blackout.json()["mode"] == "blackout"
    assert blackout.json()["title"] is None
    assert blackout.json()["revision"] == 2


def test_player_display_intermission_uses_runtime_context(seeded_settings):
    client = _client(seeded_settings)
    client.post("/api/runtime/activate-scene", json={"scene_id": DEMO_SCENE_ID})

    response = client.post("/api/player-display/intermission")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "intermission"
    assert body["title"] == "Intermission"
    assert body["subtitle"] == "Session 001: Cold Open"
    assert body["active_campaign_id"] == DEMO_CAMPAIGN_ID
    assert body["active_scene_id"] == DEMO_SCENE_ID
    assert body["revision"] == 2


def test_player_display_show_scene_title_uses_active_runtime_without_mutating_it(seeded_settings):
    client = _client(seeded_settings)
    before = client.post("/api/runtime/activate-scene", json={"scene_id": DEMO_SCENE_ID}).json()

    response = client.post("/api/player-display/show-scene-title")
    after = client.get("/api/runtime").json()

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "scene_title"
    assert body["title"] == "Ship Ambush"
    assert body["subtitle"] == "Session 001: Cold Open"
    assert body["active_scene_id"] == DEMO_SCENE_ID
    assert body["revision"] == 2
    assert after == before


def test_player_display_show_scene_title_explicit_scene_does_not_mutate_app_runtime(seeded_settings):
    client = _client(seeded_settings)
    campaign_a = _create_campaign(client, "Campaign A")
    campaign_b = _create_campaign(client, "Campaign B")
    session_a = _create_session(client, campaign_a["id"], "Session A")
    session_b = _create_session(client, campaign_b["id"], "Session B")
    scene_a = _create_scene(client, campaign_a["id"], "Scene A", session_a["id"])
    scene_b = _create_scene(client, campaign_b["id"], "Scene B", session_b["id"])
    before = client.post("/api/runtime/activate-scene", json={"scene_id": scene_a["id"]}).json()

    response = client.post("/api/player-display/show-scene-title", json={"scene_id": scene_b["id"]})
    after = client.get("/api/runtime").json()

    assert response.status_code == 200
    assert response.json()["title"] == "Scene B"
    assert response.json()["active_campaign_id"] == campaign_b["id"]
    assert after == before


def test_player_display_show_scene_title_errors_use_envelope(seeded_settings):
    client = _client(seeded_settings)

    missing_active = client.post("/api/player-display/show-scene-title")
    missing_scene = client.post("/api/player-display/show-scene-title", json={"scene_id": str(uuid.uuid4())})
    invalid_body = client.post("/api/player-display/show-scene-title", json={"scene_id": "not-a-uuid"})

    assert missing_active.status_code == 400
    assert missing_active.json()["error"]["code"] == "active_scene_required"
    assert missing_scene.status_code == 404
    assert missing_scene.json()["error"]["code"] == "scene_not_found"
    assert invalid_body.status_code == 422
    assert invalid_body.json()["error"]["code"] == "validation_error"


def test_player_display_identify_only_changes_identify_fields(seeded_settings):
    client = _client(seeded_settings)
    client.post("/api/runtime/activate-scene", json={"scene_id": DEMO_SCENE_ID})
    scene_title = client.post("/api/player-display/show-scene-title").json()

    identified = client.post("/api/player-display/identify")

    assert identified.status_code == 200
    body = identified.json()
    assert body["mode"] == "scene_title"
    assert body["title"] == scene_title["title"]
    assert body["subtitle"] == scene_title["subtitle"]
    assert body["revision"] == scene_title["revision"]
    assert body["identify_revision"] == scene_title["identify_revision"] + 1
    assert body["identify_until"].endswith("Z")
    assert body["updated_at"].endswith("Z")


def test_asset_upload_derives_metadata_from_validated_image(seeded_settings):
    client = _client(seeded_settings)
    asset = _upload_image(
        client,
        DEMO_CAMPAIGN_ID,
        filename="murder.exe",
        content=_image_bytes("PNG", (64, 40)),
        content_type="application/x-msdownload",
    )

    assert asset["mime_type"] == "image/png"
    assert asset["width"] == 64
    assert asset["height"] == 40
    assert asset["original_filename"] == "murder.exe"
    assert asset["visibility"] == "public_displayable"
    assert asset["tags"] == ["clue", "gate"]
    assert not asset["relative_path"].startswith("/")
    assert (seeded_settings.asset_dir / asset["relative_path"]).exists()
    assert asset["created_at"].endswith("Z")

    listed = client.get(f"/api/campaigns/{DEMO_CAMPAIGN_ID}/assets")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == asset["id"]

    webp = _upload_image(
        client,
        DEMO_CAMPAIGN_ID,
        filename="display.webp",
        content=_image_bytes("WEBP", (18, 12)),
        content_type="image/webp",
        name="WebP Display",
    )
    assert webp["mime_type"] == "image/webp"
    assert webp["width"] == 18


def test_asset_upload_duplicate_uses_content_addressed_blob(seeded_settings):
    client = _client(seeded_settings)
    content = _image_bytes("PNG", (19, 23))

    first = _upload_image(client, DEMO_CAMPAIGN_ID, filename="first.png", content=content, name="First")
    second = _upload_image(client, DEMO_CAMPAIGN_ID, filename="second.png", content=content, name="Second")

    assert first["checksum"] == second["checksum"]
    assert first["relative_path"] == second["relative_path"]
    assert second["original_filename"] == "second.png"
    assert (seeded_settings.asset_dir / second["relative_path"]).read_bytes() == content


def test_asset_upload_rejects_symlink_shard_directory(seeded_settings, tmp_path):
    client = _client(seeded_settings)
    content = b""
    shard = seeded_settings.asset_dir / "missing"
    for width in range(21, 40):
        candidate = _image_bytes("PNG", (width, 17))
        checksum = hashlib.sha256(candidate).hexdigest()
        candidate_shard = seeded_settings.asset_dir / checksum[:2]
        if not candidate_shard.exists():
            content = candidate
            shard = candidate_shard
            break
    assert content

    escape_dir = tmp_path / "escape"
    escape_dir.mkdir()
    shard.symlink_to(escape_dir, target_is_directory=True)

    response = client.post(
        f"/api/campaigns/{DEMO_CAMPAIGN_ID}/assets/upload",
        data={"kind": "handout_image", "visibility": "private"},
        files={"file": ("portrait.png", content, "image/png")},
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "asset_directory_invalid"
    assert not any(escape_dir.iterdir())


def test_asset_import_path_endpoint_is_not_public(seeded_settings, tmp_path):
    source = tmp_path / "source.jpeg"
    source.write_bytes(_image_bytes("JPEG", (32, 24)))
    client = _client(seeded_settings)

    response = client.post(
        f"/api/campaigns/{DEMO_CAMPAIGN_ID}/assets/import-path",
        json={
            "source_path": str(source),
            "kind": "scene_image",
            "visibility": "private",
            "name": "Copied Scene",
            "tags": ["scene", "copy"],
        },
    )

    assert response.status_code == 404


def test_asset_import_rejects_unsupported_large_and_decompression_bomb_inputs(seeded_settings, monkeypatch):
    client = _client(seeded_settings)

    unsupported = client.post(
        f"/api/campaigns/{DEMO_CAMPAIGN_ID}/assets/upload",
        data={"kind": "handout_image", "visibility": "public_displayable"},
        files={"file": ("note.txt", b"not an image", "image/png")},
    )
    assert unsupported.status_code == 400
    assert unsupported.json()["error"]["code"] == "invalid_image"

    too_large = client.post(
        f"/api/campaigns/{DEMO_CAMPAIGN_ID}/assets/upload",
        data={"kind": "handout_image", "visibility": "public_displayable"},
        files={"file": ("large.png", b"x" * (25 * 1024 * 1024 + 1), "image/png")},
    )
    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "asset_too_large"

    from backend.app import asset_store

    monkeypatch.setattr(asset_store, "MAX_IMAGE_PIXELS", 100)
    monkeypatch.setattr(asset_store.Image, "MAX_IMAGE_PIXELS", 100)
    too_many_pixels = client.post(
        f"/api/campaigns/{DEMO_CAMPAIGN_ID}/assets/upload",
        data={"kind": "handout_image", "visibility": "public_displayable"},
        files={"file": ("bomb.png", _image_bytes("PNG", (11, 10)), "image/png")},
    )
    assert too_many_pixels.status_code == 413
    assert too_many_pixels.json()["error"]["code"] == "image_too_large"


def test_duplicate_asset_imports_create_distinct_rows_with_shared_blob(seeded_settings):
    client = _client(seeded_settings)
    content = _image_bytes("PNG", (20, 20))

    first = _upload_image(client, DEMO_CAMPAIGN_ID, content=content, name="First")
    second = _upload_image(client, DEMO_CAMPAIGN_ID, content=content, name="Second")

    assert first["id"] != second["id"]
    assert first["checksum"] == second["checksum"]
    assert first["relative_path"] == second["relative_path"]


def test_show_image_updates_public_display_without_mutating_app_runtime(seeded_settings):
    client = _client(seeded_settings)
    before = client.post("/api/runtime/activate-scene", json={"scene_id": DEMO_SCENE_ID}).json()
    asset = _upload_image(client, DEMO_CAMPAIGN_ID)

    response = client.post(
        "/api/player-display/show-image",
        json={"asset_id": asset["id"], "caption": "Visible clue", "fit_mode": "fill"},
    )
    after = client.get("/api/runtime").json()

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "image"
    assert body["title"] == asset["name"]
    assert body["payload"]["type"] == "image"
    assert body["payload"]["asset_id"] == asset["id"]
    assert body["payload"]["asset_url"] == f"/api/player-display/assets/{asset['id']}/blob"
    assert body["payload"]["mime_type"] == "image/png"
    assert body["payload"]["caption"] == "Visible clue"
    assert body["payload"]["fit_mode"] == "fill"
    assert body["revision"] == 2
    assert after == before

    blob = client.get(f"/api/player-display/assets/{asset['id']}/blob")
    assert blob.status_code == 200
    assert blob.headers["content-type"].startswith("image/png")
    assert blob.content == (seeded_settings.asset_dir / asset["relative_path"]).read_bytes()


def test_private_and_inactive_assets_are_not_publicly_served(seeded_settings):
    client = _client(seeded_settings)
    private_asset = _upload_image(client, DEMO_CAMPAIGN_ID, visibility="private", name="Private")
    public_asset = _upload_image(client, DEMO_CAMPAIGN_ID, visibility="public_displayable", name="Public")
    inactive_asset = _upload_image(client, DEMO_CAMPAIGN_ID, visibility="public_displayable", name="Inactive")

    show_private = client.post("/api/player-display/show-image", json={"asset_id": private_asset["id"]})
    assert show_private.status_code == 400
    assert show_private.json()["error"]["code"] == "asset_not_public_displayable"

    client.post("/api/player-display/show-image", json={"asset_id": public_asset["id"]})
    inactive_blob = client.get(f"/api/player-display/assets/{inactive_asset['id']}/blob")
    assert inactive_blob.status_code == 404
    assert inactive_blob.json()["error"]["code"] == "player_display_asset_not_active"


def test_public_blob_endpoint_rejects_missing_blob_and_path_escape(seeded_settings):
    client = _client(seeded_settings)
    asset = _upload_image(client, DEMO_CAMPAIGN_ID)
    client.post("/api/player-display/show-image", json={"asset_id": asset["id"]})
    (seeded_settings.asset_dir / asset["relative_path"]).unlink()

    missing = client.get(f"/api/player-display/assets/{asset['id']}/blob")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "asset_blob_not_found"

    engine = get_engine(seeded_settings)
    now = utc_now_z()
    escape_asset_id = str(uuid.uuid4())
    with engine.begin() as connection:
        connection.execute(
            insert(Asset).values(
                id=escape_asset_id,
                campaign_id=DEMO_CAMPAIGN_ID,
                kind="handout_image",
                visibility="public_displayable",
                name="Escape",
                mime_type="image/png",
                byte_size=10,
                checksum="abc",
                relative_path="../escape.png",
                original_filename="escape.png",
                width=10,
                height=10,
                duration_ms=None,
                tags_json="[]",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            PlayerDisplayRuntime.__table__.update().values(
                mode="image",
                payload_json=json.dumps({"type": "image", "asset_id": escape_asset_id}),
                revision=99,
                updated_at=now,
            )
        )

    escaped = client.get(f"/api/player-display/assets/{escape_asset_id}/blob")
    assert escaped.status_code == 500
    assert escaped.json()["error"]["code"] == "asset_path_invalid"
    assert str(seeded_settings.asset_dir) not in escaped.text


def test_map_creation_requires_map_image_asset_and_campaign_match(seeded_settings):
    client = _client(seeded_settings)
    campaign_a = _create_campaign(client, "Map Campaign A")
    campaign_b = _create_campaign(client, "Map Campaign B")
    handout = _upload_image(client, campaign_a["id"], kind="handout_image", name="Handout")
    map_asset = _upload_image(client, campaign_a["id"], kind="map_image", name="Harbor Map")

    wrong_kind = client.post(f"/api/campaigns/{campaign_a['id']}/maps", json={"asset_id": handout["id"]})
    cross_campaign = client.post(f"/api/campaigns/{campaign_b['id']}/maps", json={"asset_id": map_asset["id"]})
    created = client.post(f"/api/campaigns/{campaign_a['id']}/maps", json={"asset_id": map_asset["id"]})

    assert wrong_kind.status_code == 400
    assert wrong_kind.json()["error"]["code"] == "asset_not_map_image"
    assert cross_campaign.status_code == 400
    assert cross_campaign.json()["error"]["code"] == "asset_campaign_mismatch"
    assert created.status_code == 201
    body = created.json()
    assert body["asset_id"] == map_asset["id"]
    assert body["asset_url"] == f"/api/assets/{map_asset['id']}/blob"
    assert body["width"] == map_asset["width"]
    assert body["height"] == map_asset["height"]
    assert body["grid_color"] == "#FFFFFF"
    assert body["created_at"].endswith("Z")


def test_scene_map_assignment_validates_campaign_and_active_invariant(seeded_settings):
    client = _client(seeded_settings)
    campaign_a = _create_campaign(client, "Scene Map A")
    campaign_b = _create_campaign(client, "Scene Map B")
    scene_a = _create_scene(client, campaign_a["id"], "Scene A")
    scene_b = _create_scene(client, campaign_b["id"], "Scene B")
    asset_a = _upload_image(client, campaign_a["id"], kind="map_image", name="Map A")
    asset_b = _upload_image(client, campaign_b["id"], kind="map_image", name="Map B")
    map_a = _create_map(client, campaign_a["id"], asset_a["id"], "Map A")
    map_b = _create_map(client, campaign_b["id"], asset_b["id"], "Map B")

    wrong_scene = client.post(
        f"/api/campaigns/{campaign_a['id']}/scenes/{scene_b['id']}/maps",
        json={"map_id": map_a["id"]},
    )
    wrong_map = client.post(
        f"/api/campaigns/{campaign_a['id']}/scenes/{scene_a['id']}/maps",
        json={"map_id": map_b["id"]},
    )

    assert wrong_scene.status_code == 400
    assert wrong_scene.json()["error"]["code"] == "scene_campaign_mismatch"
    assert wrong_map.status_code == 400
    assert wrong_map.json()["error"]["code"] == "map_campaign_mismatch"

    scene_map_a = _assign_scene_map(client, campaign_a["id"], scene_a["id"], map_a["id"], is_active=True)
    second_asset = _upload_image(client, campaign_a["id"], kind="map_image", name="Map A2")
    second_map = _create_map(client, campaign_a["id"], second_asset["id"], "Map A2")
    scene_map_b = _assign_scene_map(client, campaign_a["id"], scene_a["id"], second_map["id"], is_active=True)
    listed = client.get(f"/api/campaigns/{campaign_a['id']}/scenes/{scene_a['id']}/maps").json()

    assert scene_map_a["is_active"] is True
    assert scene_map_b["is_active"] is True
    assert [item["id"] for item in listed if item["is_active"]] == [scene_map_b["id"]]
    assert any(item["id"] == scene_map_a["id"] and item["is_active"] is False for item in listed)


def test_scene_map_activation_switches_active_map_transactionally(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Activation Campaign")
    scene = _create_scene(client, campaign["id"], "Activation Scene")
    asset_a = _upload_image(client, campaign["id"], kind="map_image", name="Activation A")
    asset_b = _upload_image(client, campaign["id"], kind="map_image", name="Activation B")
    map_a = _create_map(client, campaign["id"], asset_a["id"], "Activation A")
    map_b = _create_map(client, campaign["id"], asset_b["id"], "Activation B")
    scene_map_a = _assign_scene_map(client, campaign["id"], scene["id"], map_a["id"])
    scene_map_b = _assign_scene_map(client, campaign["id"], scene["id"], map_b["id"])

    activate_a = client.post(f"/api/scene-maps/{scene_map_a['id']}/activate")
    activate_b = client.post(f"/api/scene-maps/{scene_map_b['id']}/activate")
    listed = client.get(f"/api/campaigns/{campaign['id']}/scenes/{scene['id']}/maps").json()

    assert activate_a.status_code == 200
    assert activate_a.json()["is_active"] is True
    assert activate_b.status_code == 200
    assert activate_b.json()["is_active"] is True
    assert [item["id"] for item in listed if item["is_active"]] == [scene_map_b["id"]]


def test_patch_map_grid_validates_and_normalizes_settings(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Grid Campaign")
    asset = _upload_image(client, campaign["id"], kind="map_image", name="Grid Map")
    campaign_map = _create_map(client, campaign["id"], asset["id"], "Grid Map")

    response = client.patch(
        f"/api/maps/{campaign_map['id']}/grid",
        json={
            "grid_enabled": True,
            "grid_size_px": 40,
            "grid_offset_x": -3.5,
            "grid_offset_y": 9.25,
            "grid_color": "#abc",
            "grid_opacity": 0.5,
        },
    )
    bad_color = client.patch(f"/api/maps/{campaign_map['id']}/grid", json={"grid_color": "url(javascript:bad)"})
    bad_size = client.patch(f"/api/maps/{campaign_map['id']}/grid", json={"grid_size_px": 3})
    bad_offset = client.patch(f"/api/maps/{campaign_map['id']}/grid", json={"grid_offset_x": "NaN"})

    assert response.status_code == 200
    body = response.json()
    assert body["grid_enabled"] is True
    assert body["grid_color"] == "#AABBCC"
    assert body["grid_offset_x"] == -3.5
    assert body["grid_opacity"] == 0.5
    assert bad_color.status_code == 400
    assert bad_color.json()["error"]["code"] == "invalid_grid_color"
    assert bad_size.status_code == 422
    assert bad_size.json()["error"]["code"] == "validation_error"
    assert bad_offset.status_code == 400
    assert bad_offset.json()["error"]["code"] == "invalid_grid_offset"


def test_show_map_empty_body_uses_active_runtime_scene_and_active_scene_map(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Public Map Campaign")
    scene = _create_scene(client, campaign["id"], "Public Map Scene")
    asset = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Public Map")
    campaign_map = _create_map(client, campaign["id"], asset["id"], "Public Map")
    client.patch(
        f"/api/maps/{campaign_map['id']}/grid",
        json={"grid_enabled": True, "grid_size_px": 32, "grid_color": "#123456", "grid_opacity": 0.4},
    )
    scene_map = _assign_scene_map(client, campaign["id"], scene["id"], campaign_map["id"], is_active=True)
    before_runtime = client.post("/api/runtime/activate-scene", json={"scene_id": scene["id"]}).json()

    response = client.post("/api/player-display/show-map")
    after_runtime = client.get("/api/runtime").json()

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "map"
    assert body["title"] == "Public Map"
    assert body["active_scene_id"] == scene["id"]
    assert body["payload"]["type"] == "map"
    assert body["payload"]["scene_map_id"] == scene_map["id"]
    assert body["payload"]["map_id"] == campaign_map["id"]
    assert body["payload"]["asset_id"] == asset["id"]
    assert body["payload"]["asset_url"] == f"/api/player-display/assets/{asset['id']}/blob"
    assert body["payload"]["grid"]["visible"] is True
    assert body["payload"]["grid"]["size_px"] == 32
    assert body["payload"]["grid"]["color"] == "#123456"
    assert "relative_path" not in json.dumps(body["payload"])
    assert response.json()["updated_at"].endswith("Z")
    assert after_runtime == before_runtime

    blob = client.get(f"/api/player-display/assets/{asset['id']}/blob")
    assert blob.status_code == 200
    assert blob.headers["content-type"].startswith("image/png")


def test_show_map_explicit_scene_map_does_not_mutate_runtime_or_active_scene_map(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Explicit Map Campaign")
    scene_a = _create_scene(client, campaign["id"], "Active Runtime Scene")
    scene_b = _create_scene(client, campaign["id"], "Presented Scene")
    asset_a = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Runtime Map")
    asset_b = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Presented Map")
    map_a = _create_map(client, campaign["id"], asset_a["id"], "Runtime Map")
    map_b = _create_map(client, campaign["id"], asset_b["id"], "Presented Map")
    active_scene_map = _assign_scene_map(client, campaign["id"], scene_a["id"], map_a["id"], is_active=True)
    explicit_scene_map = _assign_scene_map(client, campaign["id"], scene_b["id"], map_b["id"], is_active=False)
    before_runtime = client.post("/api/runtime/activate-scene", json={"scene_id": scene_a["id"]}).json()

    response = client.post("/api/player-display/show-map", json={"scene_map_id": explicit_scene_map["id"]})
    after_runtime = client.get("/api/runtime").json()
    listed_scene_b = client.get(f"/api/campaigns/{campaign['id']}/scenes/{scene_b['id']}/maps").json()
    listed_scene_a = client.get(f"/api/campaigns/{campaign['id']}/scenes/{scene_a['id']}/maps").json()

    assert response.status_code == 200
    assert response.json()["payload"]["scene_map_id"] == explicit_scene_map["id"]
    assert response.json()["active_scene_id"] == scene_b["id"]
    assert after_runtime == before_runtime
    assert all(item["is_active"] is False for item in listed_scene_b)
    assert [item["id"] for item in listed_scene_a if item["is_active"]] == [active_scene_map["id"]]


def test_show_map_rejects_missing_active_scene_map_private_asset_and_missing_blob(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Map Error Campaign")
    scene = _create_scene(client, campaign["id"], "Map Error Scene")
    client.post("/api/runtime/activate-scene", json={"scene_id": scene["id"]})

    missing_active_map = client.post("/api/player-display/show-map")
    assert missing_active_map.status_code == 400
    assert missing_active_map.json()["error"]["code"] == "active_scene_map_required"

    private_asset = _upload_image(client, campaign["id"], kind="map_image", visibility="private", name="Private Map")
    private_map = _create_map(client, campaign["id"], private_asset["id"], "Private Map")
    private_scene_map = _assign_scene_map(client, campaign["id"], scene["id"], private_map["id"], is_active=True)
    private_response = client.post("/api/player-display/show-map", json={"scene_map_id": private_scene_map["id"]})
    assert private_response.status_code == 400
    assert private_response.json()["error"]["code"] == "asset_not_public_displayable"

    public_asset = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Missing Blob Map")
    public_map = _create_map(client, campaign["id"], public_asset["id"], "Missing Blob Map")
    public_scene_map = _assign_scene_map(client, campaign["id"], scene["id"], public_map["id"], is_active=True)
    (seeded_settings.asset_dir / public_asset["relative_path"]).unlink()
    missing_blob = client.post("/api/player-display/show-map", json={"scene_map_id": public_scene_map["id"]})
    invalid_scene_map = client.post("/api/player-display/show-map", json={"scene_map_id": str(uuid.uuid4())})

    assert missing_blob.status_code == 404
    assert missing_blob.json()["error"]["code"] == "asset_blob_not_found"
    assert invalid_scene_map.status_code == 404
    assert invalid_scene_map.json()["error"]["code"] == "scene_map_not_found"


def test_public_blob_endpoint_serves_only_active_map_asset(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Blob Map Campaign")
    scene = _create_scene(client, campaign["id"], "Blob Map Scene")
    active_asset = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Active Map")
    inactive_asset = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Inactive Map")
    active_map = _create_map(client, campaign["id"], active_asset["id"], "Active Map")
    inactive_map = _create_map(client, campaign["id"], inactive_asset["id"], "Inactive Map")
    active_scene_map = _assign_scene_map(client, campaign["id"], scene["id"], active_map["id"], is_active=True)
    _assign_scene_map(client, campaign["id"], scene["id"], inactive_map["id"], is_active=False)

    shown = client.post("/api/player-display/show-map", json={"scene_map_id": active_scene_map["id"]})
    active_blob = client.get(f"/api/player-display/assets/{active_asset['id']}/blob")
    inactive_blob = client.get(f"/api/player-display/assets/{inactive_asset['id']}/blob")

    assert shown.status_code == 200
    assert active_blob.status_code == 200
    assert active_blob.content == (seeded_settings.asset_dir / active_asset["relative_path"]).read_bytes()
    assert inactive_blob.status_code == 404
    assert inactive_blob.json()["error"]["code"] == "player_display_asset_not_active"


def test_entities_fields_party_projection_and_public_sanitizer(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Party Campaign")
    portrait = _upload_image(client, campaign["id"], kind="npc_portrait", visibility="public_displayable", name="Party Portrait")
    private_portrait = _upload_image(client, campaign["id"], kind="npc_portrait", visibility="private", name="Private Portrait")

    public_pc = client.post(
        f"/api/campaigns/{campaign['id']}/entities",
        json={
            "kind": "pc",
            "name": "Aria Vell",
            "display_name": "Aria",
            "visibility": "public_known",
            "portrait_asset_id": portrait["id"],
            "tags": ["secret-tag"],
            "notes": "PRIVATE PARTY NOTE",
        },
    )
    private_pc = client.post(
        f"/api/campaigns/{campaign['id']}/entities",
        json={"kind": "pc", "name": "Hidden PC", "visibility": "private", "portrait_asset_id": private_portrait["id"]},
    )
    npc = client.post(f"/api/campaigns/{campaign['id']}/entities", json={"kind": "npc", "name": "Not A PC"})
    level = client.post(
        f"/api/campaigns/{campaign['id']}/custom-fields",
        json={"key": "level", "label": "Level", "field_type": "number", "applies_to": ["pc"], "public_by_default": True},
    )
    hp = client.post(
        f"/api/campaigns/{campaign['id']}/custom-fields",
        json={"key": "hp", "label": "HP", "field_type": "resource", "applies_to": ["pc"], "public_by_default": True},
    )
    secret = client.post(
        f"/api/campaigns/{campaign['id']}/custom-fields",
        json={"key": "secret", "label": "Secret", "field_type": "long_text", "applies_to": ["pc"], "public_by_default": False},
    )
    values = client.patch(
        f"/api/entities/{public_pc.json()['id']}/field-values",
        json={"values": {"level": 5, "hp": {"current": 22, "max": 31}, "secret": "PRIVATE FIELD"}},
    )

    bad_roster = client.patch(
        f"/api/campaigns/{campaign['id']}/party-tracker",
        json={"member_ids": [npc.json()["id"]]},
    )
    party = client.patch(
        f"/api/campaigns/{campaign['id']}/party-tracker",
        json={
            "layout": "standard",
            "member_ids": [public_pc.json()["id"], private_pc.json()["id"]],
            "fields": [
                {"field_definition_id": level.json()["id"], "public_visible": True},
                {"field_definition_id": hp.json()["id"], "public_visible": True},
                {"field_definition_id": secret.json()["id"], "public_visible": False},
            ],
        },
    )
    shown = client.post("/api/player-display/show-party", json={"campaign_id": campaign["id"]})
    display = shown.json()
    public_blob = client.get(f"/api/player-display/assets/{portrait['id']}/blob")
    private_blob = client.get(f"/api/player-display/assets/{private_portrait['id']}/blob")

    assert public_pc.status_code == 201
    assert private_pc.status_code == 201
    assert npc.status_code == 201
    assert level.status_code == 201
    assert hp.status_code == 201
    assert secret.status_code == 201
    assert values.status_code == 200
    assert bad_roster.status_code == 400
    assert bad_roster.json()["error"]["code"] == "party_member_must_be_pc"
    assert party.status_code == 200
    assert [member["entity_id"] for member in party.json()["members"]] == [public_pc.json()["id"], private_pc.json()["id"]]
    assert shown.status_code == 200
    assert display["mode"] == "party"
    assert display["payload"]["type"] == "party"
    assert len(display["payload"]["cards"]) == 1
    card = display["payload"]["cards"][0]
    assert card["display_name"] == "Aria"
    assert card["portrait_url"] == f"/api/player-display/assets/{portrait['id']}/blob"
    assert {field["key"] for field in card["fields"]} == {"level", "hp"}
    serialized = json.dumps(display)
    assert "PRIVATE PARTY NOTE" not in serialized
    assert "secret-tag" not in serialized
    assert "PRIVATE FIELD" not in serialized
    assert "Hidden PC" not in serialized
    assert public_blob.status_code == 200
    assert private_blob.status_code == 404


def test_combat_tracker_public_initiative_projection_is_sanitized(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Combat Campaign")
    session = _create_session(client, campaign["id"], "Combat Session")
    scene = _create_scene(client, campaign["id"], "Combat Scene", session["id"])
    public_portrait = _upload_image(client, campaign["id"], kind="npc_portrait", visibility="public_displayable", name="Aria Portrait")
    private_portrait = _upload_image(client, campaign["id"], kind="npc_portrait", visibility="private", name="Secret Portrait")
    public_pc = client.post(
        f"/api/campaigns/{campaign['id']}/entities",
        json={
            "kind": "pc",
            "name": "Aria Vell",
            "display_name": "Aria",
            "visibility": "public_known",
            "portrait_asset_id": public_portrait["id"],
            "tags": ["private-tag"],
            "notes": "PRIVATE ENTITY NOTE",
        },
    ).json()
    private_portrait_pc = client.post(
        f"/api/campaigns/{campaign['id']}/entities",
        json={"kind": "pc", "name": "Private Portrait PC", "visibility": "public_known", "portrait_asset_id": private_portrait["id"]},
    ).json()
    encounter = client.post(
        f"/api/campaigns/{campaign['id']}/combat-encounters",
        json={"title": "Deck Fight", "session_id": session["id"], "scene_id": scene["id"]},
    )
    visible_pc = client.post(
        f"/api/combat-encounters/{encounter.json()['id']}/combatants",
        json={
            "entity_id": public_pc["id"],
            "initiative": 18,
            "armor_class": 15,
            "hp_current": 22,
            "hp_max": 31,
            "conditions": [{"label": "SECRET CONDITION"}],
            "public_status": ["Blessed"],
            "notes": "PRIVATE COMBAT NOTE",
        },
    )
    hidden_public_entity = client.post(
        f"/api/combat-encounters/{encounter.json()['id']}/combatants",
        json={"entity_id": public_pc["id"], "name": "Hidden Ally", "public_visible": False, "initiative": 12},
    )
    private_portrait_visible = client.post(
        f"/api/combat-encounters/{encounter.json()['id']}/combatants",
        json={"entity_id": private_portrait_pc["id"], "name": "No Portrait", "public_visible": True, "initiative": 10},
    )
    invalid_status = client.post(
        f"/api/combat-encounters/{encounter.json()['id']}/combatants",
        json={"name": "Bad Status", "public_status": [{"label": "ok", "secret": "bad"}]},
    )
    client.patch(f"/api/entities/{public_pc['id']}", json={"visibility": "private"})
    shown = client.post("/api/player-display/show-initiative", json={"encounter_id": encounter.json()["id"]})
    display = shown.json()
    public_blob = client.get(f"/api/player-display/assets/{public_portrait['id']}/blob")
    private_blob = client.get(f"/api/player-display/assets/{private_portrait['id']}/blob")

    assert encounter.status_code == 201
    assert visible_pc.status_code == 201
    assert visible_pc.json()["combatants"][0]["public_visible"] is True
    assert hidden_public_entity.status_code == 201
    assert private_portrait_visible.status_code == 201
    assert invalid_status.status_code == 400
    assert invalid_status.json()["error"]["code"] == "invalid_public_status"
    assert shown.status_code == 200
    assert display["mode"] == "initiative"
    assert display["payload"]["type"] == "initiative"
    names = [combatant["name"] for combatant in display["payload"]["combatants"]]
    assert names == ["Aria", "No Portrait"]
    first = display["payload"]["combatants"][0]
    assert first["portrait_url"] == f"/api/player-display/assets/{public_portrait['id']}/blob"
    assert first["public_status"] == ["Blessed"]
    assert display["payload"]["combatants"][1]["portrait_url"] is None
    serialized = json.dumps(display)
    assert "Hidden Ally" not in serialized
    assert "PRIVATE COMBAT NOTE" not in serialized
    assert "SECRET CONDITION" not in serialized
    assert "PRIVATE ENTITY NOTE" not in serialized
    assert "private-tag" not in serialized
    assert '"hp_current"' not in serialized
    assert '"armor_class"' not in serialized
    assert public_blob.status_code == 200
    assert private_blob.status_code == 404


def test_combat_turn_navigation_reorder_and_all_defeated_state(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Turn Campaign")
    encounter = client.post(f"/api/campaigns/{campaign['id']}/combat-encounters", json={"title": "Turn Order"}).json()
    aria = client.post(
        f"/api/combat-encounters/{encounter['id']}/combatants",
        json={"name": "Aria", "initiative": 18, "public_visible": True},
    ).json()["combatants"][0]
    enemy = client.post(
        f"/api/combat-encounters/{encounter['id']}/combatants",
        json={"name": "Enemy", "initiative": 14, "public_visible": True, "is_defeated": True},
    ).json()["combatants"][1]
    bram = client.post(
        f"/api/combat-encounters/{encounter['id']}/combatants",
        json={"name": "Bram", "initiative": 11, "public_visible": True},
    ).json()["combatants"][2]
    reordered = client.post(
        f"/api/combat-encounters/{encounter['id']}/reorder",
        json={"combatant_ids": [bram["id"], enemy["id"], aria["id"]]},
    )
    next_turn = client.post(f"/api/combat-encounters/{encounter['id']}/next-turn")
    previous_wrap = client.post(f"/api/combat-encounters/{encounter['id']}/previous-turn")
    for combatant_id in (aria["id"], enemy["id"], bram["id"]):
        client.patch(f"/api/combatants/{combatant_id}", json={"is_defeated": True})
    all_defeated = client.post(f"/api/combat-encounters/{encounter['id']}/next-turn")
    shown = client.post("/api/player-display/show-initiative", json={"encounter_id": encounter["id"]})

    assert reordered.status_code == 200
    assert [combatant["id"] for combatant in reordered.json()["combatants"]] == [bram["id"], enemy["id"], aria["id"]]
    assert next_turn.json()["active_combatant_id"] == bram["id"]
    assert next_turn.json()["round"] == 2
    assert previous_wrap.json()["active_combatant_id"] == aria["id"]
    assert previous_wrap.json()["round"] == 1
    assert all_defeated.status_code == 200
    assert all_defeated.json()["active_combatant_id"] is None
    assert all_defeated.json()["round"] == 1
    assert shown.status_code == 200
    assert shown.json()["payload"]["active_combatant_id"] is None


def test_token_entity_reference_validates_same_campaign(seeded_settings):
    client = _client(seeded_settings)
    campaign_a = _create_campaign(client, "Token Entity A")
    campaign_b = _create_campaign(client, "Token Entity B")
    scene = _create_scene(client, campaign_a["id"], "Token Entity Scene")
    map_asset = _upload_image(client, campaign_a["id"], kind="map_image", visibility="public_displayable", name="Token Entity Map")
    campaign_map = _create_map(client, campaign_a["id"], map_asset["id"], "Token Entity Map")
    scene_map = _assign_scene_map(client, campaign_a["id"], scene["id"], campaign_map["id"], is_active=True)
    entity_a = client.post(f"/api/campaigns/{campaign_a['id']}/entities", json={"kind": "pc", "name": "Local PC"}).json()
    entity_b = client.post(f"/api/campaigns/{campaign_b['id']}/entities", json={"kind": "pc", "name": "Foreign PC"}).json()

    created = client.post(f"/api/scene-maps/{scene_map['id']}/tokens", json={"name": "Linked", "entity_id": entity_a["id"]})
    rejected = client.post(f"/api/scene-maps/{scene_map['id']}/tokens", json={"name": "Foreign", "entity_id": entity_b["id"]})

    assert created.status_code == 201
    assert created.json()["token"]["entity_id"] == entity_a["id"]
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "entity_campaign_mismatch"


def test_notes_and_public_snippets_snapshot_private_note_text(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Notes Campaign")
    session = _create_session(client, campaign["id"], "Notes Session")
    scene = _create_scene(client, campaign["id"], "Notes Scene", session["id"])
    asset = _upload_image(client, campaign["id"], kind="handout_image", visibility="private", name="Private Handout")
    secret_phrase = "SECRET: the duke is already dead"
    safe_text = "The silver key is cold to the touch."

    note_response = client.post(
        f"/api/campaigns/{campaign['id']}/notes",
        json={
            "title": "Vault clue",
            "private_body": f"{safe_text}\n\n{secret_phrase}",
            "tags": ["vault", "clue"],
            "session_id": session["id"],
            "scene_id": scene["id"],
            "asset_id": asset["id"],
        },
    )
    note = note_response.json()
    snippet_response = client.post(
        f"/api/campaigns/{campaign['id']}/public-snippets",
        json={"note_id": note["id"], "title": "Public clue", "body": safe_text, "format": "markdown"},
    )
    snippet = snippet_response.json()
    patched_note = client.patch(
        f"/api/notes/{note['id']}",
        json={"private_body": f"Changed private note\n\n{secret_phrase}\n\nA different clue."},
    )
    shown = client.post("/api/player-display/show-snippet", json={"snippet_id": snippet["id"]})

    assert note_response.status_code == 201
    assert note["private_body"].endswith(secret_phrase)
    assert note["source_label"] == "Internal Notes"
    assert snippet_response.status_code == 201
    assert patched_note.status_code == 200
    assert client.get(f"/api/campaigns/{campaign['id']}/public-snippets").json()["snippets"][0]["body"] == safe_text
    assert shown.status_code == 200
    display = shown.json()
    assert display["mode"] == "text"
    assert display["payload"] == {
        "type": "public_snippet",
        "snippet_id": snippet["id"],
        "title": "Public clue",
        "body": safe_text,
        "format": "markdown",
    }
    assert "note_id" not in display["payload"]
    assert secret_phrase not in json.dumps(display)
    assert display["updated_at"].endswith("Z")


def test_markdown_upload_import_copies_content_and_path_import_is_not_public(seeded_settings, tmp_path):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Import Notes Campaign")
    markdown_path = tmp_path / "session-secret.md"
    markdown_path.write_text("# Imported\n\nPrivate prep copied into SQLite.", encoding="utf-8")

    path_response = client.post(
        f"/api/campaigns/{campaign['id']}/notes/import-path",
        json={"source_path": str(markdown_path), "title": "Copied Import", "tags": ["imported"]},
    )
    upload_response = client.post(
        f"/api/campaigns/{campaign['id']}/notes/import-upload",
        data={"title": "Uploaded Import", "tags": "upload, note"},
        files={"file": ("upload.md", b"# Uploaded\n\nCopied upload body.", "text/markdown")},
    )
    bad_extension = client.post(
        f"/api/campaigns/{campaign['id']}/notes/import-upload",
        files={"file": ("bad.pdf", b"not markdown", "application/pdf")},
    )

    assert path_response.status_code == 404
    assert upload_response.status_code == 201
    assert upload_response.json()["source_label"] == "upload.md"
    assert upload_response.json()["tags"] == ["upload", "note"]
    assert bad_extension.status_code == 400
    assert bad_extension.json()["error"]["code"] == "unsupported_markdown_extension"


def test_public_snippet_validation_rejects_cross_campaign_note_and_show_does_not_mutate_runtime(seeded_settings):
    client = _client(seeded_settings)
    campaign_a = _create_campaign(client, "Snippet Campaign A")
    campaign_b = _create_campaign(client, "Snippet Campaign B")
    note_a = client.post(
        f"/api/campaigns/{campaign_a['id']}/notes",
        json={"title": "Private A", "private_body": "A secret"},
    ).json()
    scene = _create_scene(client, campaign_a["id"], "Runtime Scene")
    runtime_before = client.post("/api/runtime/activate-scene", json={"scene_id": scene["id"]}).json()

    cross_campaign = client.post(
        f"/api/campaigns/{campaign_b['id']}/public-snippets",
        json={"note_id": note_a["id"], "title": "Bad", "body": "Nope"},
    )
    snippet = client.post(
        f"/api/campaigns/{campaign_a['id']}/public-snippets",
        json={"note_id": note_a["id"], "title": "Safe", "body": "Public only"},
    ).json()
    shown = client.post("/api/player-display/show-snippet", json={"snippet_id": snippet["id"]})
    runtime_after = client.get("/api/runtime").json()

    assert cross_campaign.status_code == 400
    assert cross_campaign.json()["error"]["code"] == "note_campaign_mismatch"
    assert shown.status_code == 200
    assert runtime_after == runtime_before
    with get_engine(seeded_settings).connect() as connection:
        note_body = connection.execute(select(Note.private_body).where(Note.id == note_a["id"])).scalar_one()
        snippet_body = connection.execute(select(PublicSnippet.body).where(PublicSnippet.id == snippet["id"])).scalar_one()
    assert note_body == "A secret"
    assert snippet_body == "Public only"


def test_token_creation_sanitizes_public_payload_and_republishes_only_public_changes(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Token Campaign")
    scene = _create_scene(client, campaign["id"], "Token Scene")
    map_asset = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Token Map")
    campaign_map = _create_map(client, campaign["id"], map_asset["id"], "Token Map")
    scene_map = _assign_scene_map(client, campaign["id"], scene["id"], campaign_map["id"], is_active=True)
    shown = client.post("/api/player-display/show-map", json={"scene_map_id": scene_map["id"]})

    gm_only = client.post(
        f"/api/scene-maps/{scene_map['id']}/tokens",
        json={"name": "Secret Guard", "x": 12, "y": 14, "visibility": "gm_only"},
    )
    visible = client.post(
        f"/api/scene-maps/{scene_map['id']}/tokens",
        json={
            "name": "Nameless Threat",
            "x": 18,
            "y": 22,
            "width": 40,
            "height": 44,
            "rotation": 450,
            "visibility": "player_visible",
            "label_visibility": "hidden",
            "shape": "square",
            "color": "#abc",
            "border_color": "#123456",
        },
    )

    assert shown.status_code == 200
    assert gm_only.status_code == 201
    assert gm_only.json()["player_display"] is None
    assert visible.status_code == 201
    body = visible.json()
    assert body["token"]["rotation"] == 90
    assert body["token"]["color"] == "#AABBCC"
    public_tokens = body["player_display"]["payload"]["tokens"]
    assert [token["id"] for token in public_tokens] == [body["token"]["id"]]
    assert public_tokens[0]["name"] is None
    assert public_tokens[0]["style"]["shape"] == "square"
    assert "relative_path" not in json.dumps(body["player_display"]["payload"])

    listed = client.get(f"/api/scene-maps/{scene_map['id']}/tokens")
    assert listed.status_code == 200
    assert len(listed.json()["tokens"]) == 2
    assert listed.json()["updated_at"].endswith("Z")


def test_portrait_token_public_blob_is_active_only(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Portrait Token Campaign")
    scene = _create_scene(client, campaign["id"], "Portrait Token Scene")
    map_asset = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Portrait Map")
    portrait_asset = _upload_image(client, campaign["id"], kind="npc_portrait", visibility="public_displayable", name="Captain")
    inactive_asset = _upload_image(client, campaign["id"], kind="npc_portrait", visibility="public_displayable", name="Inactive Captain")
    campaign_map = _create_map(client, campaign["id"], map_asset["id"], "Portrait Map")
    scene_map = _assign_scene_map(client, campaign["id"], scene["id"], campaign_map["id"], is_active=True)
    client.post("/api/player-display/show-map", json={"scene_map_id": scene_map["id"]})

    created = client.post(
        f"/api/scene-maps/{scene_map['id']}/tokens",
        json={
            "name": "Captain",
            "x": 20,
            "y": 20,
            "visibility": "player_visible",
            "label_visibility": "player_visible",
            "shape": "portrait",
            "asset_id": portrait_asset["id"],
        },
    )
    active_blob = client.get(f"/api/player-display/assets/{portrait_asset['id']}/blob")
    inactive_blob = client.get(f"/api/player-display/assets/{inactive_asset['id']}/blob")

    assert created.status_code == 201
    public_token = created.json()["player_display"]["payload"]["tokens"][0]
    assert public_token["asset_id"] == portrait_asset["id"]
    assert public_token["asset_url"] == f"/api/player-display/assets/{portrait_asset['id']}/blob"
    assert active_blob.status_code == 200
    assert inactive_blob.status_code == 404
    assert inactive_blob.json()["error"]["code"] == "player_display_asset_not_active"


def test_hidden_until_revealed_token_is_recalculated_by_fog_republish(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Hidden Token Campaign")
    scene = _create_scene(client, campaign["id"], "Hidden Token Scene")
    map_asset = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", content=_image_bytes("PNG", (80, 80)), name="Hidden Map")
    campaign_map = _create_map(client, campaign["id"], map_asset["id"], "Hidden Map")
    scene_map = _assign_scene_map(client, campaign["id"], scene["id"], campaign_map["id"], is_active=True)
    client.post(f"/api/scene-maps/{scene_map['id']}/fog/enable")
    client.post("/api/player-display/show-map", json={"scene_map_id": scene_map["id"]})

    created = client.post(
        f"/api/scene-maps/{scene_map['id']}/tokens",
        json={
            "name": "Ambusher",
            "x": 30,
            "y": 30,
            "visibility": "hidden_until_revealed",
            "label_visibility": "player_visible",
        },
    )
    revealed = client.post(
        f"/api/scene-maps/{scene_map['id']}/fog/operations",
        json={"operations": [{"type": "reveal_rect", "rect": {"x": 20, "y": 20, "width": 20, "height": 20}}]},
    )

    assert created.status_code == 201
    assert created.json()["player_display"] is None
    assert revealed.status_code == 200
    tokens = revealed.json()["player_display"]["payload"]["tokens"]
    assert len(tokens) == 1
    assert tokens[0]["name"] == "Ambusher"


def test_token_update_delete_compare_public_payload_before_republish(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Token Mutation Campaign")
    scene = _create_scene(client, campaign["id"], "Token Mutation Scene")
    map_asset = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Mutation Map")
    campaign_map = _create_map(client, campaign["id"], map_asset["id"], "Mutation Map")
    scene_map = _assign_scene_map(client, campaign["id"], scene["id"], campaign_map["id"], is_active=True)
    client.post("/api/player-display/show-map", json={"scene_map_id": scene_map["id"]})
    created = client.post(
        f"/api/scene-maps/{scene_map['id']}/tokens",
        json={"name": "Public Token", "visibility": "player_visible", "label_visibility": "player_visible"},
    ).json()

    private_label_change = client.patch(
        f"/api/tokens/{created['token']['id']}",
        json={"label_visibility": "gm_only"},
    )
    delete_response = client.delete(f"/api/tokens/{created['token']['id']}")

    assert private_label_change.status_code == 200
    assert private_label_change.json()["player_display"] is not None
    assert private_label_change.json()["player_display"]["payload"]["tokens"][0]["name"] is None
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_token_id"] == created["token"]["id"]
    assert delete_response.json()["player_display"]["payload"]["tokens"] == []


def test_token_validation_rejects_cross_campaign_asset_and_bad_color(seeded_settings):
    client = _client(seeded_settings)
    campaign_a = _create_campaign(client, "Token Campaign A")
    campaign_b = _create_campaign(client, "Token Campaign B")
    scene = _create_scene(client, campaign_a["id"], "Token Validation Scene")
    map_asset = _upload_image(client, campaign_a["id"], kind="map_image", visibility="public_displayable", name="Validation Map")
    portrait_b = _upload_image(client, campaign_b["id"], kind="npc_portrait", visibility="public_displayable", name="Wrong Portrait")
    campaign_map = _create_map(client, campaign_a["id"], map_asset["id"], "Validation Map")
    scene_map = _assign_scene_map(client, campaign_a["id"], scene["id"], campaign_map["id"], is_active=True)

    cross_campaign = client.post(
        f"/api/scene-maps/{scene_map['id']}/tokens",
        json={"name": "Wrong Portrait", "asset_id": portrait_b["id"], "shape": "portrait"},
    )
    bad_color = client.post(
        f"/api/scene-maps/{scene_map['id']}/tokens",
        json={"name": "Bad Color", "color": "url(javascript:bad)"},
    )
    missing_scene_map = client.post(
        f"/api/scene-maps/{uuid.uuid4()}/tokens",
        json={"name": "Missing"},
    )

    assert cross_campaign.status_code == 400
    assert cross_campaign.json()["error"]["code"] == "asset_campaign_mismatch"
    assert bad_color.status_code == 400
    assert bad_color.json()["error"]["code"] == "invalid_token_color"
    assert missing_scene_map.status_code == 404
    assert missing_scene_map.json()["error"]["code"] == "scene_map_not_found"


def test_scene_activation_does_not_publish_map_to_player_display(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Scene Activation Map Campaign")
    scene = _create_scene(client, campaign["id"], "Scene Activation Map Scene")
    asset = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Scene Activation Map")
    campaign_map = _create_map(client, campaign["id"], asset["id"], "Scene Activation Map")
    _assign_scene_map(client, campaign["id"], scene["id"], campaign_map["id"], is_active=True)
    before_display = client.get("/api/player-display").json()

    runtime = client.post("/api/runtime/activate-scene", json={"scene_id": scene["id"]})
    after_display = client.get("/api/player-display").json()

    assert runtime.status_code == 200
    assert runtime.json()["active_scene_id"] == scene["id"]
    assert after_display == before_display


def test_scene_context_staging_is_private_until_explicit_publish(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Scene Context Campaign")
    session = _create_session(client, campaign["id"], "Scene Context Session")
    scene = _create_scene(client, campaign["id"], "Scene Context Scene", session["id"])
    asset = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Context Map")
    campaign_map = _create_map(client, campaign["id"], asset["id"], "Context Map")
    scene_map = _assign_scene_map(client, campaign["id"], scene["id"], campaign_map["id"], is_active=True)
    note = client.post(
        f"/api/campaigns/{campaign['id']}/notes",
        json={
            "title": "Private scene note",
            "private_body": "SAFE TEXT\n\nPRIVATE SCENE SECRET",
            "scene_id": scene["id"],
        },
    ).json()
    snippet = client.post(
        f"/api/campaigns/{campaign['id']}/public-snippets",
        json={"note_id": note["id"], "title": "Public cue", "body": "SAFE TEXT", "format": "markdown"},
    ).json()
    entity = client.post(
        f"/api/campaigns/{campaign['id']}/entities",
        json={"kind": "npc", "name": "Private Ally", "notes": "PRIVATE ENTITY SECRET", "tags": ["private-tag"]},
    ).json()
    encounter = client.post(
        f"/api/campaigns/{campaign['id']}/combat-encounters",
        json={"title": "Context Fight", "session_id": session["id"], "scene_id": scene["id"]},
    ).json()
    client.post(
        f"/api/combat-encounters/{encounter['id']}/combatants",
        json={"name": "Hidden Foe", "notes": "PRIVATE COMBAT SECRET", "conditions": [{"label": "PRIVATE CONDITION"}]},
    )
    before_display = client.get("/api/player-display").json()

    activated = client.post("/api/runtime/activate-scene", json={"scene_id": scene["id"]})
    linked_entity = client.post(
        f"/api/scenes/{scene['id']}/entity-links",
        json={"entity_id": entity["id"], "role": "threat", "sort_order": 1, "notes": "GM-only scene link note"},
    )
    linked_snippet = client.post(
        f"/api/scenes/{scene['id']}/public-snippet-links",
        json={"public_snippet_id": snippet["id"], "sort_order": 0},
    )
    patched = client.patch(
        f"/api/scenes/{scene['id']}/context",
        json={
            "active_encounter_id": encounter["id"],
            "staged_display_mode": "public_snippet",
            "staged_public_snippet_id": snippet["id"],
        },
    )
    after_private_ops = client.get("/api/player-display").json()
    context = client.get(f"/api/scenes/{scene['id']}/context")
    published = client.post(f"/api/scenes/{scene['id']}/publish-staged-display")

    assert activated.status_code == 200
    assert linked_entity.status_code == 201
    assert linked_snippet.status_code == 201
    assert patched.status_code == 200
    assert after_private_ops == before_display
    assert context.status_code == 200
    context_body = context.json()
    assert context_body["scene"]["id"] == scene["id"]
    assert context_body["active_map"]["id"] == scene_map["id"]
    assert [item["id"] for item in context_body["notes"]] == [note["id"]]
    assert context_body["entities"][0]["entity_id"] == entity["id"]
    assert context_body["public_snippets"][0]["public_snippet_id"] == snippet["id"]
    assert context_body["active_encounter"]["id"] == encounter["id"]
    assert published.status_code == 200
    display = published.json()
    assert display["mode"] == "text"
    assert display["payload"]["type"] == "public_snippet"
    assert display["payload"]["body"] == "SAFE TEXT"
    serialized = json.dumps(display)
    assert "PRIVATE SCENE SECRET" not in serialized
    assert "PRIVATE ENTITY SECRET" not in serialized
    assert "PRIVATE COMBAT SECRET" not in serialized
    assert "PRIVATE CONDITION" not in serialized
    assert "private-tag" not in serialized


def test_scene_context_publish_validation_and_unlink_semantics(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Scene Context Validation")
    other_campaign = _create_campaign(client, "Other Scene Context Validation")
    scene = _create_scene(client, campaign["id"], "Context Validation Scene")
    other_scene = _create_scene(client, campaign["id"], "Other Scene")
    unlinked_snippet = client.post(
        f"/api/campaigns/{campaign['id']}/public-snippets",
        json={"title": "Unlinked", "body": "Unlinked public text", "format": "markdown"},
    ).json()
    linked_snippet = client.post(
        f"/api/campaigns/{campaign['id']}/public-snippets",
        json={"title": "Linked", "body": "Linked public text", "format": "markdown"},
    ).json()
    entity = client.post(f"/api/campaigns/{campaign['id']}/entities", json={"kind": "npc", "name": "Linked NPC"}).json()
    other_encounter = client.post(
        f"/api/campaigns/{campaign['id']}/combat-encounters",
        json={"title": "Wrong Scene Encounter", "scene_id": other_scene["id"]},
    ).json()
    foreign_encounter = client.post(
        f"/api/campaigns/{other_campaign['id']}/combat-encounters",
        json={"title": "Foreign Encounter"},
    ).json()

    none_publish = client.post(f"/api/scenes/{scene['id']}/publish-staged-display")
    missing_map_mode = client.patch(f"/api/scenes/{scene['id']}/context", json={"staged_display_mode": "active_map"})
    missing_map_publish = client.post(f"/api/scenes/{scene['id']}/publish-staged-display")
    unlinked_patch = client.patch(
        f"/api/scenes/{scene['id']}/context",
        json={"staged_display_mode": "public_snippet", "staged_public_snippet_id": unlinked_snippet["id"]},
    )
    wrong_scene_encounter_patch = client.patch(f"/api/scenes/{scene['id']}/context", json={"active_encounter_id": other_encounter["id"]})
    wrong_campaign_encounter_patch = client.patch(
        f"/api/scenes/{scene['id']}/context",
        json={"active_encounter_id": foreign_encounter["id"]},
    )
    linked_entity = client.post(f"/api/scenes/{scene['id']}/entity-links", json={"entity_id": entity["id"]})
    linked_snippet_response = client.post(
        f"/api/scenes/{scene['id']}/public-snippet-links",
        json={"public_snippet_id": linked_snippet["id"]},
    )
    entity_link_id = linked_entity.json()["entities"][0]["id"]
    snippet_link_id = linked_snippet_response.json()["public_snippets"][0]["id"]
    unlinked_entity = client.delete(f"/api/scene-entity-links/{entity_link_id}")
    unlinked_public_snippet = client.delete(f"/api/scene-public-snippet-links/{snippet_link_id}")
    entity_still_exists = client.get(f"/api/entities/{entity['id']}")
    snippets_still_exist = client.get(f"/api/campaigns/{campaign['id']}/public-snippets")

    assert none_publish.status_code == 400
    assert none_publish.json()["error"]["code"] == "no_staged_display"
    assert missing_map_mode.status_code == 200
    assert missing_map_publish.status_code == 400
    assert missing_map_publish.json()["error"]["code"] == "active_scene_map_required"
    assert unlinked_patch.status_code == 400
    assert unlinked_patch.json()["error"]["code"] == "public_snippet_not_linked_to_scene"
    assert wrong_scene_encounter_patch.status_code == 400
    assert wrong_scene_encounter_patch.json()["error"]["code"] == "combat_encounter_scene_mismatch"
    assert wrong_campaign_encounter_patch.status_code == 400
    assert wrong_campaign_encounter_patch.json()["error"]["code"] == "combat_encounter_campaign_mismatch"
    assert linked_entity.status_code == 201
    assert linked_snippet_response.status_code == 201
    assert unlinked_entity.status_code == 200
    assert unlinked_public_snippet.status_code == 200
    assert entity_still_exists.status_code == 200
    assert any(snippet["id"] == linked_snippet["id"] for snippet in snippets_still_exist.json()["snippets"])


def test_enable_fog_creates_hidden_all_mask_idempotently(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Fog Campaign")
    scene = _create_scene(client, campaign["id"], "Fog Scene")
    asset = _upload_image(client, campaign["id"], kind="map_image", name="Fog Map")
    campaign_map = _create_map(client, campaign["id"], asset["id"], "Fog Map")
    scene_map = _assign_scene_map(client, campaign["id"], scene["id"], campaign_map["id"], is_active=True)

    first = client.post(f"/api/scene-maps/{scene_map['id']}/fog/enable")
    second = client.post(f"/api/scene-maps/{scene_map['id']}/fog/enable")
    mask = client.get(first.json()["mask_url"])
    image = Image.open(io.BytesIO(mask.content)).convert("L")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert first.json()["revision"] == 1
    assert first.json()["width"] == campaign_map["width"]
    assert first.json()["height"] == campaign_map["height"]
    assert first.json()["mask_url"].startswith(f"/api/scene-maps/{scene_map['id']}/fog/mask?revision=1")
    assert mask.status_code == 200
    assert image.getextrema() == (0, 0)


def test_fog_operations_update_pixels_and_revision(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Fog Ops Campaign")
    scene = _create_scene(client, campaign["id"], "Fog Ops Scene")
    asset = _upload_image(client, campaign["id"], kind="map_image", content=_image_bytes("PNG", (100, 80)), name="Fog Ops Map")
    campaign_map = _create_map(client, campaign["id"], asset["id"], "Fog Ops Map")
    scene_map = _assign_scene_map(client, campaign["id"], scene["id"], campaign_map["id"], is_active=True)
    client.post(f"/api/scene-maps/{scene_map['id']}/fog/enable")

    reveal_rect = client.post(
        f"/api/scene-maps/{scene_map['id']}/fog/operations",
        json={"operations": [{"type": "reveal_rect", "rect": {"x": 10, "y": 12, "width": 20, "height": 16}}]},
    )
    hide_rect = client.post(
        f"/api/scene-maps/{scene_map['id']}/fog/operations",
        json={"operations": [{"type": "hide_rect", "rect": {"x": 12, "y": 14, "width": 4, "height": 4}}]},
    )
    mask_after_rects = client.get(hide_rect.json()["fog"]["mask_url"])
    image_after_rects = Image.open(io.BytesIO(mask_after_rects.content)).convert("L")
    brush = client.post(
        f"/api/scene-maps/{scene_map['id']}/fog/operations",
        json={"operations": [{"type": "reveal_brush", "radius": 5, "points": [{"x": 70, "y": 40}, {"x": 75, "y": 45}]}]},
    )
    reveal_all = client.post(
        f"/api/scene-maps/{scene_map['id']}/fog/operations",
        json={"operations": [{"type": "reveal_all"}]},
    )
    hide_all = client.post(
        f"/api/scene-maps/{scene_map['id']}/fog/operations",
        json={"operations": [{"type": "hide_all"}]},
    )
    hidden_mask = client.get(hide_all.json()["fog"]["mask_url"])
    hidden_image = Image.open(io.BytesIO(hidden_mask.content)).convert("L")

    assert reveal_rect.status_code == 200
    assert reveal_rect.json()["fog"]["revision"] == 2
    assert hide_rect.status_code == 200
    assert brush.status_code == 200
    assert brush.json()["fog"]["revision"] == 4
    assert reveal_all.status_code == 200
    assert reveal_all.json()["fog"]["revision"] == 5
    assert hide_all.status_code == 200
    assert hide_all.json()["fog"]["revision"] == 6
    assert image_after_rects.getpixel((11, 13)) == 255
    assert image_after_rects.getpixel((13, 15)) == 0
    assert hidden_image.getextrema() == (0, 0)


def test_fog_operations_validate_shapes_coordinates_and_radius(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Fog Validation Campaign")
    scene = _create_scene(client, campaign["id"], "Fog Validation Scene")
    asset = _upload_image(client, campaign["id"], kind="map_image", name="Fog Validation Map")
    campaign_map = _create_map(client, campaign["id"], asset["id"], "Fog Validation Map")
    scene_map = _assign_scene_map(client, campaign["id"], scene["id"], campaign_map["id"], is_active=True)

    missing_rect = client.post(
        f"/api/scene-maps/{scene_map['id']}/fog/operations",
        json={"operations": [{"type": "reveal_rect"}]},
    )
    bad_radius = client.post(
        f"/api/scene-maps/{scene_map['id']}/fog/operations",
        json={"operations": [{"type": "reveal_brush", "radius": 0, "points": [{"x": 1, "y": 1}]}]},
    )
    unknown = client.post(
        f"/api/scene-maps/{scene_map['id']}/fog/operations",
        json={"operations": [{"type": "summon_darkness"}]},
    )
    missing_scene_map = client.post(
        f"/api/scene-maps/{uuid.uuid4()}/fog/operations",
        json={"operations": [{"type": "reveal_all"}]},
    )

    assert missing_rect.status_code == 400
    assert missing_rect.json()["error"]["code"] == "invalid_fog_operation"
    assert bad_radius.status_code == 400
    assert bad_radius.json()["error"]["code"] == "invalid_fog_radius"
    assert unknown.status_code == 400
    assert unknown.json()["error"]["code"] == "invalid_fog_operation"
    assert missing_scene_map.status_code == 404
    assert missing_scene_map.json()["error"]["code"] == "scene_map_not_found"


def test_show_map_includes_fog_and_fog_operations_conditionally_republish(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Fog Publish Campaign")
    scene = _create_scene(client, campaign["id"], "Fog Publish Scene")
    asset = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Fog Publish Map")
    campaign_map = _create_map(client, campaign["id"], asset["id"], "Fog Publish Map")
    scene_map = _assign_scene_map(client, campaign["id"], scene["id"], campaign_map["id"], is_active=True)
    fog = client.post(f"/api/scene-maps/{scene_map['id']}/fog/enable").json()

    shown = client.post("/api/player-display/show-map", json={"scene_map_id": scene_map["id"]})
    republished = client.post(
        f"/api/scene-maps/{scene_map['id']}/fog/operations",
        json={"operations": [{"type": "reveal_rect", "rect": {"x": 1, "y": 1, "width": 10, "height": 10}}]},
    )
    public_mask = client.get(republished.json()["player_display"]["payload"]["fog"]["mask_url"])

    assert shown.status_code == 200
    assert shown.json()["payload"]["fog"]["mask_id"] == fog["id"]
    assert shown.json()["payload"]["fog"]["mask_url"] == f"/api/player-display/fog/{fog['id']}/mask?revision=1"
    assert "relative_path" not in json.dumps(shown.json()["payload"])
    assert republished.status_code == 200
    assert republished.json()["player_display"]["mode"] == "map"
    assert republished.json()["player_display"]["payload"]["scene_map_id"] == scene_map["id"]
    assert republished.json()["player_display"]["payload"]["fog"]["revision"] == 2
    assert public_mask.status_code == 200
    assert public_mask.headers["content-type"].startswith("image/png")

    other_scene = _create_scene(client, campaign["id"], "Other Fog Scene")
    other_asset = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Other Fog Map")
    other_map = _create_map(client, campaign["id"], other_asset["id"], "Other Fog Map")
    other_scene_map = _assign_scene_map(client, campaign["id"], other_scene["id"], other_map["id"], is_active=True)
    no_publish = client.post(
        f"/api/scene-maps/{other_scene_map['id']}/fog/operations",
        json={"operations": [{"type": "reveal_all"}]},
    )
    assert no_publish.status_code == 200
    assert no_publish.json()["player_display"] is None


def test_public_fog_endpoint_is_active_only_and_rejects_path_escape(seeded_settings):
    client = _client(seeded_settings)
    campaign = _create_campaign(client, "Fog Public Campaign")
    scene = _create_scene(client, campaign["id"], "Fog Public Scene")
    active_asset = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Active Fog Map")
    inactive_asset = _upload_image(client, campaign["id"], kind="map_image", visibility="public_displayable", name="Inactive Fog Map")
    active_map = _create_map(client, campaign["id"], active_asset["id"], "Active Fog Map")
    inactive_map = _create_map(client, campaign["id"], inactive_asset["id"], "Inactive Fog Map")
    active_scene_map = _assign_scene_map(client, campaign["id"], scene["id"], active_map["id"], is_active=True)
    inactive_scene_map = _assign_scene_map(client, campaign["id"], scene["id"], inactive_map["id"], is_active=False)
    active_fog = client.post(f"/api/scene-maps/{active_scene_map['id']}/fog/enable").json()
    inactive_fog = client.post(f"/api/scene-maps/{inactive_scene_map['id']}/fog/enable").json()
    client.post("/api/player-display/show-map", json={"scene_map_id": active_scene_map["id"]})

    active = client.get(f"/api/player-display/fog/{active_fog['id']}/mask")
    inactive = client.get(f"/api/player-display/fog/{inactive_fog['id']}/mask")

    assert active.status_code == 200
    assert inactive.status_code == 404
    assert inactive.json()["error"]["code"] == "player_display_fog_not_active"

    engine = get_engine(seeded_settings)
    with engine.begin() as connection:
        connection.execute(
            SceneMapFogMask.__table__.update()
            .where(SceneMapFogMask.id == active_fog["id"])
            .values(relative_path="../fog-escape.png", updated_at=utc_now_z())
        )
    escaped = client.get(f"/api/player-display/fog/{active_fog['id']}/mask")
    assert escaped.status_code == 500
    assert escaped.json()["error"]["code"] == "fog_path_invalid"
    assert str(seeded_settings.asset_dir) not in escaped.text


def test_read_404s_use_error_envelope(seeded_settings):
    response = _client(seeded_settings).get(f"/api/campaigns/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "campaign_not_found", "message": "Campaign not found"}}


def test_uuid_path_validation_uses_error_envelope(seeded_settings):
    response = _client(seeded_settings).get("/api/campaigns/not-a-campaign")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed"
    assert body["error"]["details"]


def test_request_validation_uses_error_envelope(seeded_settings):
    response = _client(seeded_settings).post("/api/campaigns", json={"name": "   "})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"]


def test_integrity_error_uses_safe_error_envelope(seeded_settings):
    app = create_app(seeded_settings)

    @app.get("/test-integrity-error")
    def test_integrity_error():  # noqa: ANN202
        raise IntegrityError("statement", "params", Exception("raw database detail"))

    response = TestClient(app, base_url="http://127.0.0.1:8000").get("/test-integrity-error")
    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "database_integrity_error",
            "message": "Database integrity error",
        }
    }


def test_workspace_widgets_return_defaults_in_deterministic_order(seeded_settings):
    response = _client(seeded_settings).get("/api/workspace/widgets")
    assert response.status_code == 200
    body = response.json()
    widgets = body["widgets"]
    assert body["updated_at"].endswith("Z")
    assert [widget["kind"] for widget in widgets] == [widget.kind for widget in DEFAULT_WORKSPACE_WIDGETS]
    assert [widget["z_index"] for widget in widgets] == sorted(widget["z_index"] for widget in widgets)
    assert widgets[0]["scope_type"] == "global"
    assert widgets[0]["scope_id"] is None
    assert widgets[0]["config"] == {}
    placeholder = next(widget for widget in widgets if widget["kind"] == "map_display")
    assert placeholder["config"]["placeholder"] is True


def test_workspace_widget_patch_persists_layout_and_returns_widget(seeded_settings):
    client = _client(seeded_settings)
    widget = client.get("/api/workspace/widgets").json()["widgets"][0]

    response = client.patch(
        f"/api/workspace/widgets/{widget['id']}",
        json={"x": 111, "y": 222, "width": 444, "height": 333, "z_index": 999, "minimized": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["x"] == 111
    assert body["y"] == 222
    assert body["width"] == 444
    assert body["height"] == 333
    assert body["z_index"] == 999
    assert body["minimized"] is True
    assert body["updated_at"].endswith("Z")

    stored = client.get("/api/workspace/widgets").json()["widgets"]
    updated = next(item for item in stored if item["id"] == widget["id"])
    assert updated["x"] == 111
    assert updated["minimized"] is True


def test_invalid_workspace_widget_id_returns_error_envelope(seeded_settings):
    response = _client(seeded_settings).patch(
        f"/api/workspace/widgets/{uuid.uuid4()}",
        json={"x": 10},
    )
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "workspace_widget_not_found",
            "message": "Workspace widget not found",
        }
    }


def test_workspace_reset_restores_defaults_and_preserves_unknown_widget(seeded_settings):
    client = _client(seeded_settings)
    first = client.get("/api/workspace/widgets").json()["widgets"][0]
    patched = client.patch(f"/api/workspace/widgets/{first['id']}", json={"x": 777, "y": 888})
    assert patched.status_code == 200
    unknown_id = str(uuid.uuid4())
    now = utc_now_z()
    with get_engine(seeded_settings).begin() as connection:
        connection.execute(
            insert(WorkspaceWidget).values(
                id=unknown_id,
                scope_type="global",
                scope_id=None,
                kind="custom_future_widget",
                title="Custom Future Widget",
                x=2000,
                y=1000,
                width=320,
                height=220,
                z_index=1000,
                locked=False,
                minimized=False,
                config_json="{}",
                created_at=now,
                updated_at=now,
            )
        )

    response = client.post("/api/workspace/widgets/reset")

    assert response.status_code == 200
    body = response.json()
    restored = next(widget for widget in body["widgets"] if widget["id"] == first["id"])
    expected = DEFAULT_WORKSPACE_WIDGETS[0]
    assert restored["x"] == expected.x
    assert restored["y"] == expected.y
    assert any(widget["id"] == unknown_id for widget in body["widgets"])
    assert len(body["widgets"]) == len(DEFAULT_WORKSPACE_WIDGETS) + 1
