"""Optional authenticated learning gateway. Never expose the local admin server directly."""
import asyncio
import ipaddress
import json
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import jwt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, RedirectResponse
from remote_password import PasswordVerifier, COOKIE, login_page

ORIGIN = 'http://127.0.0.1:1400'
MAX_BODY = 2 * 1024 * 1024


def validate_settings(settings):
    origin = settings.get('public_origin', '')
    parsed = urlsplit(origin)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.netloc != parsed.hostname or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('public_origin must be an HTTPS hostname without a path')
    if settings.get('auth_mode') == 'password':
        if len(settings.get('session_secret', '')) < 43 or not re.fullmatch(r'[a-f0-9]{32}', settings.get('password_salt', '')) or not re.fullmatch(r'[a-f0-9]{128}', settings.get('password_hash', '')):
            raise ValueError('Password authentication must be fully configured')
        if '@' not in settings.get('email', ''):
            raise ValueError('Owner email is required')
        tunnel = settings.get('tunnel_hostname', '')
        if tunnel and not re.fullmatch(r'[a-z0-9.-]+\.ts\.net', tunnel):
            raise ValueError('Expected a Tailscale Funnel hostname')
        return dict(settings)
    issuer = settings.get('issuer', '')
    if not re.fullmatch(r'https://[a-z0-9-]+\.cloudflareaccess\.com', issuer):
        raise ValueError('issuer must be your Cloudflare Access team URL')
    if not isinstance(settings.get('audience'), str) or not settings['audience'].strip():
        raise ValueError('Cloudflare Access application audience is required')
    email = settings.get('email', '')
    if not isinstance(email, str) or '@' not in email or email.strip() != email:
        raise ValueError('An exact owner email is required')
    return dict(settings)


class AccessVerifier:
    def __init__(self, settings):
        self.settings = settings
        self.keys = jwt.PyJWKClient(settings['issuer'] + '/cdn-cgi/access/certs', timeout=10)

    def verify(self, token):
        key = self.keys.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=['RS256'], audience=self.settings['audience'],
                            issuer=self.settings['issuer'], options={'require': ['exp', 'iat', 'iss', 'aud', 'sub', 'email']})
        if claims['email'].casefold() != self.settings['email'].casefold():
            raise ValueError('Owner identity does not match')
        return claims


def allowed(method, path):
    if method in ('GET', 'HEAD'):
        if path in ('/', '/review', '/notebooks', '/word/new', '/favicon.ico', '/manifest.webmanifest',
                    '/api/words', '/api/words/export', '/api/dates', '/api/notebooks',
                    '/api/review/stats', '/api/review/due', '/api/events', '/api/enrich/progress',
                    '/api/health', '/api/access-mode'):
            return True
        return bool(re.fullmatch(r'/(?:word|api/words)/[^/]+', path) or
                    re.fullmatch(r'/assets/[a-zA-Z0-9_-][a-zA-Z0-9_./-]*', path) and '..' not in path)
    if method == 'POST':
        return path in ('/api/words', '/api/notebooks', '/api/words/copy', '/api/words/move', '/api/words/enrich-missing') or bool(re.fullmatch(r'/api/words/[^/]+/(?:review|enrich)', path))
    if method in ('PUT', 'DELETE'):
        return bool(re.fullmatch(r'/api/(?:words|notebooks)/[^/]+', path))
    return False


def create_gateway(settings, transport=None):
    settings = validate_settings(settings)
    verifier = PasswordVerifier(settings) if settings.get('auth_mode') == 'password' else AccessVerifier(settings)

    @asynccontextmanager
    async def lifespan(application):
        async with httpx.AsyncClient(base_url=ORIGIN, transport=transport, trust_env=False,
                                     timeout=httpx.Timeout(30, read=None), follow_redirects=False) as client:
            application.state.client = client
            yield

    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    application.state.verifier = verifier

    @application.middleware('http')
    async def guard(request, call_next):
        try:
            local = request.client and ipaddress.ip_address(request.client.host).is_loopback
        except ValueError:
            local = False
        hosts = {urlsplit(settings['public_origin']).netloc, settings.get('tunnel_hostname', '')} - {''}
        if not local or request.headers.get('host') not in hosts:
            return JSONResponse({'detail': 'Access denied'}, status_code=403)
        password_mode = settings.get('auth_mode') == 'password'
        if password_mode and request.url.path == '/login':
            if request.method == 'GET':
                return login_page()
            if request.method == 'POST' and request.headers.get('origin') == settings['public_origin']:
                return await application.state.verifier.login(request)
            return JSONResponse({'detail':'Invalid login origin'}, status_code=403)
        if password_mode and request.url.path == '/logout':
            if request.method != 'POST' or request.headers.get('origin') != settings['public_origin']:
                return JSONResponse({'detail':'Invalid logout origin'}, status_code=403)
            response = RedirectResponse('/login', status_code=303)
            response.delete_cookie(COOKIE, secure=True, httponly=True, samesite='strict', path='/')
            response.headers['Cache-Control'] = 'no-store'
            return response
        token = request.cookies.get(COOKIE, '') if password_mode else request.headers.get('cf-access-jwt-assertion', '')
        if not token or len(token) > 16384:
            if password_mode and request.method == 'GET' and not request.url.path.startswith('/api/'):
                return RedirectResponse('/login', status_code=303)
            return JSONResponse({'detail': '请通过私人学习入口登录'}, status_code=401)
        try:
            claims = await asyncio.to_thread(application.state.verifier.verify, token)
        except Exception:
            if password_mode and request.method == 'GET' and not request.url.path.startswith('/api/'):
                return RedirectResponse('/login', status_code=303)
            return JSONResponse({'detail': '登录失效或账号无权访问'}, status_code=401)
        request.state.expires = claims['exp']
        if request.method not in ('GET', 'HEAD') and request.headers.get('origin') != settings['public_origin']:
            return JSONResponse({'detail': 'Invalid request origin'}, status_code=403)
        if not allowed(request.method, request.url.path):
            return JSONResponse({'detail': '此功能仅限服务器本机使用'}, status_code=403)
        response = await call_next(request)
        response.headers.update({'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow, noarchive',
                                 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
                                 'X-Frame-Options': 'DENY'})
        return response

    @application.api_route('/{path:path}', methods=['GET', 'HEAD', 'POST', 'PUT', 'DELETE'])
    async def proxy(request: Request, path: str):
        if request.url.path == '/api/access-mode':
            return {'remote': True}
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY:
                return JSONResponse({'detail': 'Request too large'}, status_code=413)
        headers = {'Origin': ORIGIN, 'Accept-Encoding': 'identity'}
        if request.headers.get('content-type'):
            headers['Content-Type'] = request.headers['content-type']
        # Only learning routes are reachable. Browser credentials and proxy headers are never forwarded.
        target = ORIGIN + request.scope['raw_path'].decode('ascii')
        if request.scope['query_string']:
            target += '?' + request.scope['query_string'].decode('ascii')
        client = request.app.state.client
        try:
            response = await client.send(client.build_request(request.method, target, headers=headers, content=bytes(body)), stream=True)
        except httpx.HTTPError:
            return JSONResponse({'detail': '电脑上的词汇服务暂时不可用，请稍后重试'}, status_code=503)
        async def stream():
            iterator = response.aiter_bytes().__aiter__()
            try:
                while True:
                    remaining = min(900, request.state.expires - time.time())
                    if remaining <= 0:
                        break
                    try:
                        yield await asyncio.wait_for(anext(iterator), timeout=remaining)
                    except (StopAsyncIteration, asyncio.TimeoutError):
                        break
            finally:
                await response.aclose()
        safe_headers = {key: value for key, value in response.headers.items()
                        if key in ('content-type', 'content-disposition')}
        return StreamingResponse(stream(), status_code=response.status_code, headers=safe_headers)
    return application


if __name__ == '__main__':
    import uvicorn
    root = Path(__file__).resolve().parent
    settings = json.loads((root / '.secrets' / 'remote-access.json').read_text(encoding='utf-8-sig'))
    uvicorn.run(create_gateway(settings), host='127.0.0.1', port=1401, proxy_headers=False, access_log=False)
