"""SPA 路由与本地启动入口不触碰词库、网络或真实配置。"""
import runpy
from pathlib import Path

import pytest
import uvicorn

import app
from tests.local_client import TestClient


@pytest.fixture
def frontend(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<!doctype html><title>isolated frontend</title>", encoding="utf-8")
    monkeypatch.setattr(app, "STATIC_DIR", tmp_path)
    return TestClient(app.app)


@pytest.mark.parametrize("path", ["/", "/review", "/notebooks", "/word/example"])
def test_frontend_routes_keep_spa_fallback(frontend, path):
    result = frontend.get(path)
    assert result.status_code == 200
    assert "isolated frontend" in result.text


@pytest.mark.parametrize("path", ["/api", "/api/unknown-route", "/assets/missing.js"])
def test_unknown_api_and_asset_paths_are_not_successful_html(frontend, path):
    result = frontend.get(path)
    assert result.status_code == 404
    assert "isolated frontend" not in result.text


def test_direct_start_uses_loopback_and_handles_partial_frontend_build(tmp_path, monkeypatch):
    # 模拟只生成 index.html、assets 尚不存在的构建中间状态。
    script = Path(app.__file__).resolve()
    (tmp_path / "frontend" / "dist").mkdir(parents=True)
    (tmp_path / "frontend" / "dist" / "index.html").write_text("isolated startup", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    launches = []
    monkeypatch.setattr(uvicorn, "run", lambda application, **options: launches.append((application, options)))
    runpy.run_path(str(script), run_name="__main__")
    assert len(launches) == 1
    application, options = launches[0]
    assert options["host"] == "127.0.0.1"
    assert options["proxy_headers"] is False
    client = TestClient(application)
    assert client.get("/").text == "isolated startup"
    assert client.get("/assets/missing.js").status_code == 404
    assert not (tmp_path / "words.json").exists()
