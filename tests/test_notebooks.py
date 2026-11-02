"""单词本管理、过滤、复习额度和离线归属冲突的回归测试。"""
import pytest

import app
import sync_storage as storage
from tests.local_client import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DATA_FILE", tmp_path / "words.json")
    monkeypatch.setattr(app, "_new_enrichment_candidates", {})
    return TestClient(app.app)


def create_book(client, name="金融英语"):
    response = client.post("/api/notebooks", json={"name": name, "description": "研究常用词"})
    assert response.status_code == 200
    return response.json()


def create_word(client, text, notebook_id="default"):
    response = client.post("/api/words", json={"word": text, "definition": "n. 测试释义", "notebook_id": notebook_id})
    assert response.status_code == 200
    return response.json()["word"]


def operations(path):
    return list(storage.read(path)["_sync"]["operations"].values())


def test_notebook_crud_preserves_words_and_review_history(client):
    default = client.get("/api/notebooks").json()
    assert default["total_words"] == 0
    assert default["notebooks"][0]["id"] == "default"
    book = create_book(client, "  金融英语  ")
    assert book["name"] == "金融英语"
    assert book["word_count"] == 0
    word = create_word(client, "bond", book["id"])
    client.post(f"/api/words/{word['id']}/review", json={"rating": 3})
    before = client.get(f"/api/words/{word['id']}").json()["word"]
    renamed = client.put(f"/api/notebooks/{book['id']}", json={"name": "资产定价"}).json()
    assert renamed["description"] == "研究常用词"
    assert renamed["word_count"] == 1
    assert client.delete("/api/notebooks/default").status_code == 409
    assert client.delete(f"/api/notebooks/{book['id']}").status_code == 409
    assert client.post("/api/words/move", json={"word_ids": [word["id"]], "notebook_id": "default"}).status_code == 200
    deleted = client.delete(f"/api/notebooks/{book['id']}")
    assert deleted.json() == {"ok": True, "moved_count": 0}
    after = client.get(f"/api/words/{word['id']}").json()["word"]
    assert after == {**before, "notebook_id": "default"}
    assert client.delete(f"/api/notebooks/{book['id']}").status_code == 404
    assert client.get("/api/notebooks").json()["total_words"] == 1
    assert client.get("/api/notebooks").json()["notebooks"][0]["word_count"] == 1


@pytest.mark.parametrize("body", [{}, {"name": " "}, {"name": 3}, {"name": "a" * 81},
                                  {"name": "ok", "description": "a" * 501}])
def test_invalid_notebook_does_not_write(client, body):
    assert client.post("/api/notebooks", json=body).status_code == 422
    assert not app.DATA_FILE.exists()


def test_duplicate_names_and_failed_update_are_atomic(client):
    book = create_book(client, "Finance")
    before = app.DATA_FILE.read_bytes()
    assert client.post("/api/notebooks", json={"name": "finance"}).status_code == 409
    assert client.put(f"/api/notebooks/{book['id']}", json={"name": "默认单词本"}).status_code == 409
    assert client.put(f"/api/notebooks/{book['id']}", json={"description": None}).status_code == 422
    assert client.put("/api/notebooks/missing", json={"name": "missing"}).status_code == 404
    assert app.DATA_FILE.read_bytes() == before


def test_word_assignment_and_duplicate_detection_within_notebook(client):
    book = create_book(client)
    existing = create_word(client, "bond")
    before = app.DATA_FILE.read_bytes()
    duplicate = client.post("/api/words", json={"word": "BOND", "notebook_id": "default"})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["word"] == existing
    assert app.DATA_FILE.read_bytes() == before
    assert client.post("/api/words", json={"word": "unknown", "notebook_id": "missing"}).status_code == 404
    changed = client.put(f"/api/words/{existing['id']}", json={"notebook_id": book["id"]})
    assert changed.json()["word"] == {**existing, "notebook_id": book["id"]}
    before = app.DATA_FILE.read_bytes()
    assert client.put(f"/api/words/{existing['id']}", json={"word": "changed", "notebook_id": "missing"}).status_code == 404
    assert app.DATA_FILE.read_bytes() == before


def test_bulk_move_is_atomic_and_keeps_schedule(client):
    book = create_book(client)
    first, second = create_word(client, "bond"), create_word(client, "equity")
    client.post(f"/api/words/{first['id']}/review", json={"rating": 4})
    before_word = client.get(f"/api/words/{first['id']}").json()["word"]
    before = app.DATA_FILE.read_bytes()
    response = client.post("/api/words/move", json={"word_ids": [first["id"], "missing"], "notebook_id": book["id"]})
    assert response.status_code == 404
    assert app.DATA_FILE.read_bytes() == before
    assert client.post("/api/words/move", json={"word_ids": [], "notebook_id": book["id"]}).status_code == 422
    assert client.post("/api/words/move", json={"word_ids": [first["id"]], "notebook_id": "missing"}).status_code == 404
    response = client.post("/api/words/move", json={"word_ids": [first["id"], second["id"], first["id"]], "notebook_id": book["id"]})
    assert response.json() == {"ok": True, "moved_count": 2}
    assert client.get(f"/api/words/{first['id']}").json()["word"] == {**before_word, "notebook_id": book["id"]}
    assert client.post("/api/words/move", json={"word_ids": [first["id"]], "notebook_id": book["id"]}).json()["moved_count"] == 0


def test_scoped_lists_dates_letters_and_exports(client, monkeypatch):
    book = create_book(client)
    first = create_word(client, "bond", book["id"])
    second = create_word(client, "asset", book["id"])
    other = create_word(client, "credit")
    data = app.load_words()
    for word in data["words"]:
        word["created_at"] = "2026-10-24T12:00:00+08:00" if word["id"] == other["id"] else "2026-10-25T12:00:00+08:00"
    app.save_words(data)
    params = {"notebook_id": book["id"], "sort": "alpha_asc", "size": 1}
    listing = client.get("/api/words", params=params).json()
    assert listing["total"] == 2 and listing["pages"] == 2
    assert listing["words"][0]["id"] == second["id"]
    assert listing["available_letters"] == ["a", "b"]
    assert client.get("/api/words", params={**params, "page": 2}).json()["words"][0]["id"] == first["id"]
    assert client.get("/api/dates", params=params).json()["dates"] == ["2026-10-25"]
    assert client.get("/api/words", params={**params, "q": "credit"}).json()["total"] == 0
    assert client.get("/api/words", params={**params, "date": "2026-10-24"}).json()["total"] == 0
    export = client.get("/api/words/export", params={**params, "letter": "b"}).json()
    assert [word["id"] for word in export["words"]] == [first["id"]]
    assert [item["id"] for item in export["notebooks"]] == [book["id"]]
    csv = client.get("/api/words/export", params={**params, "format": "csv"}).text
    assert "Bond" in csv and "Asset" in csv and "Credit" not in csv
    captured = []
    monkeypatch.setattr(app, "_build_pdf", lambda words, *_: captured.extend(words) or b"test-pdf")
    assert client.get("/api/words/export", params={**params, "format": "pdf"}).content == b"test-pdf"
    assert [word["id"] for word in captured] == [second["id"], first["id"]]


@pytest.mark.parametrize("endpoint", ["/api/words", "/api/dates", "/api/words/export", "/api/review/stats", "/api/review/due"])
def test_unknown_notebook_filter_is_not_silently_all_words(client, endpoint):
    assert client.get(endpoint, params={"notebook_id": "missing"}).status_code == 404


def test_review_scope_keeps_daily_new_quota_global(client, monkeypatch):
    monkeypatch.setattr(app.config, "get_srs_config", lambda: {"daily_new_limit": 1})
    book = create_book(client)
    other = create_word(client, "bond")
    fresh = create_word(client, "equity", book["id"])
    scoped = {"notebook_id": book["id"]}
    initial = client.get("/api/review/due", params=scoped).json()
    assert [card["id"] for card in initial["cards"]] == [fresh["id"]]
    client.post(f"/api/words/{other['id']}/review", json={"rating": 3})
    result = client.get("/api/review/due", params=scoped).json()
    assert result["cards"] == []
    assert result["stats"]["new_today"] == 1
    assert result["stats"]["new_remaining"] == 1
    assert result["stats"]["due_today"] == 0
    assert client.get("/api/review/stats", params=scoped).json() == result["stats"]
    assert client.get("/api/review/stats").json()["total"] == 2


def test_enrich_missing_only_queues_selected_notebook(client, monkeypatch):
    book = create_book(client)
    first = create_word(client, "bond", book["id"])
    create_word(client, "equity")
    data = app.load_words()
    for word in data["words"]:
        word["definition"] = ""
    app.save_words(data)
    queued = []
    async def capture(items):
        queued.extend(items)
    monkeypatch.setattr(app, "_maybe_reset_batch_if_idle", lambda: None)
    monkeypatch.setattr(app, "_enriching_ids", {})
    monkeypatch.setattr(app, "_ENRICH_COOLDOWN", 0)
    monkeypatch.setattr(app, "_enqueue_enrich_batch", capture)
    response = client.post("/api/words/enrich-missing", params={"notebook_id": book["id"]})
    assert response.status_code == 200, response.text
    assert response.json()["word_ids"] == [first["id"]]
    assert queued == [(first["id"], "Bond")]
    assert client.post("/api/words/enrich-missing", params={"notebook_id": "missing"}).status_code == 404


def test_deleted_book_wins_over_offline_rename_and_new_assignment(tmp_path):
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    data = storage.read(first)
    data["notebooks"].append({"id": "finance", "name": "金融英语", "description": ""})
    data["words"].append({"id": "bond", "word": "Bond", "notebook_id": "finance", "created_at": "2026-10-25"})
    storage.commit(first, data)
    storage.merge(second, operations(first))
    left = storage.read(first)
    left["notebooks"] = [book for book in left["notebooks"] if book["id"] != "finance"]
    storage.commit(first, left)
    right = storage.read(second)
    next(book for book in right["notebooks"] if book["id"] == "finance")["name"] = "离线改名"
    right["words"].append({"id": "equity", "word": "Equity", "notebook_id": "finance", "created_at": "2026-10-25"})
    storage.commit(second, right)
    left_ops, right_ops = operations(first), operations(second)
    storage.merge(first, right_ops)
    storage.merge(second, list(reversed(left_ops)))
    left, right = storage.read(first), storage.read(second)
    assert left["notebooks"] == right["notebooks"]
    assert [book["id"] for book in left["notebooks"]] == ["default"]
    assert left["words"] == right["words"]
    assert len(left["words"]) == 2
    assert {word["notebook_id"] for word in left["words"]} == {"default"}
    assert any(op["entity"] == "notebook" and op["field"] == "deleted" for op in operations(first))


def test_out_of_order_book_operations_restore_assignment_without_losing_word(tmp_path):
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    data = storage.read(first)
    data["notebooks"].append({"id": "finance", "name": "金融英语"})
    data["words"].append({"id": "bond", "word": "Bond", "notebook_id": "finance", "created_at": "2026-10-25"})
    storage.commit(first, data)
    storage.merge(second, [op for op in operations(first) if op["entity"] == "word"])
    assert storage.read(second)["words"][0]["notebook_id"] == "default"
    storage.merge(second, [op for op in operations(first) if op["entity"] == "notebook"])
    assert storage.read(second)["words"][0]["notebook_id"] == "finance"


def test_scoped_json_export_round_trips_notebook(client, tmp_path, monkeypatch):
    book = create_book(client)
    word = create_word(client, "bond", book["id"])
    exported = client.get("/api/words/export", params={"notebook_id": book["id"]}).json()
    monkeypatch.setattr(app, "DATA_FILE", tmp_path / "other.json")
    assert client.post("/api/library/import", json=exported).status_code == 200
    restored = client.get(f"/api/words/{word['id']}").json()["word"]
    assert restored == word
    assert len(client.get("/api/notebooks").json()["notebooks"]) == 2


def test_import_portable_deleted_book_uses_fresh_identity(client):
    book = create_book(client)
    word = create_word(client, "bond", book["id"])
    exported = client.get("/api/words/export", params={"notebook_id": book["id"]}).json()
    client.delete(f"/api/words/{word['id']}")
    client.delete(f"/api/notebooks/{book['id']}")
    response = client.post("/api/library/import", json=exported)
    assert response.status_code == 200
    data = app.load_words()
    restored_book = next(item for item in data["notebooks"] if item["id"] != "default")
    assert restored_book["id"] != book["id"]
    assert data["words"][0]["id"] != word["id"]
    assert data["words"][0]["notebook_id"] == restored_book["id"]


def test_same_spelling_in_two_books_reuses_dictionary_but_has_independent_review(client):
    book = create_book(client)
    first = create_word(client, "bond")
    data = app.load_words()
    data["words"][0].update(phonetic="/bɒnd/", example="The bond matures.")
    app.save_words(data)
    client.post(f"/api/words/{first['id']}/review", json={"rating": 4})
    source = client.get(f"/api/words/{first['id']}").json()["word"]
    response = client.post("/api/words", json={"word": "BOND", "notebook_id": book["id"]})
    assert response.status_code == 200
    second = response.json()["word"]
    assert second["id"] != first["id"] and second["notebook_id"] == book["id"]
    assert second["definition"] == source["definition"]
    assert second["phonetic"] == source["phonetic"]
    assert second["example"] == source["example"]
    assert "srs" not in second and "review_history" not in second
    assert second["created_at"] != source["created_at"]
    assert client.get("/api/review/stats", params={"notebook_id": "default"}).json()["new_remaining"] == 0
    assert client.get("/api/review/stats", params={"notebook_id": book["id"]}).json()["new_remaining"] == 1
    client.post(f"/api/words/{second['id']}/review", json={"rating": 1})
    assert client.get(f"/api/words/{first['id']}").json()["word"] == source
    assert client.get(f"/api/words/{second['id']}").json()["word"]["srs"]["lapses"] == 1
    assert client.post("/api/words", json={"word": "bond", "notebook_id": book["id"]}).status_code == 409


def test_copy_words_preserves_source_and_starts_new_progress(client):
    book = create_book(client)
    first, second = create_word(client, "bond"), create_word(client, "equity")
    client.post(f"/api/words/{first['id']}/review", json={"rating": 4})
    source = client.get(f"/api/words/{first['id']}").json()["word"]
    existing = create_word(client, "EQUITY", book["id"])
    response = client.post("/api/words/copy", json={"word_ids": [first["id"], second["id"]], "notebook_id": book["id"]})
    assert response.json() == {"ok": True, "copied_count": 1, "skipped_count": 1}
    assert client.get(f"/api/words/{first['id']}").json()["word"] == source
    assert client.get(f"/api/words/{existing['id']}").json()["word"] == existing
    copied = next(word for word in client.get("/api/words", params={"notebook_id": book["id"]}).json()["words"] if word["word"] == "Bond")
    assert copied["id"] != first["id"] and copied["created_at"] != first["created_at"]
    assert copied["definition"] == source["definition"]
    assert "srs" not in copied and "review_history" not in copied
    before = app.DATA_FILE.read_bytes()
    assert client.post("/api/words/copy", json={"word_ids": [second["id"], "missing"], "notebook_id": book["id"]}).status_code == 404
    assert app.DATA_FILE.read_bytes() == before
    assert client.post("/api/words/copy", json={"word_ids": [first["id"]], "notebook_id": book["id"]}).json()["copied_count"] == 0
    assert app.DATA_FILE.read_bytes() == before


def test_move_or_rename_conflict_never_merges_independent_progress(client):
    book = create_book(client)
    first, second = create_word(client, "bond"), create_word(client, "equity")
    destination = create_word(client, "BOND", book["id"])
    client.post(f"/api/words/{first['id']}/review", json={"rating": 4})
    client.post(f"/api/words/{destination['id']}/review", json={"rating": 1})
    before = app.DATA_FILE.read_bytes()
    assert client.post("/api/words/move", json={"word_ids": [second["id"], first["id"]], "notebook_id": book["id"]}).status_code == 409
    assert client.put(f"/api/words/{first['id']}", json={"notebook_id": book["id"]}).status_code == 409
    assert client.put(f"/api/words/{second['id']}", json={"word": "BOND"}).status_code == 409
    assert app.DATA_FILE.read_bytes() == before
    empty = create_book(client, "新词")
    before = app.DATA_FILE.read_bytes()
    assert client.post("/api/words/move", json={"word_ids": [destination["id"], first["id"]], "notebook_id": empty["id"]}).status_code == 409
    assert app.DATA_FILE.read_bytes() == before
