"""Configure private login locally; never print credentials or overwrite an existing setup."""
import argparse
import json
import secrets
from pathlib import Path
from remote_password import password_hash
from remote_gateway import validate_settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--email', required=True)
    parser.add_argument('--origin', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / '.secrets'
    root.mkdir(exist_ok=True)
    path = root / 'remote-access.json'
    if path.exists():
        raise SystemExit('Configuration already exists; retained without changes.')
    password, salt = secrets.token_urlsafe(24), secrets.token_hex(16)
    settings = validate_settings({'auth_mode':'password','public_origin':args.origin,
                                  'email':args.email, 'password_salt':salt,
                                  'password_hash':password_hash(password, salt),
                                  'session_secret':secrets.token_urlsafe(48)})
    path.write_text(json.dumps(settings, indent=2), encoding='utf-8')
    login = root / 'remote-login.txt'
    login.write_text('私人学习入口：'+args.origin+'\n账号：'+args.email+'\n密码：'+password+'\n\n请保存至自己的密码管理器。此文件只留本机，不上传或发送。\n',encoding='utf-8')
    print('Configured. Login details saved only in .secrets/remote-login.txt')


if __name__ == '__main__':
    main()
