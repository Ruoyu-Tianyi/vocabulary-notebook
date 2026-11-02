import json

import pytest

from migrate_legacy_config import migrate


def test_migration_is_explicit_preserves_state_and_is_idempotent(tmp_path):
    config = tmp_path / 'config.json'
    original = {'provider': 'deepseek', 'srs': {'daily_new_limit': 12}, 'sync': {'interval_seconds': 60}}
    config.write_text(json.dumps(original), encoding='utf-8')
    secrets = tmp_path / '.secrets'
    secrets.mkdir()
    secret = secrets / 'deepseek.json'
    secret.write_text(json.dumps({'api_key': 'synthetic-key', 'model': 'synthetic-model'}), encoding='utf-8')
    words = tmp_path / 'words.json'
    words.write_bytes(b'unchanged-library')
    assert migrate(tmp_path).startswith('migrated')
    result = json.loads(config.read_text())
    assert result['deepseek']['api_key'] == 'synthetic-key'
    assert result['srs'] == original['srs'] and result['sync'] == original['sync']
    assert json.loads((tmp_path / 'config.json.pre-v151.bak').read_text()) == original
    assert secret.exists() and words.read_bytes() == b'unchanged-library'
    assert migrate(tmp_path) == 'already migrated'


def test_existing_backup_cannot_be_overwritten(tmp_path):
    (tmp_path / 'config.json').write_text('{"provider":"deepseek"}')
    (tmp_path / '.secrets').mkdir()
    (tmp_path / '.secrets/deepseek.json').write_text('{"api_key":"synthetic","model":"test"}')
    (tmp_path / 'config.json.pre-v151.bak').write_bytes(b'previous backup')
    with pytest.raises(FileExistsError):
        migrate(tmp_path)
    assert (tmp_path / 'config.json.pre-v151.bak').read_bytes() == b'previous backup'
