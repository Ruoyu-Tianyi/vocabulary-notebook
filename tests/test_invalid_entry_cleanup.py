"""Distinguish invalid entries from unavailable AI; protect existing/user-edited data."""
import asyncio
import json

import httpx
import pytest

import app


@pytest.mark.parametrize("case", ["new", "legacy", "edited", "edited_back", "reviewed", "deleted", "renamed", "unavailable", "format", "spelling"])
def test_cleanup_only_removes_unchanged_new_invalid_entries(tmp_path, monkeypatch, case):
    monkeypatch.setattr(app, "DATA_FILE", tmp_path / "words.json")
    monkeypatch.setattr(app, "_new_enrichment_candidates", {})
    monkeypatch.setattr(app, "_enrich_states", {})
    monkeypatch.setattr(app, "_enriching_ids", {})
    monkeypatch.setattr(app, "_enrich_post_check", lambda *args: (case != "format" and case != "spelling", "word 不在英语词典" if case == "spelling" else "例句包含中文"))

    async def scenario():
        monkeypatch.setattr(app, "_enrich_queue", asyncio.Queue())
        monkeypatch.setattr(app, "_event_queue", asyncio.Queue())
        created = await app.create_word({"word": "xyztypo"})
        wid = created["word"]["id"]
        before = app.DATA_FILE.read_bytes()

        async def enrich(_word):
            if case == "unavailable":
                raise app.EnrichmentUnavailable("服务不可用")
            if case == "legacy":
                app._new_enrichment_candidates.clear()  # App restart/old entry.
            if case in ("edited", "edited_back"):
                app.update_word(wid, {"definition": "n. 自己的释义"})
                if case == "edited_back":
                    app.update_word(wid, {"definition": ""})
            if case == "reviewed":
                data = app.load_words()
                data["words"][0]["review_history"] = [{"id": "isolated-review", "rating": 3, "at": "2026-10-18T00:00:00Z"}]
                app.save_words(data)
            if case == "deleted":
                app.delete_word(wid)
            if case == "renamed":
                app.update_word(wid, {"word": "Contract"})
                return "/old/", "n. 旧内容", "The old entry."
            if case in ("format", "spelling"):
                return "/test/", "n. 内容", "A test."
            return "", "", ""

        monkeypatch.setattr(app, "enrich_word", enrich)
        worker = asyncio.create_task(app._enrich_worker())
        try:
            await asyncio.wait_for(app._enrich_queue.join(), 2)
            words = app.load_words()["words"]
            event = app._event_queue.get_nowait()
            assert event["type"] == "enrich_failed"
            if case in ("new", "spelling", "deleted"):
                assert not words
                assert event.get("removed", False) == (case != "deleted")
            else:
                assert len(words) == 1
                assert not event.get("removed", False)
                if case in ("legacy", "unavailable", "format"):
                    assert app.DATA_FILE.read_bytes() == before
                if case == "edited":
                    assert words[0]["definition"] == "n. 自己的释义"
                if case == "reviewed":
                    assert words[0]["srs"]["reps"] == 1
                if case == "renamed":
                    assert words[0]["word"] == "Contract" and not words[0]["definition"]
        finally:
            worker.cancel()
            with pytest.raises(asyncio.CancelledError):
                await worker

    asyncio.run(scenario())


def test_successful_ai_never_overwrites_manual_definition(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DATA_FILE", tmp_path / "words.json")
    monkeypatch.setattr(app, "_new_enrichment_candidates", {})
    monkeypatch.setattr(app, "_enrich_states", {})
    monkeypatch.setattr(app, "_enriching_ids", {})
    monkeypatch.setattr(app, "_enrich_post_check", lambda *args: (True, ""))

    async def scenario():
        monkeypatch.setattr(app, "_enrich_queue", asyncio.Queue())
        monkeypatch.setattr(app, "_event_queue", asyncio.Queue())
        wid = (await app.create_word({"word": "contract"}))["word"]["id"]

        async def enrich(_word):
            app.update_word(wid, {"definition": "n. 人工释义"})
            return "/test/", "n. AI释义", "A contract."

        monkeypatch.setattr(app, "enrich_word", enrich)
        task = asyncio.create_task(app._enrich_worker())
        try:
            await asyncio.wait_for(app._enrich_queue.join(), 2)
            assert app.get_word(wid)["word"]["definition"] == "n. 人工释义"
            assert app._event_queue.get_nowait()["definition"] == "n. 人工释义"
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    asyncio.run(scenario())


@pytest.mark.parametrize("provider", ["ollama", "deepseek"])
@pytest.mark.parametrize("payload", ["empty", "valid", "missing", "wrong_type", "malformed", "network", "http"])
def test_provider_failures_are_not_valid_empty_dictionary_answers(monkeypatch, provider, payload):
    monkeypatch.setattr(app.config, "get_provider", lambda: provider)
    monkeypatch.setattr(app.config, "get_ollama_config", lambda: {"url": "http://local.invalid", "model": "mock"})
    monkeypatch.setattr(app.config, "get_deepseek_config", lambda: {"api_key": "private-test-key", "model": "mock"})
    answers = {"empty": {"phonetic": "", "definition": " ", "example": ""},
               "valid": {"phonetic": " /test/ ", "definition": " n. 测试 ", "example": " A test. "},
               "missing": {}, "wrong_type": {"phonetic": None, "definition": "", "example": ""}}

    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            if payload == "network": raise httpx.ConnectError("private-test-key")
            text = "not json" if payload == "malformed" else json.dumps(answers.get(payload, {}))
            body = {"response": text} if provider == "ollama" else {"choices": [{"message": {"content": text}}]}
            return httpx.Response(503 if payload == "http" else 200, json=body, request=httpx.Request("POST", "http://mock.invalid"))

    monkeypatch.setattr(app.httpx, "AsyncClient", Client)
    if payload in ("empty", "valid"):
        actual = asyncio.run(app.enrich_word("Contract"))
        assert actual == (("", "", "") if payload == "empty" else ("/test/", "n. 测试", "A test."))
    else:
        with pytest.raises(app.EnrichmentUnavailable) as exc:
            asyncio.run(app.enrich_word("Contract"))
        assert "private-test-key" not in str(exc.value)
