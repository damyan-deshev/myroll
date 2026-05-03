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
