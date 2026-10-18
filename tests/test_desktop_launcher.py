"""Exercise actual launcher/service lifecycles with disposable libraries and ports."""
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest
import app
import desktop_service
from tests.local_client import TestClient

PROJECT = Path(__file__).resolve().parent.parent
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_ready(port, process=None, log=None):
    with httpx.Client(trust_env=False, timeout=0.5) as client:
        for _ in range(100):
            if process is not None and process.poll() is not None:
                pytest.fail('Isolated service exited: ' + (log.read_text(encoding='utf-8') if log and log.exists() else str(process.returncode)))
            try:
                response = client.get(f'http://127.0.0.1:{port}/api/instance')
                if response.status_code == 200:
                    return response.json()
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
    pytest.fail('Isolated service did not become ready')


def test_instance_identity_has_no_path_or_credentials_and_never_touches_library(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'DATA_FILE', tmp_path / 'words.json')
    result = TestClient(app.app).get('/api/instance').json()
    assert result == {'application': 'drive-vocabulary-book', 'installation_id': desktop_service.installation_id(PROJECT)}
    assert len(result['installation_id']) == 64
    assert str(PROJECT) not in json.dumps(result)
    assert not app.DATA_FILE.exists()


def test_release_launcher_is_a_gui_executable_with_multisize_icon():
    binary = (PROJECT / 'VocabularyBook.exe').read_bytes()
    pe = struct.unpack_from('<I', binary, 0x3C)[0]
    assert binary[:2] == b'MZ' and binary[pe:pe + 4] == b'PE\0\0'
    assert struct.unpack_from('<H', binary, pe + 24 + 68)[0] == 2  # Windows GUI subsystem.
    icon = (PROJECT / 'assets/app-icon.ico').read_bytes()
    assert struct.unpack_from('<HHH', icon) == (0, 1, 7)
    assert [icon[6 + i * 16] or 256 for i in range(7)] == [16, 24, 32, 48, 64, 128, 256]


def test_real_service_shutdown_finishes_lifespan_before_metadata_is_removed(tmp_path):
    root = tmp_path / '我的词汇本'
    root.mkdir()
    shutil.copy2(PROJECT / 'desktop_service.py', root)
    (root / 'app.py').write_text('''import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from desktop_service import installation_id
@asynccontextmanager
async def lifespan(app):
    Path('started').write_text('ready')
    yield
    await asyncio.sleep(0.1)
    Path('finished').write_text('saved')
app = FastAPI(lifespan=lifespan)
@app.get('/api/instance')
def identity():
    return {'application':'drive-vocabulary-book','installation_id':installation_id(Path(__file__).parent)}
@app.get('/events')
async def events():
    async def stream():
        while True:
            yield 'data: heartbeat\\n\\n'
            await asyncio.sleep(0.1)
    return StreamingResponse(stream(), media_type='text/event-stream')
''', encoding='utf-8')
    original = b'{"words":[{"id":"preserved","srs":{"reps":8}}]}'
    (root / 'words.json').write_bytes(original)
    runtime = root / '.runtime'
    stop = runtime / 'stop-test.request'
    port = free_port()
    process = subprocess.Popen([sys.executable, str(root / 'desktop_service.py'), '--stop-file', str(stop), '--port', str(port)],
                               creationflags=FLAGS)
    try:
        assert wait_ready(port, process, runtime / 'service.log')['installation_id'] == desktop_service.installation_id(root)
        metadata = json.loads((runtime / 'desktop-service.json').read_text())
        assert metadata['pid'] > 0
        assert (root / 'started').exists() and not (root / 'finished').exists()
        # Keep a browser-like SSE connection open throughout shutdown.
        with httpx.Client(trust_env=False) as client:
            with client.stream('GET', f'http://127.0.0.1:{port}/events') as response:
                lines = response.iter_lines()
                assert next(lines) == 'data: heartbeat'
                stop.write_text('stop')
                assert process.wait(timeout=10) == 0
        assert (root / 'finished').read_text() == 'saved'
        assert not (runtime / 'desktop-service.json').exists() and not stop.exists()
        assert (root / 'words.json').read_bytes() == original
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


@pytest.fixture
def windows_project(tmp_path):
    if os.name != 'nt' or importlib.util.find_spec('venv') is None:
        pytest.skip('Windows launcher needs the Windows desktop runtime and a full Python installation')
    root = tmp_path / '启动验收 词汇本'
    root.mkdir()
    shutil.copy2(PROJECT / 'VocabularyBook.exe', root)
    (root / 'app.py').write_text('# Preflight placeholder; isolated service uses the standard library.')
    dist = root / 'frontend/dist'
    dist.mkdir(parents=True)
    (dist / 'index.html').write_text('test')
    (root / 'words.json').write_text('{"words":[{"word":"Keep","srs":{"reps":8}}]}')
    subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(root / '.venv')], check=True, timeout=30, creationflags=FLAGS)
    # A minimal standard-library service exercises the compiled launcher's real process control.
    (root / 'desktop_service.py').write_text('''import argparse,json,os,hashlib
from pathlib import Path
from http.server import BaseHTTPRequestHandler,HTTPServer
p=argparse.ArgumentParser();p.add_argument('--stop-file');p.add_argument('--port',type=int);a=p.parse_args()
root=Path(__file__).resolve().parent;runtime=root/'.runtime';runtime.mkdir(exist_ok=True)
identity=hashlib.sha256(str(root).replace('\\\\','/').lower().encode('utf8')).hexdigest()
metadata=runtime/'desktop-service.json';stop=Path(a.stop_file)
metadata.write_text(json.dumps(dict(pid=os.getpid(),installation_id=identity,stop_file=str(stop))))
with (root/'starts').open('a') as f:f.write('start\\n')
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.end_headers();self.wfile.write(json.dumps(dict(application='drive-vocabulary-book',installation_id=identity)).encode())
 def log_message(self,*args):pass
server=HTTPServer(('127.0.0.1',a.port),Handler);server.timeout=0.1
while not stop.exists():server.handle_request()
server.server_close();(root/'finished').write_text('saved');metadata.unlink();stop.unlink()
''', encoding='utf-8')
    env = {**os.environ, 'VOCAB_LAUNCHER_PORT': str(free_port())}
    def run(argument):
        return subprocess.run([str(root / 'VocabularyBook.exe'), argument], cwd=root, env=env, timeout=15, creationflags=FLAGS).returncode
    yield root, env, run
    run('--stop')


def test_windows_launcher_starts_once_reuses_and_stops_without_changing_data(windows_project):
    root, env, run = windows_project
    before = (root / 'words.json').read_bytes()
    assert run('--check') == 1
    assert run('--start') == 0
    first = json.loads((root / '.runtime/desktop-service.json').read_text())['pid']
    assert run('--check') == 0
    assert run('--start') == 0
    assert json.loads((root / '.runtime/desktop-service.json').read_text())['pid'] == first
    assert (root / 'starts').read_text().splitlines() == ['start']
    assert run('--stop') == 0
    assert (root / 'finished').read_text() == 'saved'
    assert run('--check') == 1
    assert run('--start') == 0
    assert (root / 'starts').read_text().splitlines() == ['start', 'start']
    assert run('--stop') == 0
    assert (root / 'words.json').read_bytes() == before


def test_windows_launcher_does_not_start_over_or_stop_another_installation(windows_project):
    root, env, run = windows_project
    class Other(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"application":"drive-vocabulary-book","installation_id":"other-installation"}')
        def log_message(self, *args):
            pass
    server = HTTPServer(('127.0.0.1', int(env['VOCAB_LAUNCHER_PORT'])), Other)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert run('--start') == 1
        assert run('--stop') == 1
        assert not (root / 'starts').exists()
        with httpx.Client(trust_env=False) as client:
            assert client.get(f"http://127.0.0.1:{env['VOCAB_LAUNCHER_PORT']}/api/instance").json()['installation_id'] == 'other-installation'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
