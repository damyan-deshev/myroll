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
