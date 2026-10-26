"""在旧实例停止后复制桌面资料，保留原数据。"""
from contextlib import nullcontext
import ctypes
import errno
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

import instance_lock


class MigrationError(RuntimeError):
    """可以直接向用户显示，不含文件内容或凭据的迁移错误。"""


_ELECTRON_LOCKS = {"SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"}
_JUNCTION_TAG = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)


def _is_link_or_junction(path):
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    # Python 3.11 的 is_symlink 不识别 NTFS junction，不能让目录遍历跟随它。
    return (stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_reparse_tag", 0) == _JUNCTION_TAG)


def _check_symlinks(root):
    for folder, directories, files in os.walk(root, followlinks=False):
        folder = Path(folder)
        if folder == root:
            directories[:] = [name for name in directories if name not in _ELECTRON_LOCKS]
            files = [name for name in files if name not in _ELECTRON_LOCKS]
        if any(_is_link_or_junction(folder / name) for name in directories + files):
            raise MigrationError("旧数据目录包含符号链接或目录联接，自动迁移已停止；请使用完整备份导入或手动整理链接。")


def _publish_directory(source, destination):
    """原子发布且不替换已有目录，避免其他进程恰好创建目标时覆盖它。"""
    if sys.platform == "win32":
        os.rename(source, destination)
        return
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = library.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        arguments = (os.fsencode(source), os.fsencode(destination), 0x00000004)
    elif hasattr(library, "renameat2"):
        rename = library.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        arguments = (-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    else:
        raise MigrationError("当前系统不支持安全的目录迁移，请使用完整备份导入。")
    rename.restype = ctypes.c_int
    if rename(*arguments) != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise FileExistsError(error, "目标目录已存在")
        raise OSError(error, "无法发布迁移目录")


def migrate_user_data(old, new):
    source, destination = Path(old), Path(new)
    if not source.is_absolute() or not destination.is_absolute():
        raise MigrationError("数据迁移需要旧目录和新目录的绝对路径。")
    if _is_link_or_junction(source) or _is_link_or_junction(destination):
        raise MigrationError("数据目录不能是符号链接或目录联接，请使用完整备份导入。")
    source, destination = source.resolve(), destination.resolve()
    if source == destination or source.parent != destination.parent:
        raise MigrationError("旧目录和新目录必须位于同一父目录，且名称不同。")
    if destination.exists():
        if not destination.is_dir():
            raise MigrationError("新的数据目录位置已被文件占用，请先检查该位置。")
        return "existing"
    if not source.exists():
        return "absent"
    if not source.is_dir():
        raise MigrationError("旧数据位置不是文件夹，无法自动迁移。")
    _check_symlinks(source)
    guard = destination.parent / f".{destination.name}.migration"
    if _is_link_or_junction(guard.with_suffix(".migration.lock")):
        raise MigrationError("迁移锁位置包含符号链接或目录联接，请先检查数据目录。")
    try:
        migration_lock = instance_lock.acquire(guard)
    except RuntimeError as exc:
        raise MigrationError("另一次资料迁移正在进行，请等待完成或关闭其他应用实例后重试。") from exc
    # OS 会在进程异常退出时释放锁。保留 1 字节锁文件，避免删文件造成两个 inode 同时持锁。
    with migration_lock:
        staging = None
        try:
            if destination.exists():
                return "existing"
            try:
                cache_lock = (instance_lock.acquire(source / "data" / "words.json")
                              if (source / "data").is_dir() else nullcontext())
            except RuntimeError as exc:
                raise MigrationError("旧词库仍被其他进程使用，请完全退出旧应用和本地服务后重试。") from exc
            with cache_lock:
                staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}-migration-", dir=destination.parent))

                def ignore(folder, _names):
                    folder = Path(folder)
                    if folder == source:
                        return _ELECTRON_LOCKS
                    return {"words.json.lock"} if folder == source / "data" else set()

                # 复制链接本身而不跟随；发布前再检查，防止复制过程中新增链接越出来源目录。
                shutil.copytree(source, staging, dirs_exist_ok=True, symlinks=True, ignore=ignore)
                _check_symlinks(staging)
                try:
                    _publish_directory(staging, destination)
                except FileExistsError:
                    return "existing"
                staging = None
            return "migrated"
        finally:
            if staging is not None:
                shutil.rmtree(staging)
