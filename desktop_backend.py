"""Electron 专用入口：隔离数据、临时端口和随父进程结束的服务。"""
import asyncio
import json
import os
from pathlib import Path
import re
import socket
import sys
import threading

from compat import getenv


def prepare_environment() -> Path:
    token = getenv("VOCOVE_DESKTOP_TOKEN", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token):
        raise RuntimeError("桌面入口需要至少 32 位随机会话令牌")
    data_value = getenv("VOCOVE_DESKTOP_DATA_DIR", "")
    if not data_value or not Path(data_value).is_absolute():
        raise RuntimeError("桌面入口需要独立数据目录的绝对路径")
    data_dir = Path(data_value).resolve()
    # PyInstaller 将资源放在 __file__ 同级；安装目录始终只读。
    static_dir = Path(getenv(
        "VOCOVE_DESKTOP_STATIC_DIR", str(Path(__file__).resolve().parent / "frontend" / "dist")
    )).resolve()
    if not (static_dir / "index.html").is_file():
        raise RuntimeError("桌面前端资源缺失，请重新构建应用")
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    default_config = {
        "provider": "ollama",
        "ollama": {"url": "http://localhost:11434/api/generate", "model": "gemma4:26b"},
        "deepseek": {"api_key": "", "model": ""},
        "srs": {"daily_new_limit": 20},
        "sync": {"interval_seconds": 30, "credentials_dir": ".secrets"},
    }
    try:
        descriptor = os.open(data_dir / "config.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(default_config, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    # 显式覆盖继承的网页环境，防止桌面实例意外操作原项目词库。
    os.environ["VOCOVE_DATA_FILE"] = str(data_dir / "words.json")
    os.environ["VOCOVE_DESKTOP_STATIC_DIR"] = str(static_dir)
    os.chdir(data_dir)
    return data_dir


def _watch_parent(server, loop):
    while True:
        line = sys.stdin.readline()
        if not line or line.strip() == "shutdown":
            try:
                loop.call_soon_threadsafe(setattr, server, "should_exit", True)
            except RuntimeError:
                pass  # 服务已退出，事件循环也已关闭。
            return


async def serve(listener, application):
    import uvicorn

    server = uvicorn.Server(uvicorn.Config(
        application, host="127.0.0.1", port=listener.getsockname()[1],
        loop="asyncio", http="h11", ws="none", log_level="warning", access_log=False,
        proxy_headers=False, timeout_graceful_shutdown=5,
    ))
    loop = asyncio.get_running_loop()
    threading.Thread(target=_watch_parent, args=(server, loop), daemon=True).start()
    task = asyncio.create_task(server.serve(sockets=[listener]))
    while not server.started and not task.done():
        await asyncio.sleep(0.025)
    if server.started and not server.should_exit:
        print(json.dumps({"type": "ready", "url": os.environ["VOCOVE_DESKTOP_ORIGIN"]}), flush=True)
    await task
    if not server.started:
        raise RuntimeError("桌面后端未能完成启动")


def main():
    if len(sys.argv) > 1:
        if len(sys.argv) != 4 or sys.argv[1] != "--migrate-user-data":
            print("Vocove 后端启动参数无效", file=sys.stderr)
            return 2
        from desktop_migration import MigrationError, migrate_user_data

        try:
            status = migrate_user_data(sys.argv[2], sys.argv[3])
        except MigrationError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except Exception:
            print("资料迁移未完成，请检查目录权限和可用空间；旧目录保持不变，可修复后重试。", file=sys.stderr)
            return 1
        print(json.dumps({"type": "migration", "status": status}), flush=True)
        return 0
    prepare_environment()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        os.environ["VOCOVE_DESKTOP_ORIGIN"] = f"http://127.0.0.1:{listener.getsockname()[1]}"
        # 必须在路径和 Origin 确定后导入，避免读取项目目录的配置或词库。
        import app

        asyncio.run(serve(listener, app.app))


if __name__ == "__main__":
    raise SystemExit(main())
