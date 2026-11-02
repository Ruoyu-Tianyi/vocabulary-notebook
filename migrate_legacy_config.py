"""Explicit, offline migration of the fork's legacy DeepSeek credential file."""
import argparse
import json
from pathlib import Path

import instance_lock
from sync_storage import atomic_write


def migrate(root):
    root = Path(root).resolve()
    with instance_lock.acquire(root / 'words.json'):
        path = root / 'config.json'
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if data.get('fork_legacy_migrated'):
            return 'already migrated'
        secrets = Path(data.get('sync', {}).get('credentials_dir', '.secrets'))
        if not secrets.is_absolute():
            secrets = root / secrets
        legacy = secrets / 'deepseek.json'
        if not legacy.is_file():
            return 'no legacy credentials'
        values = json.loads(legacy.read_text(encoding='utf-8-sig'))
        if not isinstance(values, dict) or any(not isinstance(values.get(k), str) or not values[k].strip()
                                               for k in ('api_key', 'model')):
            raise ValueError('Legacy DeepSeek settings are incomplete; no files changed')
        backup = root / 'config.json.pre-v151.bak'
        # Never replace an earlier recovery point, or print credentials.
        with backup.open('xb') as stream:
            stream.write(path.read_bytes())
        data.setdefault('deepseek', {}).update({k: values[k].strip() for k in ('api_key', 'model')})
        data['fork_legacy_migrated'] = True
        atomic_write(path, data)
        return 'migrated; original config and credential file retained'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    print(migrate(args.root))
