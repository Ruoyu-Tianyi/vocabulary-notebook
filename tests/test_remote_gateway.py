# ruff: noqa: E402
"""Remote gateway rejects invalid identities and cannot access local administration."""
import time
import pytest
import httpx
jwt = pytest.importorskip('jwt')
pytest.importorskip('cryptography')
from cryptography.hazmat.primitives.asymmetric import rsa
from types import SimpleNamespace
from remote_gateway import AccessVerifier, create_gateway, validate_settings
from tests.local_client import TestClient

SETTINGS = {'public_origin':'https://words.example.com', 'issuer':'https://test.cloudflareaccess.com',
            'audience':'test-audience', 'email':'owner@example.com'}

@pytest.fixture
def keys():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)

def token(keys, **overrides):
    claims = {'iss':SETTINGS['issuer'], 'aud':SETTINGS['audience'], 'email':SETTINGS['email'],
              'sub':'owner', 'iat':int(time.time()) - 1, 'exp':int(time.time()) + 60}
    claims.update(overrides)
    return jwt.encode(claims, keys, algorithm='RS256', headers={'kid':'test'})

def verifier(keys):
    instance = AccessVerifier(SETTINGS)
    instance.keys = SimpleNamespace(get_signing_key_from_jwt=lambda value: SimpleNamespace(key=keys.public_key()))
    return instance

@pytest.mark.parametrize('overrides', [{'email':'other@example.com'}, {'iss':'https://evil.example'},
    {'aud':'different'}, {'exp':0}, {'iat':int(time.time()) + 3600}])
def test_invalid_jwt_claims_rejected(keys, overrides):
    with pytest.raises((ValueError, jwt.PyJWTError)):
        verifier(keys).verify(token(keys, **overrides))

def test_forged_signature_rejected(keys):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(jwt.PyJWTError): verifier(keys).verify(token(other))

@pytest.fixture
def client(keys):
    seen = []
    def upstream(request):
        seen.append(request)
        return httpx.Response(200, content=b'{"words":[]}', headers={'content-type':'application/json'})
    app = create_gateway(SETTINGS, transport=httpx.MockTransport(upstream))
    app.state.verifier = verifier(keys)
    with TestClient(app, base_url=SETTINGS['public_origin']) as connection:
        connection.headers['cf-access-jwt-assertion'] = token(keys)
        yield connection, seen

def test_authenticated_learning_proxy_drops_credentials(client):
    connection, seen = client
    response = connection.get('/api/words?q=%E5%90%88%E5%90%8C', headers={'cookie':'secret', 'authorization':'Bearer fake'})
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert seen[0].url.host == '127.0.0.1'
    assert 'cookie' not in seen[0].headers and 'authorization' not in seen[0].headers
    assert 'cf-access-jwt-assertion' not in seen[0].headers
    assert connection.get('/api/access-mode').json() == {'remote':True}

@pytest.mark.parametrize('path', ['/api/model-settings','/api/sync/status','/api/library/export','/api/instance','/.secrets/deepseek.json','/docs','/config.json'])
def test_admin_and_private_files_never_proxied(client, path):
    connection, seen = client
    assert connection.get(path).status_code == 403
    assert not seen

def test_mutation_requires_matching_origin(client):
    connection, seen = client
    assert connection.post('/api/words', json={'word':'Contract'}).status_code == 403
    assert connection.post('/api/words', json={}, headers={'origin':'https://evil.example'}).status_code == 403
    assert not seen
    assert connection.post('/api/words', json={}, headers={'origin':SETTINGS['public_origin']}).status_code == 200

def test_missing_identity_and_wrong_host_fail_closed(client):
    connection, seen = client
    assert connection.get('/', headers={'host':'localhost'}).status_code == 403
    connection.headers.pop('cf-access-jwt-assertion')
    assert connection.get('/').status_code == 401
    assert not seen

def test_untrusted_socket_rejected(keys):
    app = create_gateway(SETTINGS)
    app.state.verifier = verifier(keys)
    from starlette.testclient import TestClient as RemoteClient
    with RemoteClient(app, base_url=SETTINGS['public_origin'], client=('192.0.2.1', 1234)) as client:
        assert client.get('/', headers={'cf-access-jwt-assertion':token(keys)}).status_code == 403

@pytest.mark.parametrize('key,value', [('public_origin','http://words.example.com'), ('issuer','https://evil.example'),('email',''),('audience','')])
def test_incomplete_config_cannot_start(key, value):
    with pytest.raises(ValueError): validate_settings({**SETTINGS,key:value})
