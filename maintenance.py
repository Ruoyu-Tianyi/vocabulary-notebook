"""Offline update snapshots. Does not contact Drive, generate content or change data."""
from compat import getenv
import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import instance_lock


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def library_summary(path):
    if not path.exists():
        return {"words": 0, "notebooks": 0, "review_events": 0, "operations": 0, "scheduled_words": 0}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    words = data["words"]
    return {"words": len(words), "notebooks": len(data.get("notebooks", [{"id": "default"}])),
            "review_events": sum(len(word.get("review_history", [])) for word in words),
            "operations": len(data.get("_sync", {}).get("operations", {})),
            "scheduled_words": sum(bool(word.get("srs")) for word in words)}


def create_backup(data_file, config_file, secrets_dir, backup_root, revision="unknown"):
    """Require the app to be stopped, then snapshot local state without displaying secrets."""
    with instance_lock.acquire(data_file):
        summary = library_summary(data_file)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        backup = backup_root / ("update-" + stamp)
        backup.mkdir(parents=True, exist_ok=False)
        protected = [data_file, config_file]
        protected.extend(path for path in data_file.parent.glob(data_file.name + ".*")
                         if path.is_file() and path.suffix not in (".lock", ".tmp"))
        if secrets_dir.exists():
            protected.extend(path for path in secrets_dir.rglob("*") if path.is_file() and path.suffix != ".tmp")
        manifest = {"format": 1, "revision": revision, "data_file": str(data_file.resolve()),
                    "summary": summary, "files": []}
        unique = sorted({path.resolve() for path in protected if path.exists()})
        for index, source in enumerate(unique):
            relative = f"files/{index:04d}/{source.name}"
            destination = backup / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            checksum = digest(source)
            if digest(destination) != checksum:
                raise RuntimeError("备份校验失败，停止更新")
            manifest["files"].append({"source": str(source), "copy": relative, "sha256": checksum})
        (backup / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return backup


def verify_backup(backup):
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != 1:
        raise ValueError("不支持的备份格式")
    with instance_lock.acquire(Path(manifest["data_file"])):
        for entry in manifest["files"]:
            copy = (backup / entry["copy"]).resolve()
            if not copy.is_relative_to(backup.resolve()):
                raise ValueError("备份文件路径无效")
            if not copy.is_file() or digest(copy) != entry["sha256"]:
                raise RuntimeError("本地备份损坏，停止更新")
            source = Path(entry["source"])
            if not source.is_file() or digest(source) != entry["sha256"]:
                raise RuntimeError(f"更新前后的本地文件不一致，请保留现场并检查：{source.name}")
        if library_summary(Path(manifest["data_file"])) != manifest["summary"]:
            raise RuntimeError("更新前后词库与学习记录统计不一致，停止启动")
    return manifest["summary"]


def main():
    parser = argparse.ArgumentParser(description="备份并校验词汇本更新前后的本地数据；必须先停止应用")
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parent)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backup")
    verify = commands.add_parser("verify")
    verify.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()
    project = args.project.resolve()
    if args.command == "verify":
        print(json.dumps({"verified": True, "summary": verify_backup(args.backup.resolve())}))
        return
    config_file = project / "config.json"
    settings = json.loads(config_file.read_text(encoding="utf-8-sig")) if config_file.exists() else {}
    data_file = Path(getenv("VOCOVE_DATA_FILE", "words.json"))
    if not data_file.is_absolute():
        data_file = project / data_file
    secrets = Path(settings.get("sync", {}).get("credentials_dir", ".secrets"))
    if not secrets.is_absolute():
        secrets = project / secrets
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True).stdout.strip() or "unknown"
    backup = create_backup(data_file, config_file, secrets, project / ".backups", revision)
    print(json.dumps({"backup": str(backup), "revision": revision, "summary": library_summary(data_file)}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from None
