from __future__ import annotations

import json
import sqlite3
import tarfile

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.app.storage_export import DB_ARCHIVE_PATH, EXPORT_MANIFEST


def _client(settings) -> TestClient:  # noqa: ANN001
    return TestClient(create_app(settings), base_url="http://127.0.0.1:8000")


def _campaign_session(client: TestClient) -> tuple[str, str]:
    campaign = client.post("/api/campaigns", json={"name": "Scribe Campaign"}).json()
    session = client.post(f"/api/campaigns/{campaign['id']}/sessions", json={"title": "Opening"}).json()
    return campaign["id"], session["id"]


def test_live_capture_orders_and_correction_projection(migrated_settings):
    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)

    first = client.post(
        f"/api/campaigns/{campaign_id}/scribe/transcript-events",
        json={"session_id": session_id, "body": "Aureon offered the party a sealed coin."},
    )
    second = client.post(
        f"/api/campaigns/{campaign_id}/scribe/transcript-events",
        json={"session_id": session_id, "body": "Mira refused the gift."},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["order_index"] == 0
    assert second.json()["order_index"] == 1
    assert first.json()["public_safe"] is False

    correction = client.post(
        f"/api/scribe/transcript-events/{second.json()['id']}/correct",
        json={"body": "Mira accepted the gift, but marked the ribbon."},
    )
    assert correction.status_code == 201
    assert correction.json()["corrects_event_id"] == second.json()["id"]

    response = client.get(f"/api/campaigns/{campaign_id}/scribe/transcript-events?session_id={session_id}")
    assert response.status_code == 200
    body = response.json()
    assert len(body["events"]) == 3
    assert [event["body"] for event in body["projection"]] == [
        "Aureon offered the party a sealed coin.",
        "Mira accepted the gift, but marked the ribbon.",
    ]


def test_recap_memory_recall_and_export_redaction(migrated_settings, monkeypatch):
    from backend.app.api import routes_llm

    monkeypatch.setenv("MYROLL_LLM_API_KEY", "sk-secret-test-value")
    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    client.post(
        f"/api/campaigns/{campaign_id}/scribe/transcript-events",
        json={"session_id": session_id, "body": "Aureon the goldsmith revealed a sealed coin from Chult."},
    )
    evidence_source: dict[str, str] = {}

    def fake_probe(profile):  # noqa: ANN001
        return "level_2_json_validated", {"json_probe": "ok"}, "Provider returned valid JSON."

    def fake_send_chat(profile, payload, *, timeout=60.0):  # noqa: ANN001
        content = "\n".join(message["content"] for message in payload["messages"])
        if "Repair malformed JSON" in content:
            raise AssertionError("repair should not be needed for valid fixture JSON")
        return (
            json.dumps(
                {
                    "privateRecap": {
                        "title": "Aureon's Coin",
                        "bodyMarkdown": "Aureon the goldsmith revealed a sealed coin from Chult.",
                    },
                    "memoryCandidateDrafts": [
                        {
                            "title": "Aureon revealed a coin",
                            "body": "Aureon the goldsmith revealed a sealed coin from Chult.",
                            "claimStrength": "directly_evidenced",
                            "evidenceRefs": [
                                {
                                    "kind": "session_transcript_event",
                                    "id": evidence_source["id"],
                                    "quote": "Aureon the goldsmith revealed a sealed coin from Chult.",
                                }
                            ],
                        },
                        {
                            "title": "Weak guess",
                            "body": "The coin may be cursed.",
                            "claimStrength": "weak_inference",
                            "evidenceRefs": [],
                        },
                    ],
                    "continuityWarnings": [],
                    "unresolvedThreads": ["What is the sealed coin?"],
                }
            ),
            {"usage": {"prompt_tokens": 100, "completion_tokens": 80}},
        )

    monkeypatch.setattr(routes_llm, "_probe_provider", fake_probe)
    monkeypatch.setattr(routes_llm, "_send_chat", fake_send_chat)

    provider = client.post(
        "/api/llm/provider-profiles",
        json={
            "label": "Fixture provider",
            "vendor": "custom",
            "base_url": "http://127.0.0.1:9999/v1",
            "model_id": "fixture-model",
            "key_source": {"type": "env", "ref": "MYROLL_LLM_API_KEY"},
        },
    )
    assert provider.status_code == 201
    provider_id = provider.json()["id"]
    assert "sk-secret-test-value" not in json.dumps(provider.json())

    probe = client.post(f"/api/llm/provider-profiles/{provider_id}/test")
    assert probe.status_code == 200
    assert probe.json()["conformance_level"] == "level_2_json_validated"

    preview = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={"session_id": session_id, "task_kind": "session.build_recap", "gm_instruction": "Focus on objects."},
    )
    assert preview.status_code == 201
    preview_body = preview.json()
    assert preview_body["review_status"] == "unreviewed"
    assert preview_body["source_refs"]
    assert "Aureon" in preview_body["rendered_prompt"]
    evidence_source["id"] = preview_body["source_refs"][0]["id"]

    reviewed = client.post(f"/api/llm/context-packages/{preview_body['id']}/review")
    assert reviewed.status_code == 200
    assert reviewed.json()["review_status"] == "reviewed"

    recap = client.post(
        f"/api/campaigns/{campaign_id}/llm/session-recap/build",
        json={"session_id": session_id, "provider_profile_id": provider_id, "context_package_id": preview_body["id"]},
    )
    assert recap.status_code == 200
    recap_body = recap.json()
    assert recap_body["run"]["status"] == "succeeded"
    assert len(recap_body["candidates"]) == 1
    assert len(recap_body["rejected_drafts"]) == 1

    saved = client.post(
        f"/api/campaigns/{campaign_id}/scribe/session-recaps",
        json={
            "session_id": session_id,
            "title": recap_body["bundle"]["privateRecap"]["title"],
            "body_markdown": recap_body["bundle"]["privateRecap"]["bodyMarkdown"],
            "source_llm_run_id": recap_body["run"]["id"],
            "evidence_refs": preview_body["source_refs"],
        },
    )
    assert saved.status_code == 201

    candidate_id = recap_body["candidates"][0]["id"]
    accepted = client.post(f"/api/scribe/memory-candidates/{candidate_id}/accept")
    accepted_again = client.post(f"/api/scribe/memory-candidates/{candidate_id}/accept")
    assert accepted.status_code == 200
    assert accepted_again.status_code == 200
    assert accepted.json()["id"] == accepted_again.json()["id"]

    recall = client.post(f"/api/campaigns/{campaign_id}/scribe/recall", json={"query": "goldsmith"})
    assert recall.status_code == 200
    assert recall.json()["hits"][0]["source_kind"] == "campaign_memory_entry"

    export = client.post("/api/storage/export")
    assert export.status_code == 200
    archive_path = migrated_settings.export_dir / export.json()["archive_name"]
    with tarfile.open(archive_path, "r:gz") as archive:
        manifest = json.loads(archive.extractfile(EXPORT_MANIFEST).read().decode("utf-8"))  # type: ignore[union-attr]
        db_bytes = archive.extractfile(DB_ARCHIVE_PATH).read()  # type: ignore[union-attr]
    assert manifest["llm_payloads_included"] is False

    snapshot = migrated_settings.export_dir / "snapshot.sqlite3"
    snapshot.write_bytes(db_bytes)
    connection = sqlite3.connect(snapshot)
    try:
        assert connection.execute("SELECT request_json, response_text, normalized_output_json FROM llm_runs").fetchone() == (
            None,
            None,
            None,
        )
        assert connection.execute("SELECT rendered_prompt, source_refs_json FROM llm_context_packages").fetchone() == (
            "[redacted for export]",
            "[]",
        )
    finally:
        connection.close()


def test_recap_rejects_memory_candidate_with_unknown_evidence_ref(migrated_settings, monkeypatch):
    from backend.app.api import routes_llm

    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    client.post(
        f"/api/campaigns/{campaign_id}/scribe/transcript-events",
        json={"session_id": session_id, "body": "Aureon recorded the party's debt."},
    )

    def fake_probe(profile):  # noqa: ANN001
        return "level_2_json_validated", {"json_probe": "ok"}, "Provider returned valid JSON."

    def fake_send_chat(profile, payload, *, timeout=60.0):  # noqa: ANN001, ARG001
        return (
            json.dumps(
                {
                    "privateRecap": {"title": "Debt", "bodyMarkdown": "Aureon recorded the party's debt."},
                    "memoryCandidateDrafts": [
                        {
                            "title": "Aureon recorded a debt",
                            "body": "Aureon recorded the party's debt.",
                            "claimStrength": "directly_evidenced",
                            "evidenceRefs": [
                                {
                                    "kind": "session_transcript_event",
                                    "id": "not-a-real-source",
                                    "quote": "Aureon recorded the party's debt.",
                                }
                            ],
                        }
                    ],
                    "continuityWarnings": [],
                    "unresolvedThreads": [],
                }
            ),
            {"usage": {"prompt_tokens": 100, "completion_tokens": 80}},
        )

    monkeypatch.setattr(routes_llm, "_probe_provider", fake_probe)
    monkeypatch.setattr(routes_llm, "_send_chat", fake_send_chat)

    provider = client.post(
        "/api/llm/provider-profiles",
        json={
            "label": "Fixture provider",
            "vendor": "custom",
            "base_url": "http://127.0.0.1:9999/v1",
            "model_id": "fixture-model",
            "key_source": {"type": "none"},
        },
    )
    provider_id = provider.json()["id"]
    assert client.post(f"/api/llm/provider-profiles/{provider_id}/test").status_code == 200
    preview = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={"session_id": session_id, "task_kind": "session.build_recap", "gm_instruction": ""},
    ).json()
    assert client.post(f"/api/llm/context-packages/{preview['id']}/review").status_code == 200

    recap = client.post(
        f"/api/campaigns/{campaign_id}/llm/session-recap/build",
        json={"session_id": session_id, "provider_profile_id": provider_id, "context_package_id": preview["id"]},
    )

    assert recap.status_code == 200
    body = recap.json()
    assert body["candidates"] == []
    assert body["rejected_drafts"][0]["errors"] == [
        "evidence_source_missing",
        "evidence_requires_known_source",
        "direct_evidence_requires_valid_quote",
    ]


def test_repair_provider_error_finalizes_child_run(migrated_settings, monkeypatch):
    from backend.app.api import routes_llm

    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    client.post(
        f"/api/campaigns/{campaign_id}/scribe/transcript-events",
        json={"session_id": session_id, "body": "The party entered the archive."},
    )

    def fake_probe(profile):  # noqa: ANN001
        return "level_2_json_validated", {"json_probe": "ok"}, "Provider returned valid JSON."

    calls = {"count": 0}

    def fake_send_chat(profile, payload, *, timeout=60.0):  # noqa: ANN001, ARG001
        calls["count"] += 1
        if calls["count"] == 1:
            return ("not json", {"usage": {"prompt_tokens": 100, "completion_tokens": 20}})
        raise routes_llm.api_error(504, "provider_timeout", "Provider request timed out")

    monkeypatch.setattr(routes_llm, "_probe_provider", fake_probe)
    monkeypatch.setattr(routes_llm, "_send_chat", fake_send_chat)

    provider = client.post(
        "/api/llm/provider-profiles",
        json={
            "label": "Fixture provider",
            "vendor": "custom",
            "base_url": "http://127.0.0.1:9999/v1",
            "model_id": "fixture-model",
            "key_source": {"type": "none"},
        },
    )
    provider_id = provider.json()["id"]
    assert client.post(f"/api/llm/provider-profiles/{provider_id}/test").status_code == 200
    preview = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={"session_id": session_id, "task_kind": "session.build_recap", "gm_instruction": ""},
    ).json()
    assert client.post(f"/api/llm/context-packages/{preview['id']}/review").status_code == 200

    recap = client.post(
        f"/api/campaigns/{campaign_id}/llm/session-recap/build",
        json={"session_id": session_id, "provider_profile_id": provider_id, "context_package_id": preview["id"]},
    )
    assert recap.status_code == 504

    connection = sqlite3.connect(migrated_settings.db_path)
    try:
        rows = connection.execute(
            "SELECT id, task_kind, status, error_code, parent_run_id FROM llm_runs ORDER BY created_at, task_kind"
        ).fetchall()
    finally:
        connection.close()
    parent_id = rows[0][0]
    assert rows[0][1:] == ("session.build_recap", "failed", "parse_failed", None)
    assert rows[1][1:] == ("session.build_recap.repair", "failed", "provider_timeout", parent_id)


def _fixture_provider(client: TestClient, monkeypatch, fake_send_chat, *, level: str = "level_2_json_validated") -> str:  # noqa: ANN001
    from backend.app.api import routes_llm

    def fake_probe(profile):  # noqa: ANN001
        return level, {"json_probe": "ok"}, "Provider returned valid JSON."

    monkeypatch.setattr(routes_llm, "_probe_provider", fake_probe)
    monkeypatch.setattr(routes_llm, "_send_chat", fake_send_chat)

    provider = client.post(
        "/api/llm/provider-profiles",
        json={
            "label": "Fixture provider",
            "vendor": "custom",
            "base_url": "http://127.0.0.1:9999/v1",
            "model_id": "fixture-model",
            "key_source": {"type": "none"},
        },
    )
    assert provider.status_code == 201
    provider_id = provider.json()["id"]
    assert client.post(f"/api/llm/provider-profiles/{provider_id}/test").status_code == 200
    return provider_id


def _proposal_fixture(option_count: int = 3) -> dict[str, object]:
    options = []
    for index in range(option_count):
        number = index + 1
        options.append(
            {
                "title": f"Direction {number}",
                "summary": f"Short branch direction {number}.",
                "body": f"RAW PROPOSAL BODY {number}: Captain Varos betrayed the party in a draft-only future.",
                "consequences": f"Possible consequences if played {number}.",
                "whatThisReveals": f"Speculative reveal {number}.",
                "whatStaysHidden": f"Hidden thread {number}.",
                "planningMarkerText": f"GM is considering developing Captain Varos branch {number} as a political debt.",
                "proposedDelta": {"possible": f"direction-{number}"},
            }
        )
    return {"title": "Varos branch directions", "proposalOptions": options}


def _build_reviewed_branch_preview(
    client: TestClient,
    *,
    campaign_id: str,
    session_id: str | None,
    scene_id: str | None = None,
    scope_kind: str = "session",
    instruction: str = "Make Captain Varos politically costly.",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "task_kind": "scene.branch_directions",
        "scope_kind": scope_kind,
        "gm_instruction": instruction,
    }
    if session_id is not None:
        payload["session_id"] = session_id
    if scene_id is not None:
        payload["scene_id"] = scene_id
    preview = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json=payload,
    )
    assert preview.status_code == 201
    body = preview.json()
    assert client.post(f"/api/llm/context-packages/{body['id']}/review").status_code == 200
    return body


def _build_reviewed_player_safe_preview(
    client: TestClient,
    *,
    campaign_id: str,
    session_id: str,
    instruction: str = "Draft a player-safe recap from curated sources.",
    include_unshown_public_snippets: bool = False,
    excluded_source_refs: list[str] | None = None,
) -> dict[str, object]:
    preview = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={
            "session_id": session_id,
            "task_kind": "session.player_safe_recap",
            "visibility_mode": "public_safe",
            "gm_instruction": instruction,
            "include_unshown_public_snippets": include_unshown_public_snippets,
            "excluded_source_refs": excluded_source_refs or [],
        },
    )
    assert preview.status_code == 201
    body = preview.json()
    assert client.post(f"/api/llm/context-packages/{body['id']}/review").status_code == 200
    return body


def test_branch_proposals_marker_context_policy_and_player_boundary(migrated_settings, monkeypatch):
    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    client.post(
        f"/api/campaigns/{campaign_id}/scribe/transcript-events",
        json={"session_id": session_id, "body": "The party negotiated with Captain Varos at the bridge."},
    )
    player_before = client.get("/api/player-display").json()

    def fake_send_chat(profile, payload, *, timeout=60.0):  # noqa: ANN001, ARG001
        return json.dumps(_proposal_fixture(3)), {"usage": {"prompt_tokens": 120, "completion_tokens": 90}}

    provider_id = _fixture_provider(client, monkeypatch, fake_send_chat)
    preview_body = _build_reviewed_branch_preview(client, campaign_id=campaign_id, session_id=session_id)

    branch = client.post(
        f"/api/campaigns/{campaign_id}/llm/branch-directions/build",
        json={"provider_profile_id": provider_id, "context_package_id": preview_body["id"]},
    )
    assert branch.status_code == 200
    branch_body = branch.json()
    detail = branch_body["proposal_set"]
    assert detail["proposal_set"]["option_count"] == 3
    assert detail["proposal_set"]["degraded"] is False
    first, second, third = detail["options"]

    selected = client.post(f"/api/proposal-options/{first['id']}/select")
    assert selected.status_code == 200
    proposal_detail = client.get(f"/api/proposal-sets/{detail['proposal_set']['id']}").json()
    statuses = {option["id"]: option["status"] for option in proposal_detail["options"]}
    assert statuses[first["id"]] == "selected"
    assert statuses[second["id"]] == "superseded"
    assert statuses[third["id"]] == "superseded"

    selected_second = client.post(f"/api/proposal-options/{second['id']}/select")
    assert selected_second.status_code == 200
    proposal_detail = client.get(f"/api/proposal-sets/{detail['proposal_set']['id']}").json()
    statuses = {option["id"]: option["status"] for option in proposal_detail["options"]}
    assert statuses[first["id"]] == "selected"
    assert statuses[second["id"]] == "selected"
    assert statuses[third["id"]] == "superseded"

    preview_without_marker = _build_reviewed_branch_preview(
        client,
        campaign_id=campaign_id,
        session_id=session_id,
        instruction="Follow up on the selected draft without adopting it.",
    )
    assert "RAW PROPOSAL BODY 1" not in preview_without_marker["rendered_prompt"]
    assert first["planning_marker_text"] not in preview_without_marker["rendered_prompt"]

    marker = client.post(
        f"/api/proposal-options/{first['id']}/create-planning-marker",
        json={"title": "Varos political debt", "marker_text": first["planning_marker_text"]},
    )
    assert marker.status_code == 200
    marker_body = marker.json()
    marker_again = client.post(
        f"/api/proposal-options/{first['id']}/create-planning-marker",
        json={"title": "Varos political debt", "marker_text": first["planning_marker_text"]},
    )
    assert marker_again.status_code == 200
    assert marker_again.json()["id"] == marker_body["id"]

    preview_with_marker = _build_reviewed_branch_preview(
        client,
        campaign_id=campaign_id,
        session_id=session_id,
        instruction="Use active planning, but do not treat drafts as canon.",
    )
    assert "GM PLANNING CONTEXT, NOT PLAYED EVENTS" in preview_with_marker["rendered_prompt"]
    assert first["planning_marker_text"] in preview_with_marker["rendered_prompt"]
    assert "RAW PROPOSAL BODY 1" not in preview_with_marker["rendered_prompt"]
    marker_refs = [ref for ref in preview_with_marker["source_refs"] if ref["kind"] == "planning_marker"]
    assert marker_refs
    assert marker_refs[0]["lane"] == "planning"

    rejected = client.post(f"/api/proposal-options/{first['id']}/reject")
    saved = client.post(f"/api/proposal-options/{first['id']}/save-for-later")
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "active_marker_exists"
    assert saved.status_code == 409
    assert saved.json()["error"]["code"] == "active_marker_exists"

    expired = client.post(f"/api/planning-markers/{marker_body['id']}/expire")
    assert expired.status_code == 200
    time_expired_marker = client.post(
        f"/api/proposal-options/{second['id']}/create-planning-marker",
        json={
            "title": "Already expired branch",
            "marker_text": second["planning_marker_text"],
            "expires_at": "2000-01-01T00:00:00Z",
        },
    )
    assert time_expired_marker.status_code == 200
    preview_after_expire = _build_reviewed_branch_preview(
        client,
        campaign_id=campaign_id,
        session_id=session_id,
        instruction="The old marker should no longer shape context.",
    )
    assert first["planning_marker_text"] not in preview_after_expire["rendered_prompt"]
    assert second["planning_marker_text"] not in preview_after_expire["rendered_prompt"]

    player_after = client.get("/api/player-display").json()
    assert player_after == player_before
    connection = sqlite3.connect(migrated_settings.db_path)
    try:
        assert connection.execute("SELECT count(*) FROM campaign_memory_entries").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM session_recaps").fetchone()[0] == 0
    finally:
        connection.close()


def test_branch_repair_degraded_warnings_and_single_child_proposal_set(migrated_settings, monkeypatch):
    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    client.post(
        f"/api/campaigns/{campaign_id}/scribe/transcript-events",
        json={"session_id": session_id, "body": "The party asked Varos for alternate routes."},
    )
    calls = {"count": 0}

    def fake_send_chat(profile, payload, *, timeout=60.0):  # noqa: ANN001, ARG001
        calls["count"] += 1
        if calls["count"] == 1:
            return "not json", {"usage": {"prompt_tokens": 50, "completion_tokens": 5}}
        return (
            json.dumps(
                {
                    "title": "Repaired branch directions",
                    "proposalOptions": [
                        _proposal_fixture(1)["proposalOptions"][0],  # type: ignore[index]
                        {
                            "title": "Second direction",
                            "summary": "A second valid branch.",
                            "body": "RAW PROPOSAL BODY 2: a repaired valid option.",
                            "planningMarkerText": "GM is considering developing a second repaired branch.",
                        },
                        {"title": "Malformed only"},
                    ],
                }
            ),
            {"usage": {"prompt_tokens": 100, "completion_tokens": 60}},
        )

    provider_id = _fixture_provider(client, monkeypatch, fake_send_chat)
    preview_body = _build_reviewed_branch_preview(client, campaign_id=campaign_id, session_id=session_id)

    branch = client.post(
        f"/api/campaigns/{campaign_id}/llm/branch-directions/build",
        json={"provider_profile_id": provider_id, "context_package_id": preview_body["id"]},
    )
    assert branch.status_code == 200
    body = branch.json()
    assert body["run"]["task_kind"] == "scene.branch_directions.repair"
    assert body["proposal_set"]["proposal_set"]["option_count"] == 2
    assert body["proposal_set"]["proposal_set"]["degraded"] is True
    warning_codes = {warning["code"] for warning in body["warnings"]}
    assert {"degraded_option_count", "malformed_option_discarded"} <= warning_codes

    list_body = client.get(f"/api/campaigns/{campaign_id}/proposal-sets").json()
    assert len(list_body["proposal_sets"]) == 1
    summary = list_body["proposal_sets"][0]
    assert summary["degraded"] is True
    assert summary["has_warnings"] is True
    assert summary["repair_attempted"] is True

    connection = sqlite3.connect(migrated_settings.db_path)
    try:
        assert connection.execute("SELECT count(*) FROM proposal_sets").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM proposal_options").fetchone()[0] == 2
        rows = connection.execute(
            "SELECT task_kind, status, error_code, parent_run_id FROM llm_runs ORDER BY created_at, task_kind"
        ).fetchall()
    finally:
        connection.close()
    assert rows[0] == ("scene.branch_directions", "failed", "parse_failed", None)
    assert rows[1][0:3] == ("scene.branch_directions.repair", "succeeded", None)
    assert rows[1][3] is not None


def test_branch_repair_persistence_error_finalizes_child_run(migrated_settings, monkeypatch):
    from backend.app.api import routes_llm

    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    client.post(
        f"/api/campaigns/{campaign_id}/scribe/transcript-events",
        json={"session_id": session_id, "body": "The party asked Varos for alternate routes."},
    )
    calls = {"count": 0}

    def fake_send_chat(profile, payload, *, timeout=60.0):  # noqa: ANN001, ARG001
        calls["count"] += 1
        if calls["count"] == 1:
            return "not json", {"usage": {"prompt_tokens": 50, "completion_tokens": 5}}
        return json.dumps(_proposal_fixture(1)), {"usage": {"prompt_tokens": 100, "completion_tokens": 60}}

    def fake_persist(*args, **kwargs):  # noqa: ANN002, ANN003
        raise routes_llm.api_error(500, "persist_failed", "Proposal persistence failed")

    monkeypatch.setattr(routes_llm, "_persist_proposal_set", fake_persist)
    provider_id = _fixture_provider(client, monkeypatch, fake_send_chat)
    preview_body = _build_reviewed_branch_preview(client, campaign_id=campaign_id, session_id=session_id)

    branch = client.post(
        f"/api/campaigns/{campaign_id}/llm/branch-directions/build",
        json={"provider_profile_id": provider_id, "context_package_id": preview_body["id"]},
    )
    assert branch.status_code == 500
    assert branch.json()["error"]["code"] == "persist_failed"

    connection = sqlite3.connect(migrated_settings.db_path)
    try:
        assert connection.execute("SELECT count(*) FROM proposal_sets").fetchone()[0] == 0
        rows = connection.execute(
            "SELECT id, task_kind, status, error_code, parent_run_id FROM llm_runs ORDER BY created_at, task_kind"
        ).fetchall()
    finally:
        connection.close()
    parent_id = rows[0][0]
    assert rows[0][1:] == ("scene.branch_directions", "failed", "parse_failed", None)
    assert rows[1][1:] == ("scene.branch_directions.repair", "failed", "persist_failed", parent_id)


def test_planning_only_recap_candidate_is_rejected(migrated_settings, monkeypatch):
    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    scene = client.post(
        f"/api/campaigns/{campaign_id}/scenes",
        json={"title": "Bridge", "session_id": session_id},
    ).json()

    mode = {"task": "branch"}

    def fake_send_chat(profile, payload, *, timeout=60.0):  # noqa: ANN001, ARG001
        if mode["task"] == "branch":
            return json.dumps(_proposal_fixture(3)), {"usage": {"prompt_tokens": 120, "completion_tokens": 90}}
        content = "\n".join(message["content"] for message in payload["messages"])
        assert "GM PLANNING CONTEXT, NOT PLAYED EVENTS" in content
        return (
            json.dumps(
                {
                    "privateRecap": {"title": "Planning only", "bodyMarkdown": "A planning direction was considered."},
                    "memoryCandidateDrafts": [
                        {
                            "title": "Varos became a creditor",
                            "body": "Captain Varos became a political creditor.",
                            "claimStrength": "directly_evidenced",
                            "evidenceRefs": [
                                {
                                    "kind": "planning_marker",
                                    "id": mode["marker_id"],
                                    "quote": mode["marker_quote"],
                                }
                            ],
                        }
                    ],
                    "continuityWarnings": [],
                    "unresolvedThreads": [],
                }
            ),
            {"usage": {"prompt_tokens": 80, "completion_tokens": 40}},
        )

    provider_id = _fixture_provider(client, monkeypatch, fake_send_chat)
    preview_body = _build_reviewed_branch_preview(
        client,
        campaign_id=campaign_id,
        session_id=session_id,
        scene_id=scene["id"],
        scope_kind="scene",
    )
    branch = client.post(
        f"/api/campaigns/{campaign_id}/llm/branch-directions/build",
        json={"provider_profile_id": provider_id, "context_package_id": preview_body["id"]},
    ).json()
    option = branch["proposal_set"]["options"][0]
    marker = client.post(
        f"/api/proposal-options/{option['id']}/create-planning-marker",
        json={"title": "Varos political debt", "marker_text": option["planning_marker_text"]},
    ).json()
    mode["marker_id"] = marker["id"]
    mode["marker_quote"] = marker["marker_text"]
    mode["task"] = "recap"

    recap_preview = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={"session_id": session_id, "task_kind": "session.build_recap", "gm_instruction": "Do not canonize planning."},
    )
    assert recap_preview.status_code == 201
    recap_preview_body = recap_preview.json()
    assert marker["marker_text"] in recap_preview_body["rendered_prompt"]
    assert client.post(f"/api/llm/context-packages/{recap_preview_body['id']}/review").status_code == 200

    recap = client.post(
        f"/api/campaigns/{campaign_id}/llm/session-recap/build",
        json={"session_id": session_id, "provider_profile_id": provider_id, "context_package_id": recap_preview_body["id"]},
    )
    assert recap.status_code == 200
    body = recap.json()
    assert body["candidates"] == []
    assert "planning_evidence_cannot_create_memory" in body["rejected_drafts"][0]["errors"]


def test_linked_recap_candidate_accept_canonizes_marker_option_and_context(migrated_settings, monkeypatch):
    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    scene = client.post(
        f"/api/campaigns/{campaign_id}/scenes",
        json={"title": "Bridge", "session_id": session_id},
    ).json()

    mode: dict[str, object] = {"task": "branch"}

    def fake_send_chat(profile, payload, *, timeout=60.0):  # noqa: ANN001, ARG001
        if mode["task"] == "branch":
            return json.dumps(_proposal_fixture(3)), {"usage": {"prompt_tokens": 120, "completion_tokens": 90}}
        content = "\n".join(message["content"] for message in payload["messages"])
        assert f"relatedPlanningMarkerId: {mode['marker_id']}" in content
        assert "Planning marker/proposal text is provenance and context, never proof" in content
        return (
            json.dumps(
                {
                    "privateRecap": {"title": "Varos debt", "bodyMarkdown": "Captain Varos became the party's public creditor."},
                    "memoryCandidateDrafts": [
                        {
                            "title": "Varos became a public creditor",
                            "body": "Captain Varos became the party's public creditor after the bridge negotiation.",
                            "claimStrength": "directly_evidenced",
                            "relatedPlanningMarkerId": mode["marker_id"],
                            "evidenceRefs": [
                                {
                                    "kind": "session_transcript_event",
                                    "id": mode["event_id"],
                                    "quote": "Captain Varos became the party's public creditor after the bridge negotiation.",
                                }
                            ],
                        }
                    ],
                    "continuityWarnings": [],
                    "unresolvedThreads": [],
                }
            ),
            {"usage": {"prompt_tokens": 100, "completion_tokens": 60}},
        )

    provider_id = _fixture_provider(client, monkeypatch, fake_send_chat)
    branch_preview = _build_reviewed_branch_preview(
        client,
        campaign_id=campaign_id,
        session_id=session_id,
        scene_id=scene["id"],
        scope_kind="scene",
    )
    branch = client.post(
        f"/api/campaigns/{campaign_id}/llm/branch-directions/build",
        json={"provider_profile_id": provider_id, "context_package_id": branch_preview["id"]},
    ).json()
    option = branch["proposal_set"]["options"][1]
    marker = client.post(
        f"/api/proposal-options/{option['id']}/create-planning-marker",
        json={"title": "Varos public creditor", "marker_text": option["planning_marker_text"]},
    ).json()
    played = client.post(
        f"/api/campaigns/{campaign_id}/scribe/transcript-events",
        json={
            "session_id": session_id,
            "scene_id": scene["id"],
            "body": "Captain Varos became the party's public creditor after the bridge negotiation.",
        },
    ).json()
    mode.update({"task": "recap", "marker_id": marker["id"], "event_id": played["id"]})

    recap_preview = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={"session_id": session_id, "task_kind": "session.build_recap", "gm_instruction": "Extract confirmed played outcomes."},
    )
    assert recap_preview.status_code == 201
    recap_preview_body = recap_preview.json()
    assert marker["marker_text"] in recap_preview_body["rendered_prompt"]
    assert client.post(f"/api/llm/context-packages/{recap_preview_body['id']}/review").status_code == 200

    recap = client.post(
        f"/api/campaigns/{campaign_id}/llm/session-recap/build",
        json={"session_id": session_id, "provider_profile_id": provider_id, "context_package_id": recap_preview_body["id"]},
    )
    assert recap.status_code == 200
    candidate = recap.json()["candidates"][0]
    assert candidate["source_planning_marker_id"] == marker["id"]
    assert candidate["source_proposal_option_id"] == option["id"]
    assert candidate["normalization_warnings"] == []

    accepted = client.post(f"/api/scribe/memory-candidates/{candidate['id']}/accept")
    accepted_again = client.post(f"/api/scribe/memory-candidates/{candidate['id']}/accept")
    assert accepted.status_code == 200
    assert accepted_again.status_code == 200
    entry = accepted.json()
    assert entry["id"] == accepted_again.json()["id"]
    assert entry["source_planning_marker_id"] == marker["id"]
    assert entry["source_proposal_option_id"] == option["id"]

    with sqlite3.connect(migrated_settings.db_path) as connection:
        marker_row = connection.execute(
            "SELECT status, canon_memory_entry_id FROM planning_markers WHERE id = ?",
            (marker["id"],),
        ).fetchone()
        option_row = connection.execute("SELECT status FROM proposal_options WHERE id = ?", (option["id"],)).fetchone()
        search_count = connection.execute(
            "SELECT count(*) FROM scribe_search_index WHERE source_kind = 'campaign_memory_entry' AND source_id = ?",
            (entry["id"],),
        ).fetchone()[0]
    assert marker_row == ("canonized", entry["id"])
    assert option_row == ("canonized",)
    assert search_count == 1

    future_preview = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={"session_id": session_id, "task_kind": "session.build_recap", "gm_instruction": "Use canon, not old planning."},
    )
    assert future_preview.status_code == 201
    rendered = future_preview.json()["rendered_prompt"]
    assert marker["marker_text"] not in rendered
    assert "Captain Varos became the party's public creditor" in rendered

    recall = client.post(f"/api/campaigns/{campaign_id}/scribe/recall", json={"query": "public creditor"})
    assert recall.status_code == 200
    assert recall.json()["hits"][0]["source_kind"] == "campaign_memory_entry"


def test_invalid_related_marker_link_drops_to_unlinked_candidate_with_warning(migrated_settings, monkeypatch):
    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    event = client.post(
        f"/api/campaigns/{campaign_id}/scribe/transcript-events",
        json={"session_id": session_id, "body": "Mira burned the false writ in front of the council."},
    ).json()

    def fake_send_chat(profile, payload, *, timeout=60.0):  # noqa: ANN001, ARG001
        return (
            json.dumps(
                {
                    "privateRecap": {"title": "False writ", "bodyMarkdown": "Mira burned the false writ."},
                    "memoryCandidateDrafts": [
                        {
                            "title": "Mira burned the false writ",
                            "body": "Mira burned the false writ in front of the council.",
                            "claimStrength": "directly_evidenced",
                            "relatedPlanningMarkerId": "not-in-reviewed-context",
                            "evidenceRefs": [
                                {
                                    "kind": "session_transcript_event",
                                    "id": event["id"],
                                    "quote": "Mira burned the false writ in front of the council.",
                                }
                            ],
                        }
                    ],
                    "continuityWarnings": [],
                    "unresolvedThreads": [],
                }
            ),
            {"usage": {"prompt_tokens": 80, "completion_tokens": 40}},
        )

    provider_id = _fixture_provider(client, monkeypatch, fake_send_chat)
    preview = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={"session_id": session_id, "task_kind": "session.build_recap", "gm_instruction": "Keep useful played facts."},
    ).json()
    assert client.post(f"/api/llm/context-packages/{preview['id']}/review").status_code == 200
    recap = client.post(
        f"/api/campaigns/{campaign_id}/llm/session-recap/build",
        json={"session_id": session_id, "provider_profile_id": provider_id, "context_package_id": preview["id"]},
    )
    assert recap.status_code == 200
    candidate = recap.json()["candidates"][0]
    assert candidate["source_planning_marker_id"] is None
    assert "planning_marker_link_ignored" in candidate["normalization_warnings"]

    accepted = client.post(f"/api/scribe/memory-candidates/{candidate['id']}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["source_planning_marker_id"] is None


def test_edited_linked_candidate_requires_confirmation_and_expired_marker_blocks_accept(migrated_settings, monkeypatch):
    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    mode: dict[str, object] = {"task": "branch"}

    def fake_send_chat(profile, payload, *, timeout=60.0):  # noqa: ANN001, ARG001
        if mode["task"] == "branch":
            return json.dumps(_proposal_fixture(1)), {"usage": {"prompt_tokens": 120, "completion_tokens": 90}}
        return (
            json.dumps(
                {
                    "privateRecap": {"title": "Varos debt", "bodyMarkdown": "Varos claimed a debt."},
                    "memoryCandidateDrafts": [
                        {
                            "title": "Varos claimed a debt",
                            "body": "Varos claimed a debt after the council vote.",
                            "claimStrength": "directly_evidenced",
                            "relatedPlanningMarkerId": mode["marker_id"],
                            "evidenceRefs": [
                                {
                                    "kind": "session_transcript_event",
                                    "id": mode["event_id"],
                                    "quote": "Varos claimed a debt after the council vote.",
                                }
                            ],
                        }
                    ],
                    "continuityWarnings": [],
                    "unresolvedThreads": [],
                }
            ),
            {"usage": {"prompt_tokens": 100, "completion_tokens": 60}},
        )

    provider_id = _fixture_provider(client, monkeypatch, fake_send_chat)
    branch_preview = _build_reviewed_branch_preview(client, campaign_id=campaign_id, session_id=session_id)
    branch = client.post(
        f"/api/campaigns/{campaign_id}/llm/branch-directions/build",
        json={"provider_profile_id": provider_id, "context_package_id": branch_preview["id"]},
    ).json()
    option = branch["proposal_set"]["options"][0]
    marker = client.post(
        f"/api/proposal-options/{option['id']}/create-planning-marker",
        json={"title": "Varos debt", "marker_text": option["planning_marker_text"]},
    ).json()
    event = client.post(
        f"/api/campaigns/{campaign_id}/scribe/transcript-events",
        json={"session_id": session_id, "body": "Varos claimed a debt after the council vote."},
    ).json()
    mode.update({"task": "recap", "marker_id": marker["id"], "event_id": event["id"]})

    preview = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={"session_id": session_id, "task_kind": "session.build_recap", "gm_instruction": "Extract confirmed outcomes."},
    ).json()
    assert client.post(f"/api/llm/context-packages/{preview['id']}/review").status_code == 200
    recap = client.post(
        f"/api/campaigns/{campaign_id}/llm/session-recap/build",
        json={"session_id": session_id, "provider_profile_id": provider_id, "context_package_id": preview["id"]},
    ).json()
    candidate = recap["candidates"][0]

    edited = client.patch(
        f"/api/scribe/memory-candidates/{candidate['id']}",
        json={"body": "Varos claimed a debt, and the GM reviewed the wording."},
    )
    assert edited.status_code == 200
    missing_confirm = client.post(f"/api/scribe/memory-candidates/{candidate['id']}/accept")
    assert missing_confirm.status_code == 409
    assert missing_confirm.json()["error"]["code"] == "linked_marker_confirmation_required"

    expired = client.post(f"/api/planning-markers/{marker['id']}/expire")
    assert expired.status_code == 200
    with_confirm_after_expire = client.post(
        f"/api/scribe/memory-candidates/{candidate['id']}/accept",
        json={"confirm_linked_marker_canonization": True},
    )
    assert with_confirm_after_expire.status_code == 409
    assert with_confirm_after_expire.json()["error"]["code"] == "related_marker_not_active"
    with sqlite3.connect(migrated_settings.db_path) as connection:
        option_status = connection.execute("SELECT status FROM proposal_options WHERE id = ?", (option["id"],)).fetchone()[0]
    assert option_status != "canonized"


def test_player_safe_context_excludes_private_sources_and_stales_on_curation_change(migrated_settings, monkeypatch):
    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    private_recap_phrase = "PRIVATE_RECAP_PHRASE_DO_NOT_PROMPT"
    safe_recap_phrase = "The party publicly repaired the moon gate."
    private_memory_phrase = "PRIVATE_MEMORY_PHRASE_DO_NOT_PROMPT"
    planning_phrase = "PRIVATE_PLANNING_MARKER_DO_NOT_PROMPT"
    proposal_phrase = "PRIVATE_PROPOSAL_BODY_DO_NOT_PROMPT"
    live_phrase = "PRIVATE_LIVE_CAPTURE_DO_NOT_PROMPT"
    unshown_snippet_phrase = "UNSHOWN_MANUAL_SNIPPET_DO_NOT_PROMPT"
    shown_snippet_phrase = "Shown public clue about the moon gate."

    client.post(f"/api/campaigns/{campaign_id}/scribe/transcript-events", json={"session_id": session_id, "body": live_phrase})
    private_recap = client.post(
        f"/api/campaigns/{campaign_id}/scribe/session-recaps",
        json={"session_id": session_id, "title": "Private recap", "body_markdown": private_recap_phrase},
    ).json()
    safe_recap = client.post(
        f"/api/campaigns/{campaign_id}/scribe/session-recaps",
        json={"session_id": session_id, "title": "Safe recap", "body_markdown": safe_recap_phrase},
    ).json()
    public_toggle = client.patch(
        f"/api/scribe/session-recaps/{safe_recap['id']}/public-safety",
        json={"campaign_id": campaign_id, "public_safe": True, "sensitivity_reason": None},
    )
    assert public_toggle.status_code == 200

    now = "2026-05-04T12:00:00Z"
    with sqlite3.connect(migrated_settings.db_path) as connection:
        connection.execute(
            """
            INSERT INTO campaign_memory_entries
                (id, campaign_id, session_id, source_candidate_id, title, body, evidence_refs_json, tags_json, public_safe, sensitivity_reason, created_at, updated_at)
            VALUES (?, ?, ?, NULL, ?, ?, '[]', '[]', 0, 'private_note', ?, ?)
            """,
            ("private-memory-1", campaign_id, session_id, "Private memory", private_memory_phrase, now, now),
        )
        connection.execute(
            """
            INSERT INTO proposal_sets
                (id, campaign_id, session_id, scene_id, llm_run_id, context_package_id, task_kind, scope_kind, title, status, normalization_warnings_json, created_at, updated_at)
            VALUES ('proposal-set-private', ?, ?, NULL, NULL, NULL, 'scene.branch_directions', 'session', 'Private proposal set', 'proposed', '[]', ?, ?)
            """,
            (campaign_id, session_id, now, now),
        )
        connection.execute(
            """
            INSERT INTO proposal_options
                (id, proposal_set_id, stable_option_key, title, summary, body, consequences, reveals, stays_hidden, proposed_delta_json, planning_marker_text, status, selected_at, canonized_at, created_at, updated_at)
            VALUES ('proposal-option-private', 'proposal-set-private', 'private', 'Private option', 'Private', ?, '', '', '', '{}', 'GM is considering a private option.', 'selected', ?, NULL, ?, ?)
            """,
            (proposal_phrase, now, now, now),
        )
        connection.execute(
            """
            INSERT INTO planning_markers
                (id, campaign_id, session_id, scene_id, source_proposal_option_id, scope_kind, status, title, marker_text, original_marker_text, lint_warnings_json, provenance_json, edited_at, edited_from_source, expires_at, created_at, updated_at)
            VALUES ('planning-marker-private', ?, ?, NULL, 'proposal-option-private', 'session', 'active', 'Private plan', ?, NULL, '[]', '{}', NULL, 0, NULL, ?, ?)
            """,
            (campaign_id, session_id, planning_phrase, now, now),
        )

    unshown = client.post(
        f"/api/campaigns/{campaign_id}/public-snippets",
        json={"title": "Unshown artifact", "body": unshown_snippet_phrase, "format": "markdown"},
    )
    shown = client.post(
        f"/api/campaigns/{campaign_id}/public-snippets",
        json={"title": "Shown artifact", "body": shown_snippet_phrase, "format": "markdown"},
    )
    assert unshown.status_code == 201
    assert shown.status_code == 201
    assert client.post("/api/player-display/show-snippet", json={"snippet_id": shown.json()["id"]}).status_code == 200
    player_before = client.get("/api/player-display").json()

    preview = _build_reviewed_player_safe_preview(client, campaign_id=campaign_id, session_id=session_id)
    rendered = preview["rendered_prompt"]
    assert safe_recap_phrase in rendered
    assert shown_snippet_phrase in rendered
    assert private_recap_phrase not in rendered
    assert private_memory_phrase not in rendered
    assert planning_phrase not in rendered
    assert proposal_phrase not in rendered
    assert live_phrase not in rendered
    assert unshown_snippet_phrase not in rendered
    assert "public_snippet" in preview["source_classes"]

    def fake_send_chat(profile, payload, *, timeout=60.0):  # noqa: ANN001, ARG001
        return json.dumps({"publicSnippetDraft": {"title": "Safe", "bodyMarkdown": "Safe public draft."}}), {}

    provider_id = _fixture_provider(client, monkeypatch, fake_send_chat)
    changed = client.patch(
        f"/api/scribe/session-recaps/{safe_recap['id']}/public-safety",
        json={"campaign_id": campaign_id, "public_safe": False, "sensitivity_reason": "private_note"},
    )
    assert changed.status_code == 200
    stale = client.post(
        f"/api/campaigns/{campaign_id}/llm/player-safe-recap/build",
        json={"session_id": session_id, "provider_profile_id": provider_id, "context_package_id": preview["id"]},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "context_preview_stale"
    assert client.get("/api/player-display").json() == player_before
    assert private_recap["public_safe"] is False


def test_player_safe_run_warning_gate_snippet_creation_and_player_serializer(migrated_settings, monkeypatch):
    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    recap = client.post(
        f"/api/campaigns/{campaign_id}/scribe/session-recaps",
        json={"session_id": session_id, "title": "Public moon gate", "body_markdown": "The party repaired the moon gate in public."},
    ).json()
    assert client.patch(
        f"/api/scribe/session-recaps/{recap['id']}/public-safety",
        json={"campaign_id": campaign_id, "public_safe": True, "sensitivity_reason": None},
    ).status_code == 200
    player_before = client.get("/api/player-display").json()

    def fake_send_chat(profile, payload, *, timeout=60.0):  # noqa: ANN001, ARG001
        return (
            json.dumps({"publicSnippetDraft": {"title": "Moon Gate", "bodyMarkdown": "The party repaired the moon gate."}}),
            {"usage": {"prompt_tokens": 80, "completion_tokens": 20}},
        )

    provider_id = _fixture_provider(client, monkeypatch, fake_send_chat)
    preview = _build_reviewed_player_safe_preview(client, campaign_id=campaign_id, session_id=session_id)
    run = client.post(
        f"/api/campaigns/{campaign_id}/llm/player-safe-recap/build",
        json={"session_id": session_id, "provider_profile_id": provider_id, "context_package_id": preview["id"]},
    )
    assert run.status_code == 200
    run_body = run.json()
    assert run_body["public_snippet_draft"]["title"] == "Moon Gate"
    assert client.get("/api/player-display").json() == player_before
    with sqlite3.connect(migrated_settings.db_path) as connection:
        assert connection.execute("SELECT count(*) FROM public_snippets").fetchone()[0] == 0

    edited_body = "The party repaired the moon gate. Unknown to the party, this is still risky phrasing."
    scan = client.post(
        f"/api/campaigns/{campaign_id}/scribe/public-safety-warnings",
        json={"title": "Moon Gate", "body_markdown": edited_body},
    )
    assert scan.status_code == 200
    scan_body = scan.json()
    assert scan_body["ack_required"] is True
    assert any(warning["code"] == "unknown_to_party" for warning in scan_body["warnings"])

    invalid_manual = client.post(
        f"/api/campaigns/{campaign_id}/public-snippets",
        json={
            "title": "Bad provenance",
            "body": edited_body,
            "format": "markdown",
            "creation_source": "manual",
            "source_llm_run_id": run_body["run"]["id"],
        },
    )
    assert invalid_manual.status_code == 400
    assert invalid_manual.json()["error"]["code"] == "invalid_snippet_creation_source"

    without_ack = client.post(
        f"/api/campaigns/{campaign_id}/public-snippets",
        json={
            "title": "Moon Gate",
            "body": edited_body,
            "format": "markdown",
            "creation_source": "llm_scribe",
            "source_llm_run_id": run_body["run"]["id"],
            "source_draft_hash": run_body["source_draft_hash"],
            "warning_content_hash": scan_body["content_hash"],
        },
    )
    assert without_ack.status_code == 409
    assert without_ack.json()["error"]["code"] == "public_safety_ack_required"

    edited_with_markup = "# Big\n<script>alert(1)</script>\n![secret](http://image)\n[link](https://example.com)\n" + edited_body
    stale_scan_create = client.post(
        f"/api/campaigns/{campaign_id}/public-snippets",
        json={
            "title": "Moon Gate",
            "body": edited_with_markup,
            "format": "markdown",
            "creation_source": "llm_scribe",
            "source_llm_run_id": run_body["run"]["id"],
            "source_draft_hash": run_body["source_draft_hash"],
            "warning_content_hash": scan_body["content_hash"],
            "warning_ack_content_hash": scan_body["content_hash"],
        },
    )
    assert stale_scan_create.status_code == 409
    assert stale_scan_create.json()["error"]["code"] == "public_safety_scan_stale"

    rescanned = client.post(
        f"/api/campaigns/{campaign_id}/scribe/public-safety-warnings",
        json={"title": "Moon Gate", "body_markdown": edited_with_markup},
    ).json()
    created = client.post(
        f"/api/campaigns/{campaign_id}/public-snippets",
        json={
            "title": "Moon Gate",
            "body": edited_with_markup,
            "format": "markdown",
            "creation_source": "llm_scribe",
            "source_llm_run_id": run_body["run"]["id"],
            "source_draft_hash": run_body["source_draft_hash"],
            "warning_content_hash": rescanned["content_hash"],
            "warning_ack_content_hash": rescanned["content_hash"],
        },
    )
    assert created.status_code == 201
    created_body = created.json()
    assert created_body["creation_source"] == "llm_scribe"
    assert created_body["source_llm_run_id"] == run_body["run"]["id"]
    assert created_body["safety_warnings"]
    assert "matched_text" not in created_body["safety_warnings"][0]
    assert client.get("/api/player-display").json() == player_before

    export = client.post("/api/storage/export")
    assert export.status_code == 200
    archive_path = migrated_settings.export_dir / export.json()["archive_name"]
    with tarfile.open(archive_path, "r:gz") as archive:
        db_bytes = archive.extractfile(DB_ARCHIVE_PATH).read()  # type: ignore[union-attr]
    snapshot = migrated_settings.export_dir / "player-safe-snippet-export.sqlite3"
    snapshot.write_bytes(db_bytes)
    with sqlite3.connect(snapshot) as connection:
        exported = connection.execute(
            "SELECT creation_source, source_llm_run_id, source_draft_hash, safety_warnings_json FROM public_snippets WHERE id = ?",
            (created_body["id"],),
        ).fetchone()
    assert exported == ("manual", None, None, "[]")

    shown = client.post("/api/player-display/show-snippet", json={"snippet_id": created_body["id"]})
    assert shown.status_code == 200
    payload = shown.json()["payload"]
    assert payload["type"] == "public_snippet"
    assert "creation_source" not in payload
    assert "source_llm_run_id" not in payload
    assert "safety_warnings" not in payload
    assert "<script>" not in payload["body"]
    assert "http://image" not in payload["body"]
    assert "https://example.com" not in payload["body"]
    snippet_after_publish = client.get(f"/api/campaigns/{campaign_id}/public-snippets").json()["snippets"][0]
    assert snippet_after_publish["last_published_at"] is not None
    assert snippet_after_publish["publication_count"] == 1


def test_player_safe_empty_context_instruction_only_gate(migrated_settings):
    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    weak = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={"session_id": session_id, "task_kind": "session.player_safe_recap", "visibility_mode": "public_safe", "gm_instruction": "recap pls"},
    )
    strong = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={
            "session_id": session_id,
            "task_kind": "session.player_safe_recap",
            "visibility_mode": "public_safe",
            "gm_instruction": "Write a short player-facing reminder that the party rested at camp and saw dawn break.",
        },
    )
    assert weak.status_code == 400
    assert weak.json()["error"]["code"] == "public_safe_context_empty"
    assert strong.status_code == 201
    assert strong.json()["warnings"][0]["code"] == "instruction_only_public_safe_draft"


def test_public_safety_patch_requires_matching_campaign(migrated_settings):
    client = _client(migrated_settings)
    campaign_a, session_a = _campaign_session(client)
    campaign_b, _session_b = _campaign_session(client)
    recap = client.post(
        f"/api/campaigns/{campaign_a}/scribe/session-recaps",
        json={"session_id": session_a, "title": "Private recap", "body_markdown": "Private body"},
    ).json()
    rejected = client.patch(
        f"/api/scribe/session-recaps/{recap['id']}/public-safety",
        json={"campaign_id": campaign_b, "public_safe": True, "sensitivity_reason": None},
    )
    assert rejected.status_code == 404
    recaps = client.get(f"/api/campaigns/{campaign_a}/scribe/session-recaps?session_id={session_a}").json()["recaps"]
    assert recaps[0]["public_safe"] is False


def test_public_safety_patch_requires_ack_for_risky_source_text(migrated_settings):
    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    recap = client.post(
        f"/api/campaigns/{campaign_id}/scribe/session-recaps",
        json={"session_id": session_id, "title": "Mira's private turn", "body_markdown": "Mira secretly plans to betray the party."},
    ).json()

    rejected = client.patch(
        f"/api/scribe/session-recaps/{recap['id']}/public-safety",
        json={"campaign_id": campaign_id, "public_safe": True, "sensitivity_reason": None},
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "public_safety_ack_required"
    detail = rejected.json()["error"]["details"][0]
    assert detail["ack_required"] is True
    assert any(warning["code"] == "secret_language" for warning in detail["warnings"])
    recaps = client.get(f"/api/campaigns/{campaign_id}/scribe/session-recaps?session_id={session_id}").json()["recaps"]
    assert recaps[0]["public_safe"] is False

    accepted = client.patch(
        f"/api/scribe/session-recaps/{recap['id']}/public-safety",
        json={
            "campaign_id": campaign_id,
            "public_safe": True,
            "sensitivity_reason": None,
            "warning_content_hash": detail["content_hash"],
            "warning_ack_content_hash": detail["content_hash"],
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["public_safe"] is True


def test_player_safe_preview_reports_source_limit_overflow(migrated_settings):
    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    now = "2026-05-04T12:00:00Z"
    with sqlite3.connect(migrated_settings.db_path) as connection:
        for index in range(12):
            connection.execute(
                """
                INSERT INTO campaign_memory_entries
                    (id, campaign_id, session_id, source_candidate_id, title, body, evidence_refs_json, tags_json, public_safe, sensitivity_reason, created_at, updated_at)
                VALUES (?, ?, ?, NULL, ?, ?, '[]', '[]', 1, NULL, ?, ?)
                """,
                (
                    f"public-memory-{index}",
                    campaign_id,
                    session_id,
                    f"Public memory {index}",
                    f"Public-safe memory body {index}.",
                    now,
                    now,
                ),
            )

    preview = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={
            "session_id": session_id,
            "task_kind": "session.player_safe_recap",
            "visibility_mode": "public_safe",
            "gm_instruction": "Draft a concise player-safe recap from curated public-safe memory.",
        },
    )
    assert preview.status_code == 201
    body = preview.json()
    assert len([ref for ref in body["source_refs"] if ref["kind"] == "campaign_memory_entry"]) == 10
    overflow = [warning for warning in body["warnings"] if warning["code"] == "public_safe_source_limit"]
    assert overflow
    assert overflow[0]["sourceClass"] == "memory_entry"
    assert overflow[0]["included"] == 10
    assert overflow[0]["totalEligible"] == 12


def test_branch_scope_validation_and_campaign_focus_warning(migrated_settings):
    client = _client(migrated_settings)
    campaign_id, session_id = _campaign_session(client)
    scene = client.post(
        f"/api/campaigns/{campaign_id}/scenes",
        json={"title": "Bridge", "session_id": session_id},
    )
    assert scene.status_code == 201
    missing_session = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={"task_kind": "scene.branch_directions", "scope_kind": "session", "gm_instruction": "Need session."},
    )
    missing_scene = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={"task_kind": "scene.branch_directions", "scope_kind": "scene", "gm_instruction": "Need scene."},
    )
    campaign_preview = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={"task_kind": "scene.branch_directions", "scope_kind": "campaign", "gm_instruction": "ideas pls"},
    )
    scene_preview = client.post(
        f"/api/campaigns/{campaign_id}/llm/context-preview",
        json={
            "task_kind": "scene.branch_directions",
            "scope_kind": "scene",
            "scene_id": scene.json()["id"],
            "gm_instruction": "Make the bridge negotiation tense.",
        },
    )

    assert missing_session.status_code == 400
    assert missing_session.json()["error"]["code"] == "missing_session_scope"
    assert missing_scene.status_code == 400
    assert missing_scene.json()["error"]["code"] == "missing_scene_scope"
    assert campaign_preview.status_code == 201
    assert campaign_preview.json()["warnings"][0]["code"] == "campaign_scope_needs_focus"
    assert scene_preview.status_code == 201
    assert scene_preview.json()["scope_kind"] == "scene"
    assert "scene" in scene_preview.json()["source_classes"]
