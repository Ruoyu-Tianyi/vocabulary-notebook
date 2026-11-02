"""配置校验失败与原子保存只使用临时文件。"""
import json

import pytest

import config


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", path)
    monkeypatch.setattr(config, "_CONFIG", {})
    return path


def valid_config():
    return {"provider": "ollama", "ollama": {"url": "http://localhost:11434/api/generate", "model": "test"},
            "srs": {"daily_new_limit": 17}}


@pytest.mark.parametrize("data", [
    [], "config", {"provider": "unknown"},
    {"provider": "ollama", "ollama": {}},
    {"provider": "ollama", "ollama": {"url": "http://localhost", "model": []}},
    {"provider": "deepseek", "deepseek": {"api_key": "test-only", "model": " "}},
    {**valid_config(), "deepseek": None},
    {**valid_config(), "srs": []},
    {**valid_config(), "sync": "invalid"},
])
def test_invalid_config_is_never_cached_and_can_be_repaired(config_file, data):
    config_file.write_text(json.dumps(data), encoding="utf-8")
    for _ in range(2):
        with pytest.raises(RuntimeError):
            config.load_config()
        assert config._CONFIG == {}
    config_file.write_text(json.dumps(valid_config()), encoding="utf-8")
    assert config.get_provider() == "ollama"
    assert config.get_srs_config() == {"daily_new_limit": 17}


def test_missing_and_malformed_files_remain_retryable(config_file):
    with pytest.raises(RuntimeError, match="配置文件不存在"):
        config.load_config()
    config_file.write_text("{", encoding="utf-8")
    with pytest.raises(RuntimeError, match="格式错误"):
        config.load_config()
    assert config._CONFIG == {}


def test_failed_atomic_replace_preserves_disk_and_cached_settings(config_file, monkeypatch):
    original = valid_config()
    config_file.write_text(json.dumps(original), encoding="utf-8")
    before = config_file.read_bytes()
    assert config.load_config() == original

    def fail_replace(*_args):
        raise OSError("test write failure")

    monkeypatch.setattr(config.os, "replace", fail_replace)
    with pytest.raises(OSError):
        config.save_model_config("ollama", {**original["ollama"], "model": "changed"}, {})
    assert config_file.read_bytes() == before
    assert config.get_ollama_config() == original["ollama"]
    assert not list(config_file.parent.glob(".config-*"))


def test_invalid_model_save_never_replaces_valid_settings(config_file):
    original = valid_config()
    config_file.write_text(json.dumps(original), encoding="utf-8")
    before = config_file.read_bytes()
    with pytest.raises(ValueError):
        config.save_model_config("other", original["ollama"], {})
    with pytest.raises(ValueError):
        config.save_model_config("ollama", {"url": "http://localhost", "model": 123}, {})
    assert config_file.read_bytes() == before
    assert config.load_config() == original
