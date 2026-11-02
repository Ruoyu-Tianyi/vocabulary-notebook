"""桌面入口只操作临时目录，网络请求限于本测试创建的回环服务。"""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

import httpx
import pytest

import app
import desktop_backend
from tests.local_client import TestClient


TOKEN = "isolated-desktop-test-token-0123456789"
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def desktop_environment(tmp_path, monkeypatch):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("isolated desktop frontend", encoding="utf-8")
    (static / "assets" / "test.js").write_text("console.log('isolated')", encoding="utf-8")
    data = tmp_path / "desktop-data"
    monkeypatch.setenv("VOCOVE_DESKTOP_TOKEN", TOKEN)
    monkeypatch.setenv("VOCOVE_DESKTOP_DATA_DIR", str(data))
    monkeypatch.setenv("VOCOVE_DESKTOP_STATIC_DIR", str(static))
    monkeypatch.setenv("VOCOVE_DATA_FILE", str(tmp_path / "must-not-be-used.json"))
    monkeypatch.chdir(tmp_path)
    return data


def test_first_run_is_isolated_and_never_overwrites_configuration(desktop_environment):
    data = desktop_backend.prepare_environment()
    assert data == desktop_environment
    assert Path.cwd() == data
    assert os.environ["VOCOVE_DATA_FILE"] == str(data / "words.json")
    config_path = data / "config.json"
    settings = json.loads(config_path.read_text(encoding="utf-8"))
    assert settings["provider"] == "ollama"
    assert settings["ollama"]["model"] == "gemma4:26b"
    assert settings["deepseek"]["api_key"] == ""
    assert settings["sync"]["credentials_dir"] == ".secrets"
    assert not (data / "words.json").exists()
    config_path.write_text("intentionally invalid existing configuration", encoding="utf-8")
    desktop_backend.prepare_environment()
    assert config_path.read_text(encoding="utf-8") == "intentionally invalid existing configuration"


@pytest.mark.parametrize("key,value", [
    ("VOCOVE_DESKTOP_TOKEN", ""),
    ("VOCOVE_DESKTOP_TOKEN", "short-token"),
    ("VOCOVE_DESKTOP_TOKEN", "含有非ASCII" * 10),
    ("VOCOVE_DESKTOP_DATA_DIR", "relative-directory"),
    ("VOCOVE_DESKTOP_STATIC_DIR", "/nonexistent-desktop-assets"),
])
def test_invalid_launch_fails_before_creating_data(desktop_environment, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError):
        desktop_backend.prepare_environment()
    assert not desktop_environment.exists()


@pytest.mark.parametrize("path", ["/", "/assets/test.js", "/api/desktop/health", "/api/events"])
def test_desktop_auth_covers_every_route(monkeypatch, path):
    monkeypatch.setattr(app, "_DESKTOP_TOKEN", TOKEN)
    client = TestClient(app.app)
    assert client.get(path).status_code == 403
    assert client.get(path, headers={"X-Vocove-Desktop-Token": "wrong"}).status_code == 403
    remote = TestClient(app.app, peer="192.0.2.1")
    assert remote.get(path, headers={"X-Vocove-Desktop-Token": TOKEN}).status_code == 403


def test_web_mode_has_no_desktop_health_endpoint(monkeypatch):
    monkeypatch.setattr(app, "_DESKTOP_TOKEN", "")
    assert TestClient(app.app).get("/api/desktop/health").status_code == 404


@pytest.mark.parametrize("shutdown", ["command", "parent-eof"])
def test_real_desktop_launch_origin_and_shutdown(desktop_environment, shutdown):
    process = subprocess.Popen(
        [sys.executable, "-u", str(ROOT / "desktop_backend.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", env=os.environ.copy(),
    )
    lines = queue.Queue()

    def collect_output():
        for line in process.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=collect_output, daemon=True).start()
    try:
        output = []
        while True:
            line = lines.get(timeout=20)
            assert line is not None, "backend exited before ready: " + "".join(output)
            output.append(line)
            if line.startswith('{"type": "ready"'):
                origin = json.loads(line)["url"]
                break
        assert origin.startswith("http://127.0.0.1:")
        with httpx.Client(base_url=origin, timeout=5, trust_env=False) as client:
            assert client.get("/api/desktop/health").status_code == 403
            headers = {"X-Vocove-Desktop-Token": TOKEN}
            assert client.get("/api/desktop/health", headers=headers).json() == {"status": "ok"}
            assert client.get("/", headers=headers).text == "isolated desktop frontend"
            assert client.get("/assets/test.js", headers=headers).status_code == 200
            assert client.get("/api/events").status_code == 403
            with client.stream("GET", "/api/events", headers=headers) as events:
                assert events.status_code == 200
                assert next(events.iter_lines()) == ": connected"
            assert client.post("/api/notebooks", headers={**headers, "Origin": "https://example.com"},
                               json={"name": "rejected"}).status_code == 403
            wrong_port = "http://127.0.0.1:1"
            assert client.post("/api/notebooks", headers={**headers, "Origin": wrong_port},
                               json={"name": "rejected"}).status_code == 403
            created = client.post("/api/notebooks", headers={**headers, "Origin": origin},
                                  json={"name": "isolated desktop book"})
            assert created.status_code == 200
        assert (desktop_environment / "words.json").is_file()
        assert not (desktop_environment.parent / "must-not-be-used.json").exists()
        if shutdown == "command":
            process.stdin.write("shutdown\n")
            process.stdin.flush()
        else:
            process.stdin.close()
        assert process.wait(timeout=12) == 0
        # 正常退出应释放词库锁，允许下一次启动。
        app.instance_lock.acquire(desktop_environment / "words.json").close()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if not process.stdin.closed:
            process.stdin.close()
        process.stdout.close()


def test_existing_invalid_configuration_is_not_replaced_or_announced_ready(desktop_environment):
    desktop_environment.mkdir()
    path = desktop_environment / "config.json"
    path.write_text("invalid existing settings", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-u", str(ROOT / "desktop_backend.py")],
        input="", capture_output=True, text=True, encoding="utf-8", timeout=15,
        env=os.environ.copy(),
    )
    assert result.returncode != 0
    assert '"type": "ready"' not in result.stdout
    assert path.read_text(encoding="utf-8") == "invalid existing settings"
    assert not (desktop_environment / "words.json").exists()
