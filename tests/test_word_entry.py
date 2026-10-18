"""Duplicate lookup must be read-only and scoped to the selected notebook."""
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


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DATA_FILE", tmp_path / "words.json")
    monkeypatch.setattr(app.config, "get_ai_settings", lambda: {"configured": False})
    monkeypatch.setattr(app, "_enrich_jobs", {})
    monkeypatch.setattr(app, "_enriching_ids", {})
    monkeypatch.setattr(app, "_enrich_queue", asyncio.Queue())
    return TestClient(app.app)


def test_duplicate_returns_existing_fields_and_schedule_without_writing_or_enriching(client, monkeypatch):
    created = client.post("/api/words", json={"word": "contract", "definition": "n. 合同",
                          "phonetic": "/test/", "example": "The contract is valid."}).json()["word"]
    client.post(f"/api/words/{created['id']}/review", json={"rating": 3})
    stored = app.load_words()["words"][0]
    original = app.DATA_FILE.read_bytes()
    async def unexpected(*args):
        pytest.fail("Looking up an existing word must not enqueue AI work")
    monkeypatch.setattr(app, "_enqueue_enrich_batch", unexpected)
    result = client.post("/api/words", json={"word": "  Contract  ", "definition": "Must not overwrite"})
    assert result.status_code == 409
    existing = result.json()["detail"]
    assert existing["word"] == stored
    assert existing["enrichment"]["status"] == "ready"
    assert existing["message"]
    assert app.DATA_FILE.read_bytes() == original
    assert app._enrich_queue.qsize() == 0


def test_duplicate_lookup_returns_only_selected_notebook_contents(client):
    law = client.post("/api/notebooks", json={"name": "Law"}).json()["notebook"]["id"]
    finance = client.post("/api/notebooks", json={"name": "Finance"}).json()["notebook"]["id"]
    law_word = client.post("/api/words", json={"word": "security", "definition": "n. 担保", "notebook_id": law}).json()["word"]
    fin_word = client.post("/api/words", json={"word": "security", "definition": "n. 证券", "notebook_id": finance}).json()["word"]
    for book_id, expected in [(law, law_word), (finance, fin_word)]:
        result = client.post("/api/words", json={"word": "SECURITY", "notebook_id": book_id})
        assert result.status_code == 409
        assert result.json()["detail"]["word"] == expected
    assert client.post("/api/words", json={"word": "security", "definition": "n. 安全"}).status_code == 200
    assert len(app.load_words()["words"]) == 3


@pytest.mark.parametrize("status", ["queued", "processing", "failed"])
def test_existing_unfinished_word_returns_current_status_without_retrying(client, monkeypatch, status):
    created = client.post("/api/words", json={"word": "consideration"}).json()["word"]
    monkeypatch.setattr(app.config, "get_ai_settings", lambda: {"configured": True})
    app._enrich_jobs[created["id"]] = {"status": status, "error": "test error"}
    original = app.DATA_FILE.read_bytes()
    result = client.post("/api/words", json={"word": "Consideration"})
    assert result.json()["detail"]["enrichment"]["status"] == status
    assert app._enrich_queue.qsize() == 0
    assert app.DATA_FILE.read_bytes() == original


@pytest.mark.parametrize(("entered", "stored"), [
    ("  contract  ", "Contract"), ("contract law", "Contract law"),
    ("API", "API"), ("I", "I"), ("iPhone", "IPhone"),
    ("McDonald", "McDonald"), ("DNA-binding", "DNA-binding"), ("Contract", "Contract"),
    ("i", "I"), ("eBay", "EBay"),
])
def test_new_word_initial_is_uppercase_and_remaining_characters_are_preserved(client, entered, stored):
    result = client.post("/api/words", json={"word": entered, "definition": "n. 测试"})
    assert result.status_code == 200
    assert result.json()["word"]["word"] == stored
    assert app.load_words()["words"][0]["word"] == stored


@pytest.mark.parametrize("spelling", ["London", "london", "iPhone"])
def test_existing_capitalization_and_manual_edits_are_preserved(client, spelling):
    created = client.post("/api/words", json={"word": "London", "definition": "n. 伦敦"}).json()["word"]
    assert client.put(f"/api/words/{created['id']}", json={"word": spelling}).status_code == 200
    original = app.DATA_FILE.read_bytes()
    result = client.post("/api/words", json={"word": spelling.swapcase()})
    assert result.json()["detail"]["word"]["word"] == spelling
    assert app.DATA_FILE.read_bytes() == original
