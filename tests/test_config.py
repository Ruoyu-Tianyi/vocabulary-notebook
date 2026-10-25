"""Fork configuration retains local secrets and upstream fail-before-cache validation."""
import json
import pytest
import config

@pytest.fixture
def config_file(tmp_path, monkeypatch):
    path = tmp_path / 'config.json'
    monkeypatch.setattr(config, 'CONFIG_FILE', path)
    monkeypatch.setattr(config, '_CONFIG', {})
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.delenv('DEEPSEEK_MODEL', raising=False)
    monkeypatch.chdir(tmp_path)
    return path

@pytest.mark.parametrize('data', [[], 'config', {'provider':'unknown'},
    {'deepseek':None}, {'srs':[]}, {'sync':'invalid'},
    {'deepseek':{'model':' '}}, {'deepseek':{'model':123}}])
def test_invalid_config_is_never_cached_and_can_be_repaired(config_file, data):
    config_file.write_text(json.dumps(data), encoding='utf-8')
    for _ in range(2):
        with pytest.raises(RuntimeError): config.load_config()
        assert config._CONFIG == {}
    config_file.write_text(json.dumps({'provider':'deepseek','srs':{'daily_new_limit':17}}))
    assert config.get_provider() == 'deepseek'
    assert config.get_srs_config()['daily_new_limit'] == 17

def test_missing_config_supports_first_run_and_malformed_remains_retryable(config_file, monkeypatch):
    assert config.get_ai_settings()['configured'] is False
    monkeypatch.setattr(config, '_CONFIG', {})
    config_file.write_text('{')
    with pytest.raises(RuntimeError, match='格式错误'): config.load_config()
    assert config._CONFIG == {}

def test_failed_save_preserves_existing_secret_and_configuration(config_file, monkeypatch):
    import sync_storage
    config_file.write_text(json.dumps({'provider':'deepseek'}))
    config.save_ai_settings('test-only', 'test-model')
    secret = config_file.parent / '.secrets' / 'deepseek.json'
    original = secret.read_bytes()
    before = config_file.read_bytes()
    def fail(*args): raise OSError('test write failure')
    monkeypatch.setattr(sync_storage, 'atomic_write', fail)
    with pytest.raises(OSError): config.save_ai_settings('new-key', 'new-model')
    assert secret.read_bytes() == original
    assert config_file.read_bytes() == before
    assert config.get_deepseek_config()['model'] == 'test-model'

def test_invalid_settings_never_replace_secret(config_file):
    config.save_ai_settings('test-key', 'test-model')
    secret = config_file.parent / '.secrets' / 'deepseek.json'
    before = secret.read_bytes()
    for key, model in [('bad key', 'model'), ('key', ' '), ('key', 123)]:
        with pytest.raises(ValueError): config.save_ai_settings(key, model)
    assert secret.read_bytes() == before
