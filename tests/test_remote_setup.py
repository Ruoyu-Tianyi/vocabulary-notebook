import json
import os
import stat

import pytest

from configure_remote import configure


def test_setup_does_not_overwrite_credentials_or_print_them(tmp_path, capsys):
    configure(tmp_path, 'owner@example.com', 'https://words.example.com')
    config = tmp_path / 'remote-access.json'
    login = tmp_path / 'remote-login.txt'
    before = config.read_bytes(), login.read_bytes()
    values = json.loads(before[0])
    assert 'password' not in values and len(values['password_hash']) == 128
    assert not capsys.readouterr().out
    with pytest.raises(FileExistsError):
        configure(tmp_path, 'other@example.com', 'https://other.example.com')
    assert (config.read_bytes(), login.read_bytes()) == before
    if os.name != 'nt':
        assert stat.S_IMODE(config.stat().st_mode) == 0o600
        assert stat.S_IMODE(login.stat().st_mode) == 0o600


def test_setup_keeps_an_existing_recovery_file(tmp_path):
    login = tmp_path / 'remote-login.txt'
    login.write_text('previous recovery details')
    with pytest.raises(FileExistsError):
        configure(tmp_path, 'owner@example.com', 'https://words.example.com')
    assert not (tmp_path / 'remote-access.json').exists()
    assert login.read_text() == 'previous recovery details'
