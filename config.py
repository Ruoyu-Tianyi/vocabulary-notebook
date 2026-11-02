"""配置加载与校验"""
import json
import copy
import os
import tempfile
import threading
from pathlib import Path

import model_providers

CONFIG_FILE = Path("config.json")
_CONFIG: dict = {}
_CONFIG_LOCK = threading.RLock()


def _section(data: dict, name: str) -> dict:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise RuntimeError(f"{name} 必须是 JSON 对象")
    return value


def _validate_model_config(data: dict) -> None:
    if not isinstance(data, dict):
        raise RuntimeError("config.json 顶层必须是 JSON 对象")
    for name in ("ollama", "deepseek", "srs", "sync"):
        _section(data, name)
    provider = data.get("provider", "")
    if provider not in model_providers.PROVIDERS:
        raise RuntimeError("不支持的模型供应商")
    values = provider_values(data, provider)
    if not isinstance(values.get("model"), str) or not values["model"].strip():
        raise RuntimeError("模型名称不能为空")
    try:
        resolved = model_providers.resolve(provider, values)
    except (ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError("模型地址或配置格式不正确") from exc
    if provider not in ("ollama", "custom") and not resolved["api_key"]:
        raise RuntimeError("请填写 API Key 或设置供应商环境变量")


def provider_values(data, provider):
    if provider in ("ollama", "deepseek"):
        return _section(data, provider)
    return _section(_section(data, "providers"), provider)


def get_model_config(provider=None):
    provider = provider or get_provider()
    return model_providers.resolve(provider, provider_values(load_config(), provider))


def load_config() -> dict:
    global _CONFIG
    with _CONFIG_LOCK:
        if _CONFIG:
            return _CONFIG
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RuntimeError(f"配置文件不存在：{CONFIG_FILE}，请参考文档创建") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"config.json 格式错误：{exc}") from exc
        # 校验通过后才发布缓存；失败后修正文件可直接重试。
        _validate_model_config(data)
        _CONFIG = data
        return _CONFIG


def get_provider() -> str:
    return load_config()["provider"]


def get_ollama_config() -> dict:
    return load_config().get("ollama", {})


def get_deepseek_config() -> dict:
    return load_config().get("deepseek", {})


def get_srs_config() -> dict:
    """返回间隔复习配置，并为旧版 config.json 提供安全默认值。"""
    srs = _section(load_config(), "srs")
    daily_new_limit = srs.get("daily_new_limit", 20)
    if not isinstance(daily_new_limit, int) or isinstance(daily_new_limit, bool):
        raise RuntimeError("srs.daily_new_limit 必须是整数")
    if not 0 <= daily_new_limit <= 100:
        raise RuntimeError("srs.daily_new_limit 必须在 0 到 100 之间")
    return {"daily_new_limit": daily_new_limit}


def get_sync_config() -> dict:
    sync = _section(load_config(), "sync")
    interval = sync.get("interval_seconds", 30)
    if type(interval) is not int or not 10 <= interval <= 3600:
        raise RuntimeError("sync.interval_seconds 必须是 10 到 3600 之间的整数")
    return {"interval_seconds": interval,
            "credentials_dir": sync.get("credentials_dir", ".secrets")}


def last_builtin_provider(data):
    builtins = [name for name in model_providers.PROVIDERS if name != "custom"]
    if data.get("provider") in builtins:
        return data["provider"]
    if data.get("last_builtin_provider") in builtins:
        return data["last_builtin_provider"]
    return next((name for name in builtins if provider_values(data, name).get("model")), builtins[0])


def public_config() -> dict:
    data = load_config()
    profiles = {}
    for provider, preset in model_providers.PROVIDERS.items():
        values = copy.deepcopy(provider_values(data, provider))
        key = values.pop("api_key", "")
        values.update(api_key_configured=bool(key),
                      env_key_configured=bool(os.environ.get(preset["env_key"], "").strip()))
        values["base_url"] = values.get("base_url") or values.get("url") or preset["base_url"]
        if provider == "ollama":
            values["base_url"] = model_providers.normalize_url(values["base_url"], "ollama")
        values["protocol"] = values.get("protocol", preset["protocol"]) if provider == "custom" else preset["protocol"]
        values.setdefault("model", "")
        values.setdefault("timeout", 120)
        profiles[provider] = values
    return {"provider": data["provider"], "last_builtin_provider": last_builtin_provider(data), "providers": profiles,
            "catalog": list(model_providers.PROVIDERS.values()),
            "ollama": profiles["ollama"], "deepseek": profiles["deepseek"]}


def save_model_config(provider, ollama, deepseek, providers=None) -> dict:
    """原子落盘成功后才替换内存配置，保留其他业务设置。"""
    global _CONFIG
    with _CONFIG_LOCK:
        if provider not in model_providers.PROVIDERS:
            raise ValueError("不支持的模型供应商")
        data = copy.deepcopy(load_config())
        previous_builtin = last_builtin_provider(data)
        changes = providers if providers is not None else {"ollama": ollama, "deepseek": deepseek}
        for name, values in changes.items():
            if name not in model_providers.PROVIDERS or not isinstance(values, dict):
                raise ValueError("模型配置格式不正确")
            values = {key: value.strip() if isinstance(value, str) else value for key, value in values.items()}
            old = provider_values(data, name)
            merged = {**old, **values}
            # 空值表示沿用；清除动作显式标记，避免浏览器掩码覆盖密钥。
            if values.get("clear_api_key") and not values.get("api_key"):
                merged["api_key"] = ""
            elif not values.get("api_key"):
                merged["api_key"] = old.get("api_key", "")
            for key in ("clear_api_key", "api_key_configured", "env_key_configured"):
                merged.pop(key, None)
            preset = model_providers.PROVIDERS[name]
            protocol = merged.get("protocol", preset["protocol"]) if name == "custom" else preset["protocol"]
            merged["protocol"] = protocol
            url = merged.get("base_url") or merged.get("url") or preset["base_url"]
            if url:
                merged["base_url"] = model_providers.normalize_url(url, protocol)
            if name == "ollama" and merged.get("base_url"):
                merged["url"] = model_providers.normalize_url(merged["base_url"], "ollama") + "/api/generate"
            if name in ("ollama", "deepseek"):
                data[name] = merged
            else:
                data.setdefault("providers", {})[name] = merged
        data["last_builtin_provider"] = provider if provider != "custom" else previous_builtin
        data["provider"] = provider
        try:
            _validate_model_config(data)
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc
        fd, name = tempfile.mkstemp(dir=CONFIG_FILE.resolve().parent, prefix=".config-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, CONFIG_FILE)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        _CONFIG = data
        return public_config()
