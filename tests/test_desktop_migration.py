"""品牌迁移仅使用合成资料，验证原目录保留、并发锁和失败后的可重试性。"""
import errno
import json
import os
from pathlib import Path
import queue
import stat
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

import desktop_migration as migration
import instance_lock


@pytest.fixture
def profile(tmp_path):
    source = tmp_path / "previous-profile"
    (source / "data" / ".secrets").mkdir(parents=True)
    (source / "data" / "words.json").write_bytes(b"synthetic library: not parsed")
    (source / "data" / "config.json").write_bytes(b"synthetic settings: not parsed")
    (source / "data" / ".secrets" / "token.json").write_bytes(b"synthetic credentials")
    (source / "desktop-preferences.json").write_text('{"theme":"light"}', encoding="utf-8")
    (source / "cache").mkdir()
    (source / "cache" / "session").write_bytes(b"synthetic browser session")
    instance_lock.acquire(source / "data" / "words.json").close()
    return source, tmp_path / "Vocove"


def contents(directory):
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


def migration_lock_file(destination):
    return destination.parent / f".{destination.name}.migration.lock"


def wait_for_lock_release(lock_files, timeout=5):
    deadline = time.monotonic() + timeout
    while True:
        try:
            return [path.read_bytes() for path in lock_files]
        except PermissionError as exc:
            remaining = deadline - time.monotonic()
            if sys.platform != "win32" or exc.errno != errno.EACCES or remaining <= 0:
                raise
            # Windows venv redirector 退出不等于其子进程及 OS 字节锁均已回收。
            # 只等待两个已知锁的可读条件；超时仍失败，不重试迁移或其他异常。
            time.sleep(min(0.01, remaining))


def test_lock_release_wait_observes_release_within_deadline(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    now = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    monkeypatch.setattr(time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))

    def read_lock():
        if now[0] < 0.01:
            raise PermissionError(errno.EACCES, "synthetic held byte lock")
        return b"0"

    lock = SimpleNamespace(read_bytes=read_lock)
    assert wait_for_lock_release([lock], timeout=0.02) == [b"0"]
    assert now[0] == 0.01


@pytest.mark.parametrize("platform,error_number", [
    ("win32", errno.EACCES), ("win32", errno.EPERM), ("darwin", errno.EACCES),
])
def test_lock_release_wait_stops_at_deadline_or_unrelated_error(monkeypatch, platform, error_number):
    monkeypatch.setattr(sys, "platform", platform)
    now = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    monkeypatch.setattr(time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))

    def read_lock():
        raise PermissionError(error_number, "synthetic denied read")

    with pytest.raises(PermissionError):
        wait_for_lock_release([SimpleNamespace(read_bytes=read_lock)], timeout=0.02)
    assert now[0] == (0.02 if platform == "win32" and error_number == errno.EACCES else 0)


def test_copy_preserves_source_and_complete_profile_except_running_locks(profile):
    source, destination = profile
    (source / "SingletonCookie").write_bytes(b"running instance marker")
    (source / "lockfile").write_bytes(b"Windows instance lock")
    (source / "cache" / "lockfile").write_bytes(b"nested user file is retained")
    before = contents(source)
    assert migration.migrate_user_data(source, destination) == "migrated"
    assert contents(source) == before
    assert contents(destination) == {
        key: value for key, value in before.items()
        if key not in {"SingletonCookie", "lockfile", "data/words.json.lock"}
    }
    assert migration.migrate_user_data(source, destination) == "existing"
    assert set(source.parent.iterdir()) == {source, destination, migration_lock_file(destination)}
    assert migration_lock_file(destination).read_bytes() == b"0"


def test_existing_destination_is_never_merged_or_overwritten(profile):
    source, destination = profile
    destination.mkdir()
    (destination / "keep").write_bytes(b"new profile contents")
    assert migration.migrate_user_data(source, destination) == "existing"
    assert contents(destination) == {"keep": b"new profile contents"}


def test_absent_source_creates_nothing(tmp_path):
    assert migration.migrate_user_data(tmp_path / "absent", tmp_path / "Vocove") == "absent"
    assert list(tmp_path.iterdir()) == []


def test_active_library_lock_blocks_migration_then_allows_retry(profile):
    source, destination = profile
    with instance_lock.acquire(source / "data" / "words.json"):
        with pytest.raises(migration.MigrationError, match="仍被其他进程使用"):
            migration.migrate_user_data(source, destination)
    assert not destination.exists()
    assert set(source.parent.iterdir()) == {source, migration_lock_file(destination)}
    assert migration.migrate_user_data(source, destination) == "migrated"


def test_migration_guard_prevents_two_helpers_from_publishing(profile):
    source, destination = profile
    guard = destination.parent / f".{destination.name}.migration"
    with instance_lock.acquire(guard):
        with pytest.raises(migration.MigrationError, match="另一次资料迁移"):
            migration.migrate_user_data(source, destination)
    assert not destination.exists()
    assert migration_lock_file(destination).read_bytes() == b"0"
    assert migration.migrate_user_data(source, destination) == "migrated"


def test_failed_copy_removes_only_its_own_staging_and_can_be_retried(profile, monkeypatch):
    source, destination = profile
    before = contents(source)
    copytree = migration.shutil.copytree

    def fail_copy(_source, staging, **_kwargs):
        (staging / "partial").write_bytes(b"partial copy")
        raise OSError("simulated disk failure")

    monkeypatch.setattr(migration.shutil, "copytree", fail_copy)
    with pytest.raises(OSError, match="simulated"):
        migration.migrate_user_data(source, destination)
    assert contents(source) == before
    assert set(source.parent.iterdir()) == {source, migration_lock_file(destination)}
    monkeypatch.setattr(migration.shutil, "copytree", copytree)
    assert migration.migrate_user_data(source, destination) == "migrated"


def test_terminated_helper_releases_lock_and_retry_does_not_touch_abandoned_staging(profile):
    source, destination = profile
    before = contents(source)
    script = """
import sys
import time
from pathlib import Path
import desktop_migration as migration

def interrupted_copy(source, staging, **kwargs):
    (Path(staging) / 'partial').write_bytes(b'synthetic interrupted copy')
    print('copy-started', flush=True)
    while True:
        time.sleep(1)

migration.shutil.copytree = interrupted_copy
migration.migrate_user_data(sys.argv[1], sys.argv[2])
"""
    process = subprocess.Popen([sys.executable, "-u", "-c", script, str(source), str(destination)],
                               cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    lines = queue.Queue()
    threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
    try:
        assert lines.get(timeout=10).strip() == "copy-started"
        abandoned = next(source.parent.glob(f".{destination.name}-migration-*"))
        process.terminate()
        process.wait(timeout=10)
        assert not destination.exists()
        assert wait_for_lock_release([
            migration_lock_file(destination), source / "data" / "words.json.lock",
        ]) == [b"0", b"0"]
        assert migration.migrate_user_data(source, destination) == "migrated"
        assert contents(source) == before
        assert contents(abandoned) == {"partial": b"synthetic interrupted copy"}
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()


def test_atomic_publish_cannot_replace_even_an_empty_directory(tmp_path):
    staging, destination = tmp_path / "staging", tmp_path / "destination"
    staging.mkdir()
    (staging / "new").write_bytes(b"new")
    destination.mkdir()
    with pytest.raises(FileExistsError):
        migration._publish_directory(staging, destination)
    assert list(destination.iterdir()) == []
    assert (staging / "new").read_bytes() == b"new"


@pytest.mark.parametrize("kind", ["source", "content", "cache-lock"])
def test_symlinks_are_rejected_without_following_them(profile, tmp_path, kind):
    source, destination = profile
    external = tmp_path / "outside"
    external.mkdir()
    (external / "untouched").write_bytes(b"do not follow")
    if kind == "source":
        link = tmp_path / "source-link"
    elif kind == "cache-lock":
        link = source / "data" / "words.json.lock"
        link.unlink()
    else:
        link = source / "content-link"
    try:
        link.symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("当前 Windows 账号不允许创建符号链接")
    with pytest.raises(migration.MigrationError, match="符号链接"):
        migration.migrate_user_data(link if kind == "source" else source, destination)
    assert not destination.exists()
    assert contents(external) == {"untouched": b"do not follow"}


@pytest.mark.parametrize("kind", ["source", "destination", "content"])
def test_windows_junction_metadata_is_rejected_before_resolution_or_traversal(profile, monkeypatch, kind):
    source, destination = profile
    junction = {"source": source, "destination": destination, "content": source / "junction"}[kind]
    if kind == "content":
        junction.mkdir()
    original_lstat = Path.lstat

    def lstat(path):
        if path == junction:
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_reparse_tag=0xA0000003)
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", lstat)
    if kind in ("source", "destination"):
        monkeypatch.setattr(Path, "resolve", lambda _path: pytest.fail("不得解析 junction 根目录"))
    else:
        scandir = migration.os.scandir

        def guarded_scandir(path):
            if Path(path) == junction:
                pytest.fail("不得遍历 junction 指向的目录")
            return scandir(path)

        monkeypatch.setattr(migration.os, "scandir", guarded_scandir)
    with pytest.raises(migration.MigrationError, match="目录联接"):
        migration.migrate_user_data(source, destination)
    assert not destination.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS junction 需要 Windows 原生环境")
@pytest.mark.parametrize("kind", ["source", "content"])
def test_real_windows_junction_is_rejected_without_copying_its_target(profile, tmp_path, kind):
    source, destination = profile
    external = tmp_path / "outside-profile"
    external.mkdir()
    (external / "untouched").write_bytes(b"synthetic external content")
    junction = tmp_path / "source-junction" if kind == "source" else source / "nested-junction"
    result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(junction), str(external)],
                            capture_output=True, timeout=10)
    if result.returncode != 0:
        pytest.skip("当前 Windows 环境不允许创建目录联接")
    try:
        with pytest.raises(migration.MigrationError, match="目录联接"):
            migration.migrate_user_data(junction if kind == "source" else source, destination)
        assert not destination.exists()
        assert contents(external) == {"untouched": b"synthetic external content"}
    finally:
        # rmdir 仅移除本测试建立的联接，不进入或删除它指向的目录。
        os.rmdir(junction)


@pytest.mark.parametrize("target", ["same", "nested", "different-parent"])
def test_migration_requires_distinct_sibling_directories(profile, target):
    source, _destination = profile
    destination = {"same": source, "nested": source / "Vocove",
                   "different-parent": source.parent / "other" / "Vocove"}[target]
    with pytest.raises(migration.MigrationError, match="同一父目录"):
        migration.migrate_user_data(source, destination)


def test_command_runs_without_desktop_session_and_reports_only_status(profile):
    source, destination = profile
    environment = {**os.environ, "VOCOVE_DESKTOP_TOKEN": ""}
    entry = Path(__file__).resolve().parents[1] / "desktop_backend.py"
    result = subprocess.run([sys.executable, str(entry), "--migrate-user-data", str(source), str(destination)],
                            text=True, encoding="utf-8", capture_output=True, timeout=15, env=environment)
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"type": "migration", "status": "migrated"}
    assert result.stderr == ""
