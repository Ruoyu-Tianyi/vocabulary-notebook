"""Google Drive appDataFolder transport and desktop OAuth (loopback + PKCE)."""
import base64
import hashlib
import html
import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

import sync_storage as storage

SCOPE = "https://www.googleapis.com/auth/drive.appdata"
API = "https://www.googleapis.com/drive/v3"
APP = "drive-vocabulary-book-v1"
MAX_BYTES = 8 * 1024 * 1024


def safe_error(exc):
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (400, 401):
            return "Google 授权失效，请重新连接 Google Drive"
        if status == 403:
            return "Drive 拒绝访问，请检查 API 是否启用、授权权限及存储空间"
        if status == 429:
            return "Drive 请求过于频繁，稍后会自动重试"
        return f"Drive 服务暂时不可用（{status}），本地数据已保留"
    if isinstance(exc, httpx.RequestError):
        return "无法连接 Google Drive，本地更改已保存，联网后自动重试"
    if isinstance(exc, (ValueError, RuntimeError)):
        return str(exc)[:250]
    return "同步未完成，本地数据已保留；请检查本地文件权限与设置"


class DriveSync:
    def __init__(self, data_path, write_lock, settings):
        self.data_path = data_path  # callable so tests can isolate DATA_FILE
        self.write_lock = write_lock
        self.settings = settings
        self.lock = threading.Lock()
        self.auth_lock = threading.RLock()
        self.busy = False
        self.auth_pending = False
        self.authorization_url = ""
        self._auth_cancel = None
        self.error = ""

    @property
    def secrets_dir(self):
        return Path(self.settings()["credentials_dir"])

    def _read_secret(self, name):
        path = self.secrets_dir / name
        return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else None

    def import_credentials(self, document):
        installed = document.get("installed", {}) if isinstance(document, dict) else {}
        if (not isinstance(installed, dict) or not isinstance(installed.get("client_id"), str)
                or not installed["client_id"].endswith(".apps.googleusercontent.com")
                or not isinstance(installed.get("client_secret"), str) or not installed["client_secret"]):
            raise ValueError("请选择 Google Cloud 下载的桌面应用 OAuth 客户端 JSON 文件")
        with self.auth_lock:
            if self.auth_pending or self.busy or self._read_secret("token.json"):
                raise ValueError("请先断开连接并等待正在进行的授权/同步结束，再更换客户端")
            storage.atomic_write(self.secrets_dir / "client_secret.json", {"installed": {
                "client_id": installed["client_id"], "client_secret": installed["client_secret"]}})

    def begin_auth(self):
        with self.auth_lock:
            if self.auth_pending or self.busy:
                raise ValueError("授权或同步正在进行，请稍候")
            document = self._read_secret("client_secret.json")
            if not document:
                raise ValueError("请先导入 Google Cloud 的桌面 OAuth 客户端 JSON 文件")
            if self.folder_settings().get("enabled"):
                raise ValueError("请先断开同步文件夹，再使用 API 直连")
            client = document["installed"]
            state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
            cancelled = threading.Event()
            self._auth_cancel = cancelled
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            owner = self

            class Callback(BaseHTTPRequestHandler):
                def log_message(self, *_):
                    pass  # authorization codes must not enter access logs

                def do_GET(self):
                    parsed = urlparse(self.path)
                    query = parse_qs(parsed.query)
                    if cancelled.is_set() or parsed.path != "/callback" or query.get("state", [""])[0] != state:
                        self.send_error(400, "Invalid OAuth callback")
                        return
                    try:
                        if query.get("error") or not query.get("code"):
                            raise ValueError("Google 授权已取消，请重新连接")
                        with httpx.Client(timeout=30) as http:
                            response = http.post("https://oauth2.googleapis.com/token", data={
                                "client_id": client["client_id"], "client_secret": client["client_secret"],
                                "code": query["code"][0], "code_verifier": verifier,
                                "redirect_uri": redirect, "grant_type": "authorization_code"})
                            response.raise_for_status()
                            token = response.json()
                            token["expires_at"] = time.time() + token.get("expires_in", 3600)
                            if not token.get("refresh_token"):
                                raise ValueError("Google 未返回离线授权，请重新连接并同意授权")
                            account = http.get(API + "/about", params={"fields": "user(permissionId,emailAddress)"},
                                               headers={"Authorization": "Bearer " + token["access_token"]})
                            account.raise_for_status()
                            user = account.json()["user"]
                        binding = client["client_id"] + ":" + user["permissionId"]
                        with owner.auth_lock, owner.write_lock:
                            if cancelled.is_set():
                                raise ValueError("本次授权已取消，请返回词汇本重新连接")
                            data = storage.read(owner.data_path())
                            if data["_sync"]["account"] not in ("", binding):
                                raise ValueError("此词库已绑定另一账号或 OAuth 客户端。请使用原账号和客户端，或为新账号指定新的 VOCAB_DATA_FILE")
                            data["_sync"]["account"] = binding
                            if data["_sync"].get("transport") != "api:" + binding:
                                data["_sync"]["uploaded"] = []
                                data["_sync"]["downloaded_files"] = []
                                data["_sync"]["last_synced_at"] = None
                            data["_sync"]["transport"] = "api:" + binding
                            storage.atomic_write(owner.data_path(), data)
                            token["email"] = user.get("emailAddress", "Google Drive")
                            storage.atomic_write(owner.secrets_dir / "token.json", token)
                            owner.error = ""
                        message = "Google Drive 连接成功。请返回词汇本，数据会自动同步。"
                    except Exception as exc:
                        message = safe_error(exc)
                        with owner.auth_lock:
                            if not cancelled.is_set():
                                owner.error = message
                    finally:
                        with owner.auth_lock:
                            if owner._auth_cancel is cancelled:
                                owner.auth_pending = False
                                owner.authorization_url = ""
                            cancelled.set()
                    payload = ("<!doctype html><meta charset='utf-8'><title>词汇本同步</title><p>" + html.escape(message) + "</p>").encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)

            server = HTTPServer(("127.0.0.1", 0), Callback)
            server.timeout = 1
            redirect = f"http://127.0.0.1:{server.server_port}/callback"
            url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
                "client_id": client["client_id"], "redirect_uri": redirect,
                "response_type": "code", "scope": SCOPE, "state": state,
                "code_challenge": challenge, "code_challenge_method": "S256",
                "access_type": "offline", "prompt": "consent"})
            self.auth_pending, self.error = True, ""
            self.authorization_url = url

            def wait_callback():
                deadline = time.monotonic() + 180
                try:
                    while not cancelled.is_set() and self.auth_pending and time.monotonic() < deadline:
                        server.handle_request()
                    with self.auth_lock:
                        if self._auth_cancel is cancelled and self.auth_pending and not cancelled.is_set():
                            self.error = "Google 授权超时，请重新连接"
                            self.auth_pending = False
                            self.authorization_url = ""
                            cancelled.set()
                finally:
                    server.server_close()

            threading.Thread(target=wait_callback, daemon=True).start()
            return {"authorization_url": url}

    def cancel_auth(self):
        with self.auth_lock:
            if self._auth_cancel:
                self._auth_cancel.set()
            self.auth_pending = False
            self.authorization_url = ""
            self.error = ""

    def disconnect(self):
        with self.auth_lock:
            if self.busy or self.auth_pending:
                raise ValueError("请等待正在进行的授权或同步结束")
            folder = self.folder_settings()
            if folder.get("enabled"):
                folder["enabled"] = False
                storage.atomic_write(self.secrets_dir / "sync-settings.json", folder)
            else:
                (self.secrets_dir / "token.json").unlink(missing_ok=True)
            self.error = ""

    def folder_settings(self):
        return self._read_secret("sync-settings.json") or {}

    def configure_folder(self, folder_path):
        """Persist only a local pointer. Each computer has an independent words.json."""
        with self.auth_lock, self.write_lock:
            if self.busy or self.auth_pending:
                raise ValueError("请等待正在进行的同步或授权结束")
            if self._read_secret("token.json"):
                raise ValueError("请先断开 API 直连，再连接同步文件夹")
            path = Path(folder_path).expanduser()
            if not path.is_absolute() or not path.parent.is_dir():
                raise ValueError("请输入同步盘中的绝对文件夹路径，且上级文件夹必须存在")
            path = path.resolve()
            if path == self.data_path().resolve().parent or path == self.secrets_dir.resolve():
                raise ValueError("请在 Google Drive 中新建专用同步文件夹，不要选择程序目录")
            path.mkdir(exist_ok=True)
            manifest = path / "library.json"
            if not manifest.exists():
                try:
                    with manifest.open("x", encoding="utf-8") as stream:
                        json.dump({"app": APP, "library_id": secrets.token_hex(24)}, stream)
                except FileExistsError:
                    pass
            identity = json.loads(manifest.read_text(encoding="utf-8"))
            if identity.get("app") != APP or not identity.get("library_id"):
                raise ValueError("所选文件夹不是兼容的词汇本同步目录")
            previous = self.folder_settings()
            data = storage.read(self.data_path())
            if previous.get("library_id") != identity["library_id"] or not previous.get("enabled"):
                data["_sync"]["uploaded"] = []
                data["_sync"]["downloaded_files"] = []
                data["_sync"]["last_synced_at"] = None
                data["_sync"]["transport"] = "folder:" + identity["library_id"]
                storage.atomic_write(self.data_path(), data)
            storage.atomic_write(self.secrets_dir / "sync-settings.json", {
                "folder_path": str(path), "library_id": identity["library_id"], "enabled": True})
            self.error = ""
            return {"ok": True}

    def _access_token(self, http):
        with self.auth_lock:
            token = self._read_secret("token.json")
            if not token:
                raise ValueError("尚未连接 Google Drive")
            client = self._read_secret("client_secret.json")
        # 网络请求不持有状态锁，避免令牌刷新阻塞状态轮询和应用事件循环。
        if token.get("expires_at", 0) <= time.time() + 60:
            if not client or not token.get("refresh_token"):
                raise ValueError("Google 授权不完整，请重新连接 Google Drive")
            response = http.post("https://oauth2.googleapis.com/token", data={
                "client_id": client["installed"]["client_id"], "client_secret": client["installed"]["client_secret"],
                "refresh_token": token["refresh_token"], "grant_type": "refresh_token"})
            response.raise_for_status()
            token.update(response.json())
            token["expires_at"] = time.time() + token.get("expires_in", 3600)
            with self.auth_lock:
                storage.atomic_write(self.secrets_dir / "token.json", token)
        return token["access_token"]

    def status(self):
        with self.auth_lock, self.write_lock:
            token = self._read_secret("token.json")
            meta = storage.read(self.data_path())["_sync"]
            folder = self.folder_settings()
            folder_mode = folder.get("enabled", False)
            return {"provider": "drive_folder" if folder_mode else "google_drive", "configured": bool(self._read_secret("client_secret.json")),
                    "connected": bool(token) or folder_mode, "account": folder.get("folder_path", "") if folder_mode else (token or {}).get("email", ""),
                    "folder_path": folder.get("folder_path", ""), "folder_enabled": folder_mode,
                    "auth_pending": self.auth_pending, "syncing": self.busy,
                    "authorization_url": self.authorization_url if self.auth_pending else "",
                    "pending": len(set(meta["operations"]) - set(meta["uploaded"])),
                    "last_synced_at": meta.get("last_synced_at"), "error": self.error,
                    "last_pulled_at": meta.get("last_pulled_at"),
                    "interval_seconds": self.settings()["interval_seconds"]}

    def sync(self):
        with self.auth_lock:
            if self.auth_pending:
                return {"busy": True}
            if not self.lock.acquire(blocking=False):
                return {"busy": True}
            self.busy = True
        progress = {"pulled": 0, "pushed": 0}
        try:
            if self.folder_settings().get("enabled"):
                return self._sync_folder(progress)
            with httpx.Client(timeout=30) as http:
                http.headers["Authorization"] = "Bearer " + self._access_token(http)
                files, page = [], None
                while True:
                    params = {"spaces": "appDataFolder", "pageSize": 1000,
                              "q": f"trashed = false and appProperties has {{ key='app' and value='{APP}' }}",
                              "fields": "nextPageToken,files(id,size)"}
                    if page:
                        params["pageToken"] = page
                    response = http.get(API + "/files", params=params)
                    response.raise_for_status()
                    listing = response.json()
                    files.extend(listing.get("files", []))
                    page = listing.get("nextPageToken")
                    if not page:
                        break
                with self.write_lock:
                    seen = set(storage.read(self.data_path())["_sync"].get("downloaded_files", []))
                for file in files:
                    if file["id"] in seen:
                        continue
                    if int(file.get("size", 0)) > MAX_BYTES:
                        raise ValueError("云端变更文件过大，已暂停同步，本地数据保留")
                    payload = bytearray()
                    with http.stream("GET", API + "/files/" + file["id"], params={"alt": "media"}) as response:
                        response.raise_for_status()
                        for chunk in response.iter_bytes():
                            payload.extend(chunk)
                            if len(payload) > MAX_BYTES:
                                raise ValueError("云端变更文件过大，已暂停同步")
                    document = json.loads(payload)
                    if document.get("version") != storage.VERSION:
                        raise ValueError("云端词库版本不兼容，请升级应用")
                    operations = document["operations"]
                    with self.write_lock:
                        progress["pulled"] += storage.merge(self.data_path(), operations)
                        data = storage.read(self.data_path())
                        meta = data["_sync"]
                        meta["downloaded_files"] = sorted(set(meta.get("downloaded_files", [])) | {file["id"]})
                        meta["uploaded"] = sorted(set(meta["uploaded"]) | {op["id"] for op in operations})
                        if progress["pulled"]:
                            meta["last_pulled_at"] = datetime.now(timezone.utc).isoformat()
                        storage.atomic_write(self.data_path(), data)
                with self.write_lock:
                    meta = storage.read(self.data_path())["_sync"]
                    uploaded = set(meta["uploaded"])
                    pending = [op for key, op in sorted(meta["operations"].items()) if key not in uploaded]
                for start in range(0, len(pending), 50):
                    batch = pending[start:start + 50]
                    storage.validate_operations(batch)
                    payload = json.dumps({"version": storage.VERSION, "operations": batch}, ensure_ascii=False).encode()
                    if len(payload) > MAX_BYTES:
                        raise ValueError("待同步变更过大，请缩短单词内容")
                    digest = hashlib.sha256(payload).hexdigest()
                    boundary = secrets.token_hex(24)
                    metadata = json.dumps({"name": f"vocabulary-{digest}.json", "parents": ["appDataFolder"],
                                           "mimeType": "application/json", "appProperties": {"app": APP}}).encode()
                    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode() + metadata
                            + f"\r\n--{boundary}\r\nContent-Type: application/json\r\n\r\n".encode() + payload
                            + f"\r\n--{boundary}--\r\n".encode())
                    response = http.post("https://www.googleapis.com/upload/drive/v3/files",
                                         params={"uploadType": "multipart", "fields": "id"}, content=body,
                                         headers={"Content-Type": f"multipart/related; boundary={boundary}"})
                    response.raise_for_status()
                    file_id = response.json()["id"]
                    with self.write_lock:
                        data = storage.read(self.data_path())
                        meta = data["_sync"]
                        meta["uploaded"] = sorted(set(meta["uploaded"]) | {op["id"] for op in batch})
                        meta["downloaded_files"] = sorted(set(meta.get("downloaded_files", [])) | {file_id})
                        storage.atomic_write(self.data_path(), data)
                    progress["pushed"] += len(batch)
            with self.write_lock:
                data = storage.read(self.data_path())
                data["_sync"]["last_synced_at"] = datetime.now(timezone.utc).isoformat()
                if progress["pulled"]:
                    data["_sync"]["last_pulled_at"] = data["_sync"]["last_synced_at"]
                storage.atomic_write(self.data_path(), data)
            self.error = ""
            return progress
        except Exception as exc:
            self.error = safe_error(exc)
            return {"error": self.error, **progress}
        finally:
            with self.auth_lock:
                self.busy = False
                self.lock.release()

    def _sync_folder(self, progress):
        settings = self.folder_settings()
        root = Path(settings["folder_path"])
        if not root.is_dir() or not (root / "library.json").is_file():
            raise ValueError("同步文件夹不可用，请确认 Google Drive 已启动、文件夹可离线使用；本地记录已保留")
        identity = json.loads((root / "library.json").read_text(encoding="utf-8"))
        if identity.get("library_id") != settings["library_id"] or identity.get("app") != APP:
            raise ValueError("同步目录身份不匹配，请确认 Google Drive 登录的是原账号")
        with self.write_lock:
            meta = storage.read(self.data_path())["_sync"]
            seen = set(meta.get("downloaded_files", []))
        # Files are immutable and named by their content; cloud conflict copies deduplicate by op ID.
        for file in sorted(root.glob("vocabulary-*.json")):
            if file.name in seen:
                continue
            if file.stat().st_size > MAX_BYTES:
                raise ValueError("同步文件过大，已暂停同步")
            document = json.loads(file.read_text(encoding="utf-8"))
            if document.get("version") != storage.VERSION:
                raise ValueError("同步文件版本不兼容，请升级应用")
            with self.write_lock:
                progress["pulled"] += storage.merge(self.data_path(), document["operations"])
                data = storage.read(self.data_path())
                meta = data["_sync"]
                meta["downloaded_files"] = sorted(set(meta.get("downloaded_files", [])) | {file.name})
                meta["uploaded"] = sorted(set(meta["uploaded"]) | {op["id"] for op in document["operations"]})
                if progress["pulled"]:
                    meta["last_pulled_at"] = datetime.now(timezone.utc).isoformat()
                storage.atomic_write(self.data_path(), data)
        with self.write_lock:
            meta = storage.read(self.data_path())["_sync"]
            uploaded = set(meta["uploaded"])
            pending = [op for key, op in sorted(meta["operations"].items()) if key not in uploaded]
        for start in range(0, len(pending), 50):
            batch = pending[start:start + 50]
            storage.validate_operations(batch)
            document = {"version": storage.VERSION, "operations": batch}
            content = json.dumps(document, ensure_ascii=False, sort_keys=True).encode()
            if len(content) > MAX_BYTES:
                raise ValueError("待同步变更过大，请缩短单词内容")
            name = "vocabulary-" + hashlib.sha256(content).hexdigest() + ".json"
            file = root / name
            # Unique temporary names avoid two desktop writers colliding during atomic replace.
            temp = root / (name + "." + secrets.token_hex(8) + ".tmp")
            try:
                with temp.open("wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                temp.replace(file)
            finally:
                temp.unlink(missing_ok=True)
            with self.write_lock:
                data = storage.read(self.data_path())
                meta = data["_sync"]
                meta["uploaded"] = sorted(set(meta["uploaded"]) | {op["id"] for op in batch})
                meta["downloaded_files"] = sorted(set(meta.get("downloaded_files", [])) | {name})
                storage.atomic_write(self.data_path(), data)
            progress["pushed"] += len(batch)
        with self.write_lock:
            data = storage.read(self.data_path())
            data["_sync"]["last_synced_at"] = datetime.now(timezone.utc).isoformat()
            storage.atomic_write(self.data_path(), data)
        self.error = ""
        return progress
