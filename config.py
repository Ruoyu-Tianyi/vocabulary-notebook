"""配置加载与校验"""
import json
import os
import threading
from pathlib import Path

CONFIG_FILE = Path("config.json")
_CONFIG: dict = {}
_AI_LOCK = threading.RLock()
DEFAULT_MODEL = "deepseek-flash"


def load_config() -> dict:
    global _CONFIG
    if _CONFIG:
        return _CONFIG

    if not CONFIG_FILE.exists():
        _CONFIG = {"provider": "deepseek", "deepseek": {"model": DEFAULT_MODEL}}
        return _CONFIG

    try:
        _CONFIG = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"config.json 格式错误：{e}")

    if not isinstance(_CONFIG, dict):
        _CONFIG = {}
        raise RuntimeError("config.json 必须是 JSON 对象")
    if _CONFIG.get("provider", "deepseek") not in ("deepseek", "ollama"):
        _CONFIG = {}
        raise RuntimeError("此版本使用 DeepSeek API，请设置 provider=deepseek")
    # Upgrade old Ollama configs in memory while retaining notebook/sync settings.
    _CONFIG["provider"] = "deepseek"

    return _CONFIG


def get_provider() -> str:
    return load_config()["provider"]


def get_deepseek_config() -> dict:
    with _AI_LOCK:
        configured = load_config().get("deepseek", {})
        path = Path(get_sync_config()["credentials_dir"]) / "deepseek.json"
        local = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
        key = os.environ.get("DEEPSEEK_API_KEY") or local.get("api_key") or configured.get("api_key", "")
        model = os.environ.get("DEEPSEEK_MODEL") or local.get("model") or configured.get("model") or DEFAULT_MODEL
        if not isinstance(key, str) or not isinstance(model, str) or not model.strip() or len(model) > 100:
            raise RuntimeError("DeepSeek 配置无效，请检查本机 API Key 和模型名称")
        return {"api_key": key.strip(), "model": model.strip()}


def get_ai_settings() -> dict:
    settings = get_deepseek_config()
    return {"provider": "deepseek", "configured": bool(settings["api_key"]), "model": settings["model"],
            "environment_key": bool(os.environ.get("DEEPSEEK_API_KEY"))}


def save_ai_settings(api_key: str, model: str):
    from sync_storage import atomic_write
    with _AI_LOCK:
        current = get_deepseek_config()
        if not isinstance(api_key, str) or len(api_key) > 1000 or any(c.isspace() for c in api_key.strip()):
            raise ValueError("API Key 格式无效")
        if not isinstance(model, str) or not model.strip() or len(model) > 100:
            raise ValueError("模型名称不能为空且不能超过 100 个字符")
        # A blank password field preserves an existing key without exposing it to the UI.
        path = Path(get_sync_config()["credentials_dir"]) / "deepseek.json"
        if not api_key.strip() and not current["api_key"]:
            raise ValueError("请填写 DeepSeek API Key")
        local = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
        local.update(model=model.strip())
        if api_key.strip():
            local["api_key"] = api_key.strip()
        atomic_write(path, local)
    return get_ai_settings()


def get_srs_config() -> dict:
    """返回间隔复习配置，并为旧版 config.json 提供安全默认值。"""
    srs = load_config().get("srs", {})
    daily_new_limit = srs.get("daily_new_limit", 20)
    if not isinstance(daily_new_limit, int) or isinstance(daily_new_limit, bool):
        raise RuntimeError("srs.daily_new_limit 必须是整数")
    if not 0 <= daily_new_limit <= 100:
        raise RuntimeError("srs.daily_new_limit 必须在 0 到 100 之间")
    return {"daily_new_limit": daily_new_limit}


def get_sync_config() -> dict:
    sync = load_config().get("sync", {})
    interval = sync.get("interval_seconds", 30)
    if type(interval) is not int or not 10 <= interval <= 3600:
        raise RuntimeError("sync.interval_seconds 必须是 10 到 3600 之间的整数")
    return {"interval_seconds": interval,
            "credentials_dir": sync.get("credentials_dir", ".secrets")}


def public_config() -> dict:
    """Expose upstream model settings without copying keys or sync credentials."""
    settings = get_ai_settings()
    return {"provider": "deepseek", "deepseek": {"model": settings["model"],
            "api_key_configured": settings["configured"], "environment_key": settings["environment_key"]}}
