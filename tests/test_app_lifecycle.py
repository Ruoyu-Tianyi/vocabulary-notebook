"""启动与停止失败时仍释放临时词库锁，不运行真实服务。"""
import asyncio
import threading
from types import SimpleNamespace

import pytest

import app
import instance_lock


@pytest.fixture
def isolated_lifecycle(tmp_path, monkeypatch):
    path = tmp_path / "words.json"
    monkeypatch.setattr(app, "DATA_FILE", path)
    monkeypatch.setattr(app.config, "get_provider", lambda: "ollama")
    monkeypatch.setattr(app.config, "get_sync_config", lambda: {"interval_seconds": 30})
    monkeypatch.setattr(app.config, "get_srs_config", lambda: {"daily_new_limit": 20})
    monkeypatch.setattr(app, "load_words", lambda: {"words": []})
    monkeypatch.setattr(app, "cloud", SimpleNamespace(lock=threading.Lock(), cancel_auth=lambda: None))
    for name in ("_enriching_ids", "_enrich_states", "_new_enrichment_candidates"):
        monkeypatch.setattr(app, name, {})
    for name in ("_event_queue", "_enrich_queue", "_enrich_current"):
        monkeypatch.setattr(app, name, None)
    for name in ("_enrich_batch_total", "_enrich_batch_done"):
        monkeypatch.setattr(app, name, 0)
    return path


@pytest.mark.parametrize("target", ["get_provider", "get_srs_config", "load_words"])
def test_startup_failure_releases_instance_lock(isolated_lifecycle, monkeypatch, target):
    def fail():
        raise ValueError("isolated startup failure")

    monkeypatch.setattr(app if target == "load_words" else app.config, target, fail)

    async def scenario():
        with pytest.raises(ValueError, match="startup failure"):
            async with app.lifespan(app.app):
                pytest.fail("invalid startup must not enter the application")
        instance_lock.acquire(isolated_lifecycle).close()

    asyncio.run(scenario())
    assert not isolated_lifecycle.exists()


@pytest.mark.parametrize("failure", ["background", "cancel_auth"])
def test_shutdown_failure_still_joins_workers_and_releases_lock(isolated_lifecycle, monkeypatch, failure):
    finished = set()

    async def worker(name):
        try:
            if name == "sync" and failure == "background":
                raise RuntimeError("isolated background failure")
            await asyncio.Event().wait()
        finally:
            finished.add(name)

    monkeypatch.setattr(app, "_enrich_worker", lambda: worker("enrich"))
    monkeypatch.setattr(app, "_periodic_backup_loop", lambda: worker("backup"))
    monkeypatch.setattr(app, "_cloud_sync_loop", lambda: worker("sync"))
    if failure == "cancel_auth":
        def fail_cancel():
            raise RuntimeError("isolated cancellation failure")
        monkeypatch.setattr(app.cloud, "cancel_auth", fail_cancel)

    async def run_lifespan():
        async with app.lifespan(app.app):
            await asyncio.sleep(0)
            with pytest.raises(RuntimeError, match="另一个"):
                instance_lock.acquire(isolated_lifecycle)

    async def scenario():
        if failure == "cancel_auth":
            with pytest.raises(RuntimeError, match="cancellation failure"):
                await run_lifespan()
        else:
            await run_lifespan()
        assert finished == {"enrich", "backup", "sync"}
        instance_lock.acquire(isolated_lifecycle).close()

    asyncio.run(scenario())
    assert not isolated_lifecycle.exists()
