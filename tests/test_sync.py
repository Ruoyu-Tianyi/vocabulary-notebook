"""Two independent computers, offline concurrent edits, persistent FSRS and Drive IO."""
import copy
import json
import threading

import httpx
import pytest
from tests.local_client import TestClient

import app
import drive_sync
import sync_storage as storage
import instance_lock


def word(word_id="contract", text="contract", **extra):
    return {"id": word_id, "word": text, "notebook_id": "default", "phonetic": "",
            "definition": "n. 合同", "example": "A binding contract.",
            "created_at": "2026-10-18T08:00:00+00:00", **extra}


def ops(path):
    return list(storage.read(path)["_sync"]["operations"].values())


def engine(path, secrets):
    return drive_sync.DriveSync(lambda: path, threading.RLock(),
                                lambda: {"credentials_dir": str(secrets), "interval_seconds": 30})


def test_legacy_migration_preserves_schedule_and_original(tmp_path):
    path = tmp_path / "words.json"
    srs = storage.review_state(None, [{"id": "legacy", "rating": 3, "at": "2026-10-17T10:00:00Z"}])
    original = {"words": [word(srs=srs)]}
    path.write_text(json.dumps(original), encoding="utf-8")
    migrated = storage.read(path)
    assert migrated["words"][0]["srs"] == srs
    assert migrated["words"][0]["notebook_id"] == "default"
    assert json.loads(path.with_suffix(".json.legacy.bak").read_text()) == original
    assert storage.read(path) == migrated


def test_field_edits_merge_independently_and_converge(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    storage.commit(a, {"words": [word()]})
    storage.merge(b, ops(a))
    left, right = storage.read(a), storage.read(b)
    left["words"][0]["definition"] = "n. 法律上可执行的协议"
    right["words"][0]["example"] = "The contract is enforceable."
    storage.commit(a, left)
    storage.commit(b, right)
    storage.merge(a, ops(b))
    storage.merge(b, ops(a))
    assert storage.read(a)["words"] == storage.read(b)["words"]
    assert storage.read(a)["words"][0]["definition"] == "n. 法律上可执行的协议"
    assert storage.read(a)["words"][0]["example"] == "The contract is enforceable."


def test_same_field_conflict_is_deterministic_in_any_merge_order(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    storage.commit(a, {"words": [word()]})
    storage.merge(b, ops(a))
    for path, value in ((a, "法律定义"), (b, "金融定义")):
        data = storage.read(path)
        data["words"][0]["definition"] = value
        storage.commit(path, data)
    left, right = ops(a), ops(b)
    storage.merge(a, right)
    storage.merge(b, list(reversed(left)))
    assert storage.read(a)["words"] == storage.read(b)["words"]
    before = a.read_bytes()
    storage.merge(a, left + right)
    assert a.read_bytes() == before


def test_offline_review_events_are_both_preserved_and_replayed(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    storage.commit(a, {"words": [word()]})
    storage.merge(b, ops(a))
    for path, event in ((a, {"id": "review-a", "rating": 3, "at": "2026-10-18T10:00:00Z"}),
                        (b, {"id": "review-b", "rating": 1, "at": "2026-10-18T11:00:00Z"})):
        data = storage.read(path)
        data["words"][0]["review_history"] = [event]
        storage.commit(path, data)
    left, right = ops(a), ops(b)
    storage.merge(a, right)
    storage.merge(b, left)
    merged = storage.read(a)["words"][0]
    assert merged == storage.read(b)["words"][0]
    assert len(merged["review_history"]) == 2
    assert merged["srs"]["reps"] == 2
    assert merged["srs"]["lapses"] == 1
    assert merged["srs"] == storage.review_state(None, merged["review_history"])


def test_delete_wins_over_stale_offline_edit_and_review(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    storage.commit(a, {"words": [word()]})
    storage.merge(b, ops(a))
    data = storage.read(a)
    data["words"] = []
    storage.commit(a, data)
    data = storage.read(b)
    data["words"][0].update(definition="离线编辑", review_history=[{"id": "late", "rating": 4, "at": "2026-10-18T11:00:00Z"}])
    storage.commit(b, data)
    left, right = ops(a), ops(b)
    storage.merge(a, right)
    storage.merge(b, left)
    assert storage.read(a)["words"] == storage.read(b)["words"] == []


def test_corrupt_local_file_is_never_overwritten(tmp_path):
    path = tmp_path / "words.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="损坏"):
        storage.read(path)
    with pytest.raises(ValueError):
        storage.merge(path, [])
    assert path.read_text() == "{broken"


def test_invalid_remote_batch_cannot_partially_overwrite(tmp_path):
    path = tmp_path / "words.json"
    storage.commit(path, {"words": [word()]})
    before = path.read_bytes()
    valid = copy.deepcopy(ops(path)[0])
    valid.update(id="remote-id", clock=100, field="definition", value="remote")
    invalid = {**valid, "id": "bad", "field": "review", "value": {"id": "x", "rating": 5, "at": "bad"}}
    with pytest.raises(ValueError):
        storage.merge(path, [valid, invalid])
    assert path.read_bytes() == before


def test_folder_two_computers_restart_and_idempotency(tmp_path):
    folder = tmp_path / "drive"
    a, b = tmp_path / "pc-a.json", tmp_path / "pc-b.json"
    left, right = engine(a, tmp_path / "secrets-a"), engine(b, tmp_path / "secrets-b")
    left.configure_folder(str(folder))
    right.configure_folder(str(folder))
    storage.commit(a, {"words": [word()]})
    assert left.sync()["pushed"] > 0
    assert right.sync()["pulled"] > 0
    changed = storage.read(b)
    changed["words"].append(word("bond", "bond"))
    storage.commit(b, changed)
    assert right.sync()["pushed"] > 0
    assert left.sync()["pulled"] > 0
    assert storage.read(a)["words"] == storage.read(b)["words"]
    restarted = engine(a, tmp_path / "secrets-a")
    assert restarted.sync() == {"pulled": 0, "pushed": 0}
    assert restarted.status()["pending"] == 0


def test_unavailable_folder_keeps_offline_changes(tmp_path):
    folder, path = tmp_path / "drive", tmp_path / "words.json"
    sync = engine(path, tmp_path / "secrets")
    sync.configure_folder(str(folder))
    storage.commit(path, {"words": [word()]})
    before = path.read_bytes()
    folder.rename(tmp_path / "offline-drive")
    assert "error" in sync.sync()
    assert path.read_bytes() == before
    assert sync.status()["pending"] > 0
    (tmp_path / "offline-drive").rename(folder)
    assert sync.sync()["pushed"] > 0


class FakeDrive:
    def __init__(self):
        self.files = {}
        self.requests = []
        self.fail_upload_once = False

    def handle(self, request):
        self.requests.append(request)
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "refreshed", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer refreshed"
        if request.url.path == "/drive/v3/files":
            assert request.url.params["spaces"] == "appDataFolder"
            return httpx.Response(200, json={"files": [{"id": key, "size": str(len(value))} for key, value in self.files.items()]})
        if request.url.path.startswith("/drive/v3/files/"):
            return httpx.Response(200, content=self.files[request.url.path.rsplit("/", 1)[1]])
        if request.url.path == "/upload/drive/v3/files":
            boundary = request.headers["Content-Type"].split("boundary=")[1].encode()
            parts = request.content.split(b"--" + boundary)
            metadata = json.loads(parts[1].split(b"\r\n\r\n", 1)[1].strip())
            assert metadata["parents"] == ["appDataFolder"]
            payload = parts[2].split(b"\r\n\r\n", 1)[1].strip()
            self.files[str(len(self.files) + 1)] = payload
            if self.fail_upload_once:
                self.fail_upload_once = False
                raise httpx.ReadTimeout("response lost after upload", request=request)
            return httpx.Response(200, json={"id": str(len(self.files))})
        raise AssertionError(str(request.url))


def connect_fake(sync):
    storage.atomic_write(sync.secrets_dir / "client_secret.json", {"installed": {"client_id": "test.apps.googleusercontent.com", "client_secret": "secret"}})
    storage.atomic_write(sync.secrets_dir / "token.json", {"access_token": "expired", "refresh_token": "refresh", "expires_at": 0})


def test_drive_api_refresh_upload_download_and_retry(tmp_path, monkeypatch):
    drive = FakeDrive()
    real_client = httpx.Client
    monkeypatch.setattr(drive_sync.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(drive.handle), **kwargs))
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    left, right = engine(a, tmp_path / "secret-a"), engine(b, tmp_path / "secret-b")
    connect_fake(left)
    connect_fake(right)
    storage.commit(a, {"words": [word()]})
    drive.fail_upload_once = True
    assert "error" in left.sync()
    assert left.status()["pending"] > 0
    # Upload succeeded but its response was lost. Pulling the immutable log recovers it.
    assert "error" not in left.sync()
    assert len(drive.files) == 1
    assert right.sync()["pulled"] > 0
    assert storage.read(a)["words"] == storage.read(b)["words"]
    assert right.sync() == {"pulled": 0, "pushed": 0}
    assert right.status()["pending"] == 0
    assert all(b"refresh_token" not in payload and b"client_secret" not in payload for payload in drive.files.values())


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "words.json"
    monkeypatch.setattr(app, "DATA_FILE", path)
    monkeypatch.setattr(app, "cloud", engine(path, tmp_path / "secrets"))
    monkeypatch.setattr(app.config, "_CONFIG", {"provider": "ollama", "ollama": {"url": "http://127.0.0.1:11434/api/generate", "model": "test"}})
    # No lifespan: these API checks must not contact a real local AI or Drive account.
    return TestClient(app.app)


def test_full_backup_roundtrip_preserves_review_history(client, tmp_path):
    created = client.post("/api/words", json={"word": "bond", "definition": "n. 债券"}).json()["word"]
    client.post(f"/api/words/{created['id']}/review", json={"rating": 4})
    backup = client.get("/api/library/export").json()
    target = tmp_path / "restored.json"
    storage.merge(target, backup["operations"])
    restored = storage.read(target)["words"][0]
    assert len(restored["review_history"]) == 1 and restored["srs"]["reps"] == 1
    assert client.post("/api/library/import", json=backup).json()["imported"] == 0


def test_origin_guard_and_input_validation(client):
    assert client.post("/api/words", json={"word": 123}).status_code == 422
    assert client.post("/api/words", json={"word": "bad"}, headers={"Origin": "https://example.org"}).status_code == 403
    assert client.get("/api/sync/status", headers={"Host": "evil.example"}).status_code == 400
    assert client.post("/api/sync/credentials", json={"web": {"client_id": "not desktop"}}).status_code == 422
    assert client.post("/api/sync/connect").status_code == 409


def test_legacy_import_rejects_bad_state_before_writing(client):
    assert client.post("/api/library/import", json={"words": [word()]}).json()["imported"] == 1
    before = app.DATA_FILE.read_bytes()
    response = client.post("/api/library/import", json={"words": [word("bad", srs={"d": "broken"})]})
    assert response.status_code == 422
    assert app.DATA_FILE.read_bytes() == before


def test_cache_lock_rejects_second_process_and_releases(tmp_path):
    path = tmp_path / "words.json"
    held = instance_lock.acquire(path)
    try:
        with pytest.raises(RuntimeError, match="另一个"):
            instance_lock.acquire(path)
    finally:
        held.close()
    instance_lock.acquire(path).close()


def test_future_cache_version_never_overwrites_existing_data(tmp_path):
    path = tmp_path / "words.json"
    data = storage.commit(path, {"words": [word()]})
    data["_sync"]["version"] = 999
    storage.atomic_write(path, data)
    original = path.read_bytes()
    with pytest.raises(ValueError, match="版本"):
        storage.read(path)
    with pytest.raises(ValueError):
        storage.commit(path, {"words": []})
    assert path.read_bytes() == original


def test_pending_auth_can_resume_and_cancel_without_connecting(client):
    credentials = {"installed": {"client_id": "test.apps.googleusercontent.com", "client_secret": "secret"}}
    assert client.post('/api/sync/credentials', json=credentials).status_code == 200
    first = client.post('/api/sync/connect').json()['authorization_url']
    state = client.get('/api/sync/status').json()
    assert state['auth_pending'] and state['authorization_url'] == first
    assert app.cloud.sync() == {'busy': True}
    assert not app.cloud.busy
    assert client.post('/api/sync/cancel-auth').status_code == 200
    state = client.get('/api/sync/status').json()
    assert not state['auth_pending'] and not state['connected']
    assert state['authorization_url'] == ''
    assert not (app.cloud.secrets_dir / 'token.json').exists()
    second = client.post('/api/sync/connect').json()['authorization_url']
    assert second != first
    client.post('/api/sync/cancel-auth')


def test_token_refresh_does_not_block_status(tmp_path, monkeypatch):
    sync = engine(tmp_path / 'words.json', tmp_path / 'secrets')
    connect_fake(sync)
    entered, release = threading.Event(), threading.Event()
    drive = FakeDrive()
    def handle(request):
        if request.url.path.endswith('/token'):
            entered.set()
            assert release.wait(5)
        return drive.handle(request)
    real_client = httpx.Client
    monkeypatch.setattr(drive_sync.httpx, 'Client', lambda **kw: real_client(transport=httpx.MockTransport(handle), **kw))
    worker = threading.Thread(target=sync.sync)
    worker.start()
    try:
        assert entered.wait(2)
        # 查询必须在网络请求结束之前完成，否则 UI 会一直等待。
        from concurrent.futures import ThreadPoolExecutor
        pool = ThreadPoolExecutor(1)
        future = pool.submit(sync.status)
        try:
            assert future.result(timeout=1)['syncing']
        finally:
            release.set()
            pool.shutdown(wait=True)
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    assert not sync.status()['syncing']


def test_switch_folder_resets_last_success_time(tmp_path):
    sync = engine(tmp_path / 'words.json', tmp_path / 'secrets')
    sync.configure_folder(str(tmp_path / 'first'))
    assert 'error' not in sync.sync()
    assert sync.status()['last_synced_at']
    sync.configure_folder(str(tmp_path / 'second'))
    assert sync.status()['last_synced_at'] is None


def test_cancelled_oauth_callback_cannot_persist_credentials(tmp_path, monkeypatch):
    from urllib.parse import urlparse, parse_qs, urlencode
    sync = engine(tmp_path / 'words.json', tmp_path / 'secrets')
    sync.import_credentials({'installed': {'client_id': 'test.apps.googleusercontent.com', 'client_secret': 'secret'}})
    entered, release = threading.Event(), threading.Event()
    real_client = httpx.Client
    def handle(request):
        if request.url.path.endswith('/token'):
            entered.set()
            assert release.wait(5)
            return httpx.Response(200, json={'access_token': 'access', 'refresh_token': 'refresh', 'expires_in': 3600})
        return httpx.Response(200, json={'user': {'permissionId': 'user', 'emailAddress': 'test@example.com'}})
    monkeypatch.setattr(drive_sync.httpx, 'Client', lambda **kw: real_client(transport=httpx.MockTransport(handle), **kw))
    query = parse_qs(urlparse(sync.begin_auth()['authorization_url']).query)
    callback = query['redirect_uri'][0] + '?' + urlencode({'state': query['state'][0], 'code': 'code'})
    def call():
        with real_client(timeout=5, trust_env=False) as browser:
            browser.get(callback)
    worker = threading.Thread(target=call)
    worker.start()
    try:
        assert entered.wait(2)
        sync.cancel_auth()
        newer = sync.begin_auth()['authorization_url']
        release.set()
        worker.join(5)
        assert not worker.is_alive()
        assert not (sync.secrets_dir / 'token.json').exists()
        assert sync.status()['authorization_url'] == newer
        assert sync.status()['auth_pending']
        assert not sync.error
    finally:
        release.set()
        sync.cancel_auth()
        worker.join(5)


@pytest.mark.parametrize('denied', [False, True])
def test_oauth_callback_completes_or_reports_denial(tmp_path, monkeypatch, denied):
    from urllib.parse import urlparse, parse_qs, urlencode
    sync = engine(tmp_path / 'words.json', tmp_path / 'secrets')
    sync.import_credentials({'installed': {'client_id': 'test.apps.googleusercontent.com', 'client_secret': 'secret'}})
    real_client = httpx.Client
    def handle(request):
        if request.url.path.endswith('/token'):
            return httpx.Response(200, json={'access_token': 'access', 'refresh_token': 'refresh', 'expires_in': 3600})
        return httpx.Response(200, json={'user': {'permissionId': 'user', 'emailAddress': 'test@example.com'}})
    monkeypatch.setattr(drive_sync.httpx, 'Client', lambda **kw: real_client(transport=httpx.MockTransport(handle), **kw))
    query = parse_qs(urlparse(sync.begin_auth()['authorization_url']).query)
    with real_client(timeout=5, trust_env=False) as browser:
        # 不合法的 state 不应结束当前授权。
        assert browser.get(query['redirect_uri'][0] + '?state=wrong&code=code').status_code == 400
        assert sync.auth_pending
        params = {'state': query['state'][0], **({'error': 'access_denied'} if denied else {'code': 'code'})}
        assert browser.get(query['redirect_uri'][0] + '?' + urlencode(params)).status_code == 200
    assert not sync.auth_pending
    assert not sync.authorization_url
    assert sync.status()['connected'] is not denied
    assert bool(sync.error) is denied
    if not denied:
        assert sync.status()['account'] == 'test@example.com'
        assert storage.read(sync.data_path())['_sync']['account'] == 'test.apps.googleusercontent.com:user'


def test_atomic_write_failure_preserves_original_and_removes_temporary_file(tmp_path):
    path = tmp_path / 'words.json'
    storage.atomic_write(path, {'words': []})
    original = path.read_bytes()

    with pytest.raises(ValueError):
        storage.atomic_write(path, {'partial': '不能留下的临时内容', 'invalid': float('nan')})

    assert path.read_bytes() == original
    assert set(tmp_path.iterdir()) == {path}


def test_atomic_writes_use_independent_temporary_files(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / 'state.json'
    barrier = threading.Barrier(2)
    original_dump = storage.json.dump

    def overlapping_dump(*args, **kwargs):
        original_dump(*args, **kwargs)
        barrier.wait(timeout=5)

    monkeypatch.setattr(storage.json, 'dump', overlapping_dump)
    with ThreadPoolExecutor(max_workers=2) as pool:
        writes = [pool.submit(storage.atomic_write, path, {'writer': i}) for i in range(2)]
        for write in writes:
            write.result(timeout=5)

    assert json.loads(path.read_text()) in ({'writer': 0}, {'writer': 1})
    assert set(tmp_path.iterdir()) == {path}


@pytest.mark.parametrize('field', ['first_review_at', 'due_at'])
def test_remote_invalid_schedule_timestamps_do_not_enter_cache(tmp_path, field):
    path = tmp_path / 'words.json'
    storage.commit(path, {'words': [word()]})
    original = path.read_bytes()
    state = storage.review_state(None, [{'id': 'first', 'rating': 3, 'at': '2026-10-18T10:00:00Z'}])
    state[field] = 'not-a-timestamp'
    operation = {**ops(path)[0], 'id': 'invalid-schedule', 'clock': 100, 'field': 'srs_base', 'value': state}

    with pytest.raises(ValueError):
        storage.merge(path, [operation])

    assert path.read_bytes() == original


@pytest.mark.parametrize('timestamp', ['2026-10-18T10:00:00Z', '2026-10-18T10:00:00+00:00', '2026-10-18T10:00:00'])
@pytest.mark.parametrize('with_optional_dates', [False, True])
def test_remote_schedule_keeps_legacy_timestamp_compatibility(tmp_path, timestamp, with_optional_dates):
    path = tmp_path / 'words.json'
    storage.commit(path, {'words': [word()]})
    state = {'d': 5.0, 's': 2.0, 'last_review_at': timestamp}
    if with_optional_dates:
        state.update(first_review_at=timestamp, due_at=timestamp)
    operation = {**ops(path)[0], 'id': 'legacy-schedule', 'clock': 100, 'field': 'srs_base', 'value': state}

    assert storage.merge(path, [operation]) == 1
    assert storage.read(path)['words'][0]['srs'] == state


def test_folder_failure_reports_changes_already_merged(tmp_path):
    path, source = tmp_path / 'local.json', tmp_path / 'remote.json'
    sync = engine(path, tmp_path / 'secrets')
    folder = tmp_path / 'drive'
    sync.configure_folder(str(folder))
    storage.commit(source, {'words': [word()]})
    remote_operations = ops(source)
    storage.atomic_write(folder / 'vocabulary-a.json', {'version': storage.VERSION, 'operations': remote_operations})
    storage.atomic_write(folder / 'vocabulary-z.json', {'version': 999, 'operations': []})

    result = sync.sync()

    assert result['error']
    assert result['pulled'] == len(remote_operations)
    assert result['pushed'] == 0
    assert storage.read(path)['words'] == storage.read(source)['words']
    assert sync.status()['last_pulled_at']
    assert not sync.status()['syncing']
