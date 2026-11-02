"""每个测试使用独立配置，不依赖开发者机器上的模型或学习设置。"""
import json

import pytest

import config


@pytest.fixture(autouse=True)
def isolated_default_config(tmp_path_factory, monkeypatch):
    # 与用例的 tmp_path 分离，保留缺失文件、临时文件清理等断言的独立性。
    directory = tmp_path_factory.mktemp("default-settings")
    path = directory / "config.json"
    path.write_text(json.dumps({
        "provider": "ollama",
        "ollama": {"url": "http://127.0.0.1:9/api/generate", "model": "test-only"},
        "srs": {"daily_new_limit": 20},
        "sync": {"interval_seconds": 30, "credentials_dir": str(directory / ".secrets")},
    }), encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_FILE", path)
    monkeypatch.setattr(config, "_CONFIG", {})
