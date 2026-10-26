"""One process per local cache. The two computers use separate local caches."""
from pathlib import Path


def acquire(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.with_suffix(path.suffix + ".lock").open("a+b")
    try:
        stream.seek(0)
        if stream.read(1) == b"":
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        import os
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        stream.close()
        raise RuntimeError("这个本地词库已被另一个 Vocove 进程打开，请先关闭原窗口") from exc
    return stream
