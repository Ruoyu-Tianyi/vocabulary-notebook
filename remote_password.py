"""Single-owner password sessions for the optional private gateway."""
import asyncio
import hashlib
import hmac
import html
import time
from collections import deque
from urllib.parse import parse_qs

import jwt
from fastapi.responses import HTMLResponse, RedirectResponse

COOKIE = '__Host-vocab_session'


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


class PasswordVerifier:
    def __init__(self, settings):
        self.settings = settings
        self.attempts = deque()

    def verify(self, token):
        claims = jwt.decode(token, self.settings['session_secret'], algorithms=['HS256'],
                            issuer=self.settings['public_origin'], audience='private-learning',
                            options={'require':['exp','iat','sub','email','iss','aud']})
        if claims['email'].casefold() != self.settings['email'].casefold():
            raise ValueError('Invalid identity')
        return claims

    async def login(self, request):
        now = time.time()
        while self.attempts and self.attempts[0] < now - 600:
            self.attempts.popleft()
        if len(self.attempts) >= 10:
            return login_page('尝试次数过多，请 10 分钟后再试。', 429)
        self.attempts.append(now)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 8192:
                return login_page('请求内容过长。', 413)
        fields = parse_qs(body.decode('utf-8', errors='replace'))
        email = fields.get('email', [''])[0].strip().casefold()
        password = fields.get('password', [''])[0]
        computed = await asyncio.to_thread(password_hash, password, self.settings['password_salt'])
        if not (hmac.compare_digest(computed, self.settings['password_hash']) and
                hmac.compare_digest(email.encode(), self.settings['email'].casefold().encode())):
            return login_page('邮箱或密码不正确。', 401)
        self.attempts.clear()
        token = jwt.encode({'sub':'owner','email':self.settings['email'], 'iat':int(now),
                            'exp':int(now) + 7 * 86400, 'iss':self.settings['public_origin'],
                            'aud':'private-learning'}, self.settings['session_secret'], algorithm='HS256')
        response = RedirectResponse('/', status_code=303)
        response.headers['Cache-Control'] = 'no-store'
        response.set_cookie(COOKIE, token, max_age=7 * 86400, secure=True, httponly=True, samesite='strict', path='/')
        return response


def login_page(error='', status=200):
    return HTMLResponse('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>私人学习 · 登录</title><style>
    *{box-sizing:border-box}body{margin:0;background:#191815;color:#e8e2d1;font-family:system-ui;min-height:100vh;display:grid;place-items:center;padding:24px}.card{width:100%;max-width:420px;border:1px solid #494337;background:#24221d;border-radius:20px;padding:32px}h1{font-size:28px;margin:8px 0 12px}.tag{color:#c9ac59;letter-spacing:3px;font-size:12px}p{color:#bdb6a6;line-height:1.6}label{display:block;margin-top:20px;font-size:14px}input{width:100%;margin-top:8px;padding:14px;background:#191815;border:1px solid #655b44;border-radius:8px;color:#fff;font:inherit}button{width:100%;padding:14px;margin-top:24px;border:0;border-radius:8px;background:#c9ac59;color:#191815;font-size:16px;font-weight:700}input:focus,button:focus{outline:2px solid #e3c773;outline-offset:3px}.error{color:#ffb3a7}</style><main class="card"><div class="tag">PRIVATE LEARNING</div><h1>欢迎回到词汇本</h1><p>登录后接续你的记录与复习。</p>'''
    + ('<p class="error" role="alert">' + html.escape(error) + '</p>' if error else '')
    + '''<form method="post" action="/login"><label>邮箱<input name="email" type="email" autocomplete="username" required></label><label>密码<input name="password" type="password" autocomplete="current-password" required></label><button type="submit">进入学习空间</button></form></main></html>''', status_code=status,
    headers={'Cache-Control':'no-store','X-Robots-Tag':'noindex, nofollow','X-Frame-Options':'DENY','X-Content-Type-Options':'nosniff'})
