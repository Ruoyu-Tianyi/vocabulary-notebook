"""模型配置的持久化、密钥保护及供应商核验。"""
import json
from unittest.mock import AsyncMock, patch

import pytest
from tests.local_client import TestClient

import config
from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / 'config.json'
    original = {'provider': 'deepseek', 'deepseek': {'api_key': 'private-test-key', 'model': 'old-model'},
                'ollama': {'url': 'http://localhost:11434/api/generate', 'model': 'local'},
                'srs': {'daily_new_limit': 17}}
    path.write_text(json.dumps(original))
    monkeypatch.setattr(config, 'CONFIG_FILE', path)
    monkeypatch.setattr(config, '_CONFIG', {})
    return TestClient(app)


def test_read_masks_key(client):
    response = client.get('/api/model-settings')
    assert response.status_code == 200
    assert 'private-test-key' not in response.text
    assert response.json()['deepseek']['api_key_configured'] is True


def test_save_preserves_key_and_other_settings(client):
    data = client.get('/api/model-settings').json()
    data['providers']['deepseek']['model'] = 'new-model'
    with patch('app.deepseek_models', AsyncMock(return_value=['new-model'])):
        response = client.put('/api/model-settings', json=data)
    assert response.status_code == 200
    assert 'private-test-key' not in response.text
    stored = json.loads(config.CONFIG_FILE.read_text())
    assert stored['deepseek']['api_key'] == 'private-test-key'
    assert stored['srs']['daily_new_limit'] == 17
    assert config.get_deepseek_config()['model'] == 'new-model'


def test_manual_model_saves_without_network(client):
    data = client.get('/api/model-settings').json()
    data['providers']['deepseek']['model'] = 'manual-model'
    with patch('model_providers.discover', AsyncMock(return_value=['new-model'])) as discover:
        response = client.put('/api/model-settings', json=data)
        discover.assert_not_called()
        health = client.get('/api/health').json()
    assert response.status_code == 200
    assert health['status'] == 'unverified'


def test_failed_discovery_does_not_report_expired(client):
    with patch('model_providers.discover', AsyncMock(side_effect=ValueError('private-test-key'))):
        assert client.get('/api/health').json()['status'] == 'unverified'
        response = client.post('/api/model-settings/models', json={'provider': 'deepseek'})
        assert response.status_code == 502
        assert 'private-test-key' not in response.text


def test_switch_to_ollama_and_reject_other_provider(client):
    data = client.get('/api/model-settings').json()
    data['provider'] = 'ollama'
    assert client.put('/api/model-settings', json=data).status_code == 200
    assert config.get_provider() == 'ollama'
    data['provider'] = 'other'
    assert client.put('/api/model-settings', json=data).status_code == 422


@pytest.mark.parametrize('provider', ['openai', 'anthropic', 'gemini', 'qwen', 'moonshot', 'zhipu',
                                     'siliconflow', 'openrouter', 'groq', 'mistral', 'together', 'fireworks', 'xai'])
def test_provider_roundtrip(client, provider):
    profile = {'model': 'test-model', 'api_key': 'new-secret'}
    response = client.put('/api/model-settings', json={'provider': provider, 'providers': {provider: profile}})
    assert response.status_code == 200
    assert 'new-secret' not in response.text
    assert config.get_model_config()['api_key'] == 'new-secret'
    assert config.get_deepseek_config()['api_key'] == 'private-test-key'


def test_key_not_forwarded_when_url_changed(client):
    with patch('model_providers.discover', AsyncMock()) as discover:
        response = client.post('/api/model-settings/models', json={
            'provider': 'deepseek', 'base_url': 'https://other.example/v1'})
    assert response.status_code == 400
    discover.assert_not_called()


def test_environment_key_and_clear(client, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'env-secret')
    response = client.put('/api/model-settings', json={'provider': 'deepseek', 'providers': {
        'deepseek': {'model': 'manual', 'clear_api_key': True}}})
    assert response.status_code == 200
    assert 'env-secret' not in response.text
    assert config.get_deepseek_config()['api_key'] == ''
    assert config.get_model_config()['api_key'] == 'env-secret'


def test_custom_without_key_and_test_does_not_save(client):
    before = config.CONFIG_FILE.read_text()
    with patch('model_providers.complete', AsyncMock(return_value='OK')) as complete:
        response = client.post('/api/model-settings/test', json={
            'provider': 'custom', 'base_url': 'http://localhost:1234/v1', 'model': 'local'})
    assert response.status_code == 200
    assert complete.call_args.args[0]['api_key'] == ''
    assert config.CONFIG_FILE.read_text() == before


def test_builtin_selection_survives_saving_custom_and_reload(client, monkeypatch):
    assert client.put('/api/model-settings', json={'provider': 'anthropic', 'providers': {
        'anthropic': {'model': 'claude', 'api_key': 'synthetic'}}}).status_code == 200
    assert client.put('/api/model-settings', json={'provider': 'custom', 'providers': {
        'custom': {'model': 'local', 'base_url': 'http://localhost:1234/v1'}}}).status_code == 200
    monkeypatch.setattr(config, '_CONFIG', {})
    data = client.get('/api/model-settings').json()
    assert data['provider'] == 'custom'
    assert data['last_builtin_provider'] == 'anthropic'


def test_first_custom_setup_from_example_placeholder(client):
    config.load_config()['providers'] = {'custom': {'base_url': '', 'model': '', 'api_key': '', 'protocol': 'openai'}}
    profile = {'provider': 'custom', 'base_url': 'http://localhost:1234/v1', 'model': 'local'}
    with patch('model_providers.complete', AsyncMock(return_value='OK')):
        assert client.post('/api/model-settings/test', json=profile).status_code == 200
    assert client.put('/api/model-settings', json={'provider': 'custom', 'providers': {
        'custom': {key: value for key, value in profile.items() if key != 'provider'}}}).status_code == 200


def test_whitespace_key_preserves_saved_secret_and_canonicalizes_profile(client):
    profile = {'model': '  selected-model  ', 'api_key': '   ', 'base_url': '  https://api.deepseek.com/chat/completions/  '}
    with patch('model_providers.complete', AsyncMock(return_value='OK')) as complete:
        response = client.post('/api/model-settings/test', json={'provider': 'deepseek', **profile})
    assert response.status_code == 200
    assert complete.call_args.args[0]['api_key'] == 'private-test-key'
    assert complete.call_args.args[0]['model'] == 'selected-model'
    response = client.put('/api/model-settings', json={'provider': 'deepseek', 'providers': {'deepseek': profile}})
    assert response.status_code == 200
    assert config.get_deepseek_config()['api_key'] == 'private-test-key'
    assert response.json()['providers']['deepseek']['model'] == 'selected-model'
    assert response.json()['providers']['deepseek']['base_url'] == 'https://api.deepseek.com'


def test_default_url_and_native_protocol_return_after_save(client):
    response = client.put('/api/model-settings', json={'provider': 'anthropic', 'providers': {
        'anthropic': {'model': 'claude', 'api_key': 'synthetic', 'base_url': ''}}})
    assert response.status_code == 200
    profile = response.json()['providers']['anthropic']
    assert profile['base_url'] == 'https://api.anthropic.com/v1'
    assert profile['protocol'] == 'anthropic'


def test_new_key_replaces_key_even_when_clear_was_checked(client):
    profile = {'model': 'model', 'api_key': 'replacement', 'clear_api_key': True}
    with patch('model_providers.complete', AsyncMock(return_value='OK')) as complete:
        assert client.post('/api/model-settings/test', json={'provider': 'deepseek', **profile}).status_code == 200
    assert complete.call_args.args[0]['api_key'] == 'replacement'
    assert client.put('/api/model-settings', json={'provider': 'deepseek', 'providers': {'deepseek': profile}}).status_code == 200
    assert config.get_deepseek_config()['api_key'] == 'replacement'
