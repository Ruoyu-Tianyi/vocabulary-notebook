"""Windows launcher's local service bridge with cooperative, graceful shutdown."""
import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path


def installation_id(root):
    return hashlib.sha256(str(root.resolve()).rstrip('\\/').replace('\\', '/').lower().encode('utf-8')).hexdigest()


async def serve(root, stop_file, port):
    import uvicorn
    import app
    runtime = root / '.runtime'
    metadata = runtime / 'desktop-service.json'
    info = {'pid': os.getpid(), 'installation_id': installation_id(root), 'stop_file': str(stop_file)}
    # The launcher never stops a process by PID; it asks this exact service to exit.
    temp = metadata.with_suffix('.tmp')
    temp.write_text(json.dumps(info), encoding='utf-8')
    temp.replace(metadata)
    server = uvicorn.Server(uvicorn.Config(app.app, host='127.0.0.1', port=port,
                                         log_level='warning', proxy_headers=False,
                                         timeout_graceful_shutdown=3))

    async def watch():
        while not stop_file.exists():
            await asyncio.sleep(0.2)
        server.should_exit = True

    watcher = asyncio.create_task(watch())
    try:
        await server.serve()
    finally:
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stop-file', required=True)
    parser.add_argument('--port', type=int, default=1400)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    # Also support isolated Python distributions that omit the script directory from sys.path.
    sys.path.insert(0, str(root))
    runtime = root / '.runtime'
    runtime.mkdir(exist_ok=True)
    stop_file = Path(args.stop_file).resolve()
    if stop_file.parent != runtime.resolve() or not stop_file.name.startswith('stop-') or stop_file.suffix != '.request':
        raise ValueError('Invalid launcher stop path')
    os.chdir(root)
    log = runtime / 'service.log'
    if log.exists() and log.stat().st_size > 2_000_000:
        log.replace(runtime / 'service.previous.log')
    with log.open('a', encoding='utf-8', buffering=1) as stream:
        sys.stdout = sys.stderr = stream
        try:
            asyncio.run(serve(root, stop_file, args.port))
        except Exception:
            import traceback
            traceback.print_exc()
            return 1
        finally:
            # asyncio.run also joins outstanding executor threads. Only now may the
            # launcher/backup tool consider every background write finished.
            metadata = runtime / 'desktop-service.json'
            try:
                if json.loads(metadata.read_text(encoding='utf-8')).get('pid') == os.getpid():
                    metadata.unlink()
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            stop_file.unlink(missing_ok=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
