"""Compatibility and update checks protect real state independently of the UI."""
import asyncio
import json
from pathlib import Path

import pytest
from tests.local_client import TestClient

import app
import instance_lock
import maintenance
import sync_storage as storage


def sample(word_id="law", created_at="2026-10-18T09:00:00+08:00", **extra):
    return {"id": word_id, "word": word_id, "definition": "n. 法律", "phonetic": "",
            "example": "The law applies.", "created_at": created_at, "notebook_id": "default", **extra}


def protected_project(root):
    data_file, config_file, secrets = root / "words.json", root / "config.json", root / ".secrets"
    secrets.mkdir()
    config_file.write_text('{"provider":"deepseek","srs":{"daily_new_limit":10}}')
    (secrets / "deepseek.json").write_text('{"api_key":"private-key","model":"deepseek-flash"}')
    (secrets / "sync-settings.json").write_text('{"folder_path":"private-drive-folder","enabled":true}')
    (secrets / "token.json").write_text('{"refresh_token":"private-drive-token"}')
    storage.commit(data_file, {"words": [sample(review_history=[{"id": "review-1", "rating": 3, "at": "2026-10-18T10:00:00+08:00"}])]})
    return data_file, config_file, secrets


def test_update_snapshot_preserves_reviews_and_secrets_without_exposing_them(tmp_path):
    data, config, secrets = protected_project(tmp_path)
    original = data.read_bytes()
    backup = maintenance.create_backup(data, config, secrets, tmp_path / ".backups", "previous-revision")
    result = maintenance.verify_backup(backup)
    assert result["words"] == 1 and result["review_events"] == 1 and result["scheduled_words"] == 1
    assert "private-key" not in json.dumps(result)
    manifest = json.loads((backup / "manifest.json").read_text())
    assert manifest["revision"] == "previous-revision"
    assert len(manifest["files"]) == 5
    assert data.read_bytes() == original
    for entry in manifest["files"]:
        assert Path(entry["source"]).read_bytes() == (backup / entry["copy"]).read_bytes()


@pytest.mark.parametrize("removed", ["words.json", "config.json", ".secrets/deepseek.json", ".secrets/sync-settings.json"])
def test_update_verification_fails_on_any_lost_state(tmp_path, removed):
    data, config, secrets = protected_project(tmp_path)
    backup = maintenance.create_backup(data, config, secrets, tmp_path / ".backups")
    (tmp_path / removed).unlink()
    with pytest.raises(RuntimeError, match="不一致"):
        maintenance.verify_backup(backup)
    assert not (tmp_path / removed).exists()  # never silently restore over newer data


def test_snapshot_requires_app_to_be_stopped(tmp_path):
    data, config, secrets = protected_project(tmp_path)
    with instance_lock.acquire(data):
        with pytest.raises(RuntimeError, match="另一个"):
            maintenance.create_backup(data, config, secrets, tmp_path / ".backups")
    assert not (tmp_path / ".backups").exists()


def test_future_data_version_cannot_be_overwritten_by_old_app(tmp_path):
    path = tmp_path / "words.json"
    data = storage.commit(path, {"words": [sample()]})
    data["_sync"]["version"] = 999
    storage.atomic_write(path, data)
    original = path.read_bytes()
    with pytest.raises(ValueError, match="版本"):
        storage.read(path)
    with pytest.raises(ValueError):
        storage.commit(path, {"words": []})
    assert path.read_bytes() == original


def test_backup_and_legacy_upgrade_keep_existing_schedule(tmp_path):
    path, config_file, secrets = protected_project(tmp_path)
    state = storage.read(path)["words"][0]["srs"]
    legacy = {"words": [sample(srs=state)]}
    path.write_text(json.dumps(legacy))
    backup = maintenance.create_backup(path, config_file, secrets, tmp_path / ".backups")
    maintenance.verify_backup(backup)
    migrated = storage.read(path)
    assert migrated["words"][0]["srs"] == state
    assert json.loads(path.with_suffix(".json.legacy.bak").read_text()) == legacy
    assert len(migrated["notebooks"]) == 1


def test_time_sorting_respects_timezones_pagination_and_exports(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DATA_FILE", tmp_path / "words.json")
    app.save_words({"words": [sample("older", "2026-10-18T09:00:00+08:00"),
                              sample("newest", "2026-10-18T03:00:00+00:00"),
                              sample("middle", "2026-10-18T10:00:00+08:00")]})
    original = app.DATA_FILE.read_bytes()
    client = TestClient(app.app)
    result = client.get("/api/words", params={"sort": "created_desc", "size": 2}).json()
    assert [word["id"] for word in result["words"]] == ["newest", "middle"]
    next_page = client.get("/api/words", params={"sort": "created_desc", "size": 2, "page": 2}).json()
    assert next_page["words"][0]["id"] == "older"
    export = client.get("/api/words/export", params={"sort": "created_desc"}).json()
    assert [word["id"] for word in export["words"]] == ["newest", "middle", "older"]
    oldest = client.get("/api/words", params={"sort": "created_asc"}).json()
    assert [word["id"] for word in oldest["words"]] == ["older", "middle", "newest"]
    assert app.DATA_FILE.read_bytes() == original  # sorting never rewrites persisted state


def test_new_word_immediate_definition_and_missing_key_status(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DATA_FILE", tmp_path / "words.json")
    monkeypatch.setattr(app.config, "get_ai_settings", lambda: {"configured": False})
    monkeypatch.setattr(app, "_enrich_jobs", {})
    client = TestClient(app.app)
    manual = client.post("/api/words", json={"word": "contract", "definition": "n. 合同"}).json()
    assert manual["word"]["definition"] == "n. 合同" and manual["enrichment"]["status"] == "ready"
    pending = client.post("/api/words", json={"word": "consideration"}).json()
    assert pending["enrichment"]["status"] == "not_configured"
    retried = client.post(f"/api/words/{pending['word']['id']}/enrich").json()
    assert retried["enrichment"]["status"] == "not_configured"
    assert len(app.load_words()["words"]) == 2


def test_worker_result_is_available_without_sse_and_retry_is_deduplicated(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DATA_FILE", tmp_path / "words.json")
    monkeypatch.setattr(app, "_enrich_jobs", {})
    monkeypatch.setattr(app, "_enriching_ids", {})
    monkeypatch.setattr(app.config, "get_ai_settings", lambda: {"configured": True})
    calls = []
    async def fake_enrich(word, context):
        calls.append(word)
        return "/test/", "n. 合同", "The contract is valid."
    monkeypatch.setattr(app, "enrich_word", fake_enrich)
    monkeypatch.setattr(app, "_enrich_post_check", lambda *args: (True, ""))

    async def scenario():
        monkeypatch.setattr(app, "_enrich_queue", asyncio.Queue())
        monkeypatch.setattr(app, "_event_queue", asyncio.Queue())
        created = await app.create_word({"word": "contract"})
        word_id = created["word"]["id"]
        assert created["enrichment"]["status"] == "queued"
        await app.retry_word_enrichment(word_id)
        assert app._enrich_queue.qsize() == 1
        worker = asyncio.create_task(app._enrich_worker())
        try:
            await asyncio.wait_for(app._enrich_queue.join(), timeout=2)
            fetched = app.get_word(word_id)
            assert fetched["enrichment"]["status"] == "ready"
            assert fetched["word"]["definition"] == "n. 合同"
            await app.retry_word_enrichment(word_id)
            assert app._enrich_queue.qsize() == 0 and calls == ["Contract"]
        finally:
            worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await worker
    asyncio.run(scenario())
