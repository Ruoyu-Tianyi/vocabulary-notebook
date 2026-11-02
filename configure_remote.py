"""Configure private login locally; never print credentials or overwrite an existing setup."""
import argparse
import json
import os
import secrets
from pathlib import Path
from remote_password import password_hash
from remote_gateway import validate_settings


def configure(root, email, origin):
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    path, login = root / 'remote-access.json', root / 'remote-login.txt'
    if path.exists() or login.exists():
        raise FileExistsError('Existing configuration or login details retained without changes.')
    password, salt = secrets.token_urlsafe(24), secrets.token_hex(16)
    settings = validate_settings({'auth_mode': 'password', 'public_origin': origin,
                                  'email': email, 'password_salt': salt,
                                  'password_hash': password_hash(password, salt),
                                  'session_secret': secrets.token_urlsafe(48)})
    # Exclusive creation prevents overwriting another setup; 0600 restricts POSIX access.
    for target, content in (
        (path, json.dumps(settings, indent=2)),
        (login, f'私人学习入口：{origin}\n账号：{email}\n密码：{password}\n\n请保存至自己的密码管理器。此文件只留本机，不上传或发送。\n'),
    ):
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--email', required=True)
    parser.add_argument('--origin', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / '.secrets'
    configure(root, args.email, args.origin)
    print('Configured. Login details saved only in .secrets/remote-login.txt')


if __name__ == '__main__':
    main()
