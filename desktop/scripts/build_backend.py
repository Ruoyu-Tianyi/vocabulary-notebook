"""在本机原生平台冻结后端；产物全部留在当前 worktree。"""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", choices=("x64", "arm64"), required=True)
    args = parser.parse_args()
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine().lower())
    if args.arch != arch:
        raise SystemExit("Python 与 Node 架构不一致，请使用同架构解释器，避免生成不可运行的安装包。")
    root = Path(__file__).resolve().parents[2]
    build = root / "desktop" / "build"
    env = {**os.environ, "PYINSTALLER_CONFIG_DIR": str(build / "pyinstaller-cache")}
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--distpath", str(build / "backend"), "--workpath", str(build / "pyinstaller"),
        str(root / "desktop" / "backend.spec"),
    ], cwd=root, env=env, check=True)
    (build / "backend" / "target.json").write_text(json.dumps({
        "platform": sys.platform, "arch": arch,
    }) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
