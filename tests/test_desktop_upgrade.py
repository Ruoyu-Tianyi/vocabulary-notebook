"""Upgrade failure boundaries use synthetic local data and fake installers only."""
import json
from pathlib import Path

import pytest

import maintenance
from tools import desktop_upgrade as upgrade


def fixture_profile(tmp_path):
    profile = tmp_path / 'profile'
    data = profile / 'data'
    (data / '.secrets').mkdir(parents=True)
    (data / 'words.json').write_text(json.dumps({'words': [{'word': 'fixture',
        'review_history': [{'rating': 3}], 'srs': {'due': 'fixture'}}]}))
    (data / 'config.json').write_text(json.dumps({'provider': 'deepseek',
        'deepseek': {'api_key': 'synthetic-only'}, 'sync': {'credentials_dir': '.secrets'}}))
    (data / '.secrets/token.json').write_text('synthetic-token')
    (data / 'future-feature.json').write_text('preserve-unknown-files')
    return profile


def installer_fixture(tmp_path):
    installer = tmp_path / 'Vocove-fixture.exe'
    installer.write_bytes(b'not-executable')
    Path(str(installer) + '.sha256').write_text(f'{maintenance.digest(installer)}  {installer.name}\n')
    return installer


def test_checksum_rejects_tampering_before_stopping(tmp_path, monkeypatch):
    installer = installer_fixture(tmp_path)
    installer.write_bytes(b'tampered')
    monkeypatch.setattr(upgrade, 'stop_application', lambda *a: pytest.fail('must not stop'))
    with pytest.raises(ValueError, match='SHA-256'):
        upgrade.upgrade(installer, tmp_path / 'Vocove.exe', tmp_path / 'profile', tmp_path / 'backups', 'rev')


def test_snapshot_preserves_unknown_files_credentials_and_learning(tmp_path):
    profile = fixture_profile(tmp_path)
    backup = upgrade.snapshot(profile, tmp_path / 'backups', 'old-revision')
    assert maintenance.verify_backup(backup)['review_events'] == 1
    assert (backup / 'desktop-data/.secrets/token.json').read_text() == 'synthetic-token'
    (profile / 'data/future-feature.json').write_text('new-data')
    with pytest.raises(RuntimeError, match='不一致'):
        maintenance.verify_backup(backup)
    assert (profile / 'data/future-feature.json').read_text() == 'new-data'


@pytest.mark.parametrize('failure', ['installer', 'smoke', 'data-change'])
def test_failure_never_restarts_or_restores(tmp_path, monkeypatch, failure):
    profile = fixture_profile(tmp_path)
    monkeypatch.setattr(upgrade, 'stop_application', lambda *a: None)
    monkeypatch.setattr(upgrade.subprocess, 'Popen', lambda *a, **kw: pytest.fail('must not restart'))

    def fail(installer, executable, backup):
        if failure == 'data-change':
            (profile / 'data/words.json').write_text('{"words": []}')
            maintenance.verify_backup(backup)
        raise RuntimeError(failure)

    monkeypatch.setattr(upgrade, 'install_and_check', fail)
    with pytest.raises(RuntimeError):
        upgrade.upgrade(installer_fixture(tmp_path), tmp_path / 'Vocove.exe', profile,
                        tmp_path / 'backups', 'old-revision')
    backups = list((tmp_path / 'backups').iterdir())
    assert len(backups) == 1
    assert 'failed' in json.loads((backups[0] / 'upgrade.json').read_text())['status']
    if failure == 'data-change':
        assert (profile / 'data/words.json').read_text() == '{"words": []}'


def test_restart_happens_only_after_verification(tmp_path, monkeypatch):
    profile = fixture_profile(tmp_path)
    events = []
    monkeypatch.setattr(upgrade, 'stop_application', lambda *a: events.append('stop'))
    monkeypatch.setattr(upgrade, 'install_and_check', lambda *a: events.append('verified'))
    monkeypatch.setattr(upgrade.subprocess, 'CREATE_NO_WINDOW', 0, raising=False)
    monkeypatch.setattr(upgrade.subprocess, 'Popen', lambda *a, **kw: events.append('restart'))
    upgrade.upgrade(installer_fixture(tmp_path), tmp_path / 'Vocove.exe', profile,
                    tmp_path / 'backups', 'old-revision')
    assert events == ['stop', 'verified', 'restart']


def test_smoke_environment_does_not_mutate_parent_or_use_real_data(tmp_path, monkeypatch):
    monkeypatch.setenv('VOCAB_DESKTOP_USER_DATA_DIR', 'real-profile')
    monkeypatch.setenv('VOCOVE_DATA_FILE', 'real-words.json')
    monkeypatch.setenv('ELECTRON_RUN_AS_NODE', '1')
    env = upgrade.isolated_environment(tmp_path)
    assert env['VOCOVE_DESKTOP_USER_DATA_DIR'] == str(tmp_path)
    assert 'VOCAB_DESKTOP_USER_DATA_DIR' not in env
    assert 'VOCOVE_DATA_FILE' not in env
    assert 'ELECTRON_RUN_AS_NODE' not in env
    assert upgrade.os.environ['VOCOVE_DATA_FILE'] == 'real-words.json'
