"""Pull completed archives with a restricted SSH key; verify before retention."""
import argparse
import hashlib
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def pull(config):
    from backup_serve import ARCHIVE
    destination = Path(config['destination'])
    destination.mkdir(parents=True, exist_ok=True)
    command = [config.get('ssh', 'ssh'), '-T', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
               '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15',
               '-o', 'ServerAliveInterval=30', '-i', config['identity_file'], config['host']]
    result = subprocess.run(command + ['list'], capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError('backup_server_unavailable')
    rows = json.loads(result.stdout)
    if not isinstance(rows, list) or not rows:
        raise ValueError('no_verified_server_archives')
    downloaded = 0
    for row in rows:
        name, expected = row['name'], row['sha256']
        if not isinstance(name, str) or not ARCHIVE.fullmatch(name) or not isinstance(expected, str) or len(expected) != 64:
            raise ValueError('invalid_backup_listing')
        path = destination / name
        if path.is_file() and path.stat().st_size == row['bytes'] and sha256(path) == expected:
            continue
        temporary = destination / (name + '.partial')
        with temporary.open('wb') as file:
            result = subprocess.run(command + ['get ' + name], stdout=file, stderr=subprocess.PIPE, timeout=3600)
        if result.returncode or temporary.stat().st_size != row['bytes'] or sha256(temporary) != expected:
            raise ValueError('backup_transfer_failed_verification')
        os.replace(temporary, path)
        Path(str(path) + '.sha256').write_text(expected + '  ' + name + '\n', encoding='utf-8')
        downloaded += 1
    newest = sorted(destination.glob('snake-stack-*.tar.gz.age'), reverse=True)
    keep = max(2, int(config.get('keep', 14)))
    for old in newest[keep:]:
        marker = Path(str(old) + '.sha256')
        if ARCHIVE.fullmatch(old.name) and not old.is_symlink() and marker.is_file() and sha256(old) == marker.read_text().split()[0]:
            old.unlink()
            marker.unlink()
    print('PASS off-server backups verified; new archives:', downloaded, 'retained:', min(len(newest), keep))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    log_path = args.config.parent / 'pull.log'
    if log_path.exists() and log_path.stat().st_size > 1024 * 1024:
        os.replace(log_path, Path(str(log_path) + '.previous'))
    with log_path.open('a', encoding='utf-8') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            pull(json.loads(args.config.read_text()))
        except Exception as error:
            print('Backup pull failed:', type(error).__name__, '(private details withheld)', file=sys.stderr)
            raise SystemExit(1)


if __name__ == '__main__':
    main()
