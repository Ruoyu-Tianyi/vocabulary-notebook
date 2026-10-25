"""Exercise real password sessions without real accounts or network access."""
import time

import httpx
import jwt
import pytest

from remote_gateway import create_gateway
from remote_password import COOKIE, password_hash
from tests.local_client import TestClient


@pytest.fixture
def client():
    settings = {'auth_mode': 'password', 'public_origin': 'https://words.example.com',
                'email': 'owner@example.com', 'password_salt': 'ab' * 16,
                'password_hash': password_hash('test-password', 'ab' * 16),
                'session_secret': 'synthetic-test-key-' * 4}
    app = create_gateway(settings, httpx.MockTransport(lambda request: httpx.Response(200, json={})))
    with TestClient(app, base_url=settings['public_origin'], follow_redirects=False) as connection:
        yield connection, settings


def login(connection, password='test-password'):
    return connection.post('/login', data={'email': 'owner@example.com', 'password': password},
                           headers={'origin': 'https://words.example.com'})


def test_login_session_logout(client):
    connection, _ = client
    assert connection.get('/').status_code == 303
    assert connection.get('/api/words').status_code == 401
    response = login(connection)
    assert response.status_code == 303
    assert response.headers['cache-control'] == 'no-store'
    cookie = response.headers['set-cookie']
    assert all(value in cookie for value in ('Secure', 'HttpOnly', 'SameSite=strict', 'Path=/'))
    assert connection.get('/api/words').status_code == 200
    assert connection.get('/api/model-settings').status_code == 403
    assert connection.post('/api/words', json={}).status_code == 403
    assert connection.post('/logout', headers={'origin': 'https://words.example.com'}).status_code == 303
    assert connection.get('/api/words').status_code == 401


def test_invalid_login_origin_and_throttle(client):
    connection, _ = client
    assert connection.post('/login', data={}).status_code == 403
    for _ in range(10):
        assert login(connection, 'wrong').status_code == 401
    assert login(connection).status_code == 429


@pytest.mark.parametrize('expired', [True, False])
def test_expired_or_forged_session(client, expired):
    connection, settings = client
    claims = {'iss': settings['public_origin'], 'aud': 'private-learning', 'sub': 'owner',
              'email': settings['email'], 'iat': int(time.time()) - 60,
              'exp': int(time.time()) - 1 if expired else int(time.time()) + 60}
    token = jwt.encode(claims, settings['session_secret'] if expired else 'forged-key-' * 8, algorithm='HS256')
    connection.cookies.set(COOKIE, token)
    assert connection.get('/api/words').status_code == 401
