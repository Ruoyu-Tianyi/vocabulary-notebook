"""Regressions reported during upstream review; all storage and AI are isolated."""
import asyncio
import threading
from datetime import timedelta
import pytest
import app
import sync_storage as storage
from drive_sync import DriveSync
from tests.local_client import TestClient


@pytest.mark.parametrize("peer", ["192.168.1.10", "203.0.113.1", "::ffff:192.168.1.10", "untrusted"])
def test_nonlocal_peer_cannot_manage_sync_even_with_forged_headers(tmp_path, monkeypatch, peer):
    data = tmp_path / "words.json"
    monkeypatch.setattr(app, "DATA_FILE", data)
    monkeypatch.setattr(app, "cloud", DriveSync(lambda: data, threading.RLock(), lambda: {"credentials_dir": str(tmp_path / "secrets"), "interval_seconds": 30}))
    folder = tmp_path / "folder"
    folder.mkdir()
    client = TestClient(app.app, peer=peer)
    headers = {"Host": "localhost", "Origin": "http://localhost:5173",
               "X-Forwarded-For": "127.0.0.1", "Forwarded": "for=127.0.0.1"}
    assert client.post("/api/sync/folder", json={"path": str(folder)}, headers=headers).status_code == 403
    assert client.get("/api/sync/status", headers=headers).status_code == 403
    assert not list(folder.iterdir())
    assert not (tmp_path / "secrets").exists()
    assert not data.exists()


@pytest.mark.parametrize("peer", ["127.0.0.1", "::1"])
def test_loopback_peer_can_read_sync_status(tmp_path, monkeypatch, peer):
    monkeypatch.setattr(app, "cloud", DriveSync(lambda: tmp_path / "words.json", threading.RLock(), lambda: {"credentials_dir": str(tmp_path / "secrets"), "interval_seconds": 30}))
    assert TestClient(app.app, peer=peer).get("/api/sync/status").status_code == 200


@pytest.mark.parametrize("change", ["move", "rename-course", "describe-course", "delete"])
def test_ai_result_for_old_course_is_discarded_and_retry_is_not_cooled_down(tmp_path, monkeypatch, change):
    monkeypatch.setattr(app, "DATA_FILE", tmp_path / "words.json")
    monkeypatch.setattr(app, "_enriching_ids", {"security": 999999999})
    monkeypatch.setattr(app, "_enrich_post_check", lambda *args: (True, ""))
    app.save_words({"words": [{"id": "security", "word": "security", "definition": "", "phonetic": "",
                               "example": "", "created_at": "2026-10-18T00:00:00Z", "notebook_id": "finance"}],
                    "notebooks": [{"id": "default", "name": "默认", "description": ""},
                                  {"id": "finance", "name": "金融", "description": "投资课程"},
                                  {"id": "law", "name": "法律", "description": "担保法课程"}]})

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        events = asyncio.Queue()
        monkeypatch.setattr(app, "_event_queue", events)
        queue = asyncio.Queue()
        monkeypatch.setattr(app, "_enrich_queue", queue)
        async def ai(word, context):
            assert context == "金融: 投资课程"
            entered.set()
            await release.wait()
            return "/s/", "n. 证券", "The security pays a dividend."
        monkeypatch.setattr(app, "enrich_word", ai)
        await queue.put(("security", "security"))
        task = asyncio.create_task(app._enrich_worker())
        try:
            await asyncio.wait_for(entered.wait(), 2)
            data = app.load_words()
            if change == "move":
                data["words"][0]["notebook_id"] = "law"
            elif change == "delete":
                data["words"] = []
            else:
                book = next(b for b in data["notebooks"] if b["id"] == "finance")
                book["name" if change == "rename-course" else "description"] = "合同法"
            app.save_words(data)
            before = app.DATA_FILE.read_bytes()
            release.set()
            await asyncio.wait_for(queue.join(), 2)
            assert app.DATA_FILE.read_bytes() == before
            assert "security" not in app._enriching_ids
            event = events.get_nowait()
            assert event["type"] == "enrich_failed" and "旧补全" in event["reason"]
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    asyncio.run(scenario())


def test_utc_suffix_and_fractional_seconds_work_for_review_replay():
    for value in ("2026-10-18T03:00:00Z", "2026-10-18T03:00:00.123456Z"):
        offset = value[:-1] + "+00:00"
        assert storage._time(value) == storage._time(offset)
        assert app._parse_review_time(value) == app._parse_review_time(offset)
        assert storage._time(value).utcoffset() == timedelta(0)
    assert storage._time("2026-10-18T11:00:00").utcoffset() == timedelta(hours=8)
    events = [{"id": "first", "rating": 3, "at": "2026-10-18T03:00:00Z"},
              {"id": "second", "rating": 4, "at": "2026-10-19T03:00:00.123Z"}]
    state = storage.review_state(None, events)
    assert state["reps"] == 2


@pytest.mark.parametrize("value", ["2026-10-18T03:00:00Z", "2026-10-18T03:00:00.123456Z"])
def test_utc_suffix_matches_explicit_offset_on_older_python(value):
    assert app._parse_review_time(value) == app._parse_review_time(value[:-1] + "+00:00")
