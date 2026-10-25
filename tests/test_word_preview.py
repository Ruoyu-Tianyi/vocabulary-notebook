"""New-word previews use isolated data and mocked enrichment."""
import asyncio

import pytest
from tests.local_client import TestClient

import app


@pytest.fixture(autouse=True)
def queue_loop():
    # Python 3.9 queues bind eagerly; asyncio.run in another test clears its loop.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def word(word_id, created_at, **extra):
    return {"notebook_id": "default", "id": word_id, "word": word_id, "definition": "n. 测试", "phonetic": "",
            "example": "This is a test.", "created_at": created_at, **extra}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DATA_FILE", tmp_path / "words.json")
    monkeypatch.setattr(app, "_enrich_states", {})
    monkeypatch.setattr(app, "_new_enrichment_candidates", {})
    monkeypatch.setattr(app, "_enriching_ids", {})
    monkeypatch.setattr(app, "_enrich_current", None)
    monkeypatch.setattr(app, "_enrich_batch_total", 0)
    monkeypatch.setattr(app, "_enrich_batch_done", 0)
    return app.DATA_FILE








@pytest.mark.parametrize("outcome", ["success", "empty", "rejected"])
def test_preview_status_and_persisted_result_survive_missed_sse(isolated, monkeypatch, outcome):
    async def enrich(_word, context=""):
        if outcome == "empty":
            return "", "", ""
        return "/test/", "n. 合同", "The contract is valid."

    monkeypatch.setattr(app, "enrich_word", enrich)
    monkeypatch.setattr(app, "_enrich_post_check", lambda *args: (outcome != "rejected", "测试校验失败"))

    async def scenario():
        monkeypatch.setattr(app, "_enrich_queue", asyncio.Queue())
        monkeypatch.setattr(app, "_event_queue", asyncio.Queue())
        created = await app.create_word({"word": "contract"})
        word_id = created["word"]["id"]
        assert created["enrichment"]["status"] == "queued"
        worker = asyncio.create_task(app._enrich_worker())
        try:
            await asyncio.wait_for(app._enrich_queue.join(), timeout=2)
            if outcome == "empty":
                assert not app.load_words()["words"]
                assert app._enrich_states[word_id]["status"] == "removed"
                assert app._event_queue.get_nowait()["removed"] is True
                return
            result = app.get_word(word_id)  # No SSE consumer is required for the preview.
            if outcome == "success":
                assert result["enrichment"]["status"] == "ready"
                assert result["word"]["definition"] == "n. 合同"
                assert result["word"]["example"] == "The contract is valid."
            else:
                assert result["enrichment"]["status"] == "failed"
                assert result["enrichment"]["error"]
                assert result["word"]["definition"] == ""
            assert "enrichment" not in app.load_words()["words"][0]
        finally:
            worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await worker

    asyncio.run(scenario())


def test_manual_definition_is_immediately_available_and_existing_words_stay_compatible(isolated):
    app.save_words({"words": [word("manual", "2026-10-18T10:00:00+08:00"),
                              word("legacy", "2026-10-18T09:00:00+08:00", definition="")]})
    assert app.get_word("manual")["enrichment"]["status"] == "ready"
    assert app.get_word("legacy")["enrichment"]["status"] == "idle"


@pytest.mark.parametrize("spelling", ["Contract", "contract", "iPhone"])
def test_duplicate_returns_original_content_and_progress_without_writes_or_ai(isolated, monkeypatch, spelling):
    existing = word("legacy", "2026-10-18T10:00:00+08:00", word=spelling, phonetic="/test/",
                    srs={"d": 5.0, "s": 10.0, "reps": 3, "lapses": 1})
    app.save_words({"words": [existing]})
    original = isolated.read_bytes()
    async def unexpected(*args):
        pytest.fail("An existing word must not trigger AI enrichment")
    monkeypatch.setattr(app, "_enqueue_enrich_batch", unexpected)
    result = TestClient(app.app).post("/api/words", json={"word": "  " + spelling.swapcase() + "  ", "definition": "Do not overwrite"})
    assert result.status_code == 409
    assert result.json()["detail"]["word"] == existing
    assert result.json()["detail"]["enrichment"]["status"] == "ready"
    assert isolated.read_bytes() == original


@pytest.mark.parametrize("status", ["queued", "processing", "failed"])
def test_duplicate_returns_current_pending_or_failure_state_without_retry(isolated, monkeypatch, status):
    existing = word("pending", "2026-10-18T10:00:00+08:00", definition="")
    app.save_words({"words": [existing]})
    app._enrich_states["pending"] = {"status": status}
    monkeypatch.setattr(app, "_enrich_queue", asyncio.Queue())
    original = isolated.read_bytes()
    result = TestClient(app.app).post("/api/words", json={"word": "Pending"})
    assert result.status_code == 409
    assert result.json()["detail"]["enrichment"]["status"] == status
    assert app._enrich_queue.qsize() == 0
    assert isolated.read_bytes() == original


@pytest.mark.parametrize(("entered", "stored"), [
    ("  contract  ", "Contract"), ("contract law", "Contract law"),
    ("API", "API"), ("I", "I"), ("iPhone", "IPhone"),
    ("McDonald", "McDonald"), ("DNA-binding", "DNA-binding"), ("Contract", "Contract"),
    ("i", "I"), ("eBay", "EBay"),
])
def test_initial_normalization_is_applied_before_persistence_and_enrichment(isolated, monkeypatch, entered, stored):
    monkeypatch.setattr(app, "_enrich_queue", asyncio.Queue())
    result = TestClient(app.app).post("/api/words", json={"word": entered})
    assert result.status_code == 200
    assert result.json()["word"]["word"] == stored
    assert app.load_words()["words"][0]["word"] == stored
    assert app._enrich_queue.get_nowait()[1] == stored
