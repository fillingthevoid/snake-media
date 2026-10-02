"""Restricted SSH command: list/get completed encrypted archives only."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

ARCHIVE = re.compile(r'snake-stack-\d{8}T\d{6}Z\.tar\.gz\.age')


def parse_command(command):
    parts = command.split()
    if parts == ['list']:
        return 'list', None
    if len(parts) == 2 and parts[0] == 'get' and ARCHIVE.fullmatch(parts[1]):
        return 'get', parts[1]
    raise ValueError('unsupported_backup_command')


def completed(root):
    rows = []
    for file in sorted(Path(root).glob('snake-stack-*.tar.gz.age')):
        marker = Path(str(file) + '.sha256')
        if not ARCHIVE.fullmatch(file.name) or file.is_symlink() or not marker.is_file() or marker.is_symlink():
            continue
        parts = marker.read_text().split()
        if len(parts) == 2 and re.fullmatch(r'[a-f0-9]{64}', parts[0]) and parts[1] == file.name:
            rows.append({'name': file.name, 'bytes': file.stat().st_size, 'sha256': parts[0]})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    try:
        action, name = parse_command(os.environ.get('SSH_ORIGINAL_COMMAND', ''))
        rows = completed(args.root)
        if action == 'list':
            print(json.dumps(rows))
        else:
            if name not in {r['name'] for r in rows}:
                raise ValueError('backup_not_completed')
            with (args.root / name).open('rb') as source:
                while block := source.read(1024 * 1024):
                    sys.stdout.buffer.write(block)
    except Exception:
        print('Backup request rejected.', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
