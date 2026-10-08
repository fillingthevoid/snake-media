"""Private SQLite recovery archives and separately sanitized public templates.

Run on the Docker host with a private JSON configuration, never in GitHub CI.
"""
import argparse
import copy
from contextlib import closing
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import urllib.request
import xml.etree.ElementTree as ET


def snapshot_database(source, target):
    with closing(sqlite3.connect(Path(source).resolve().as_uri() + '?mode=ro', uri=True, timeout=30)) as live:
        with closing(sqlite3.connect(target)) as backup:
            live.backup(backup, pages=512, sleep=0.05)
            if backup.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise ValueError('snapshot_integrity_failed')
    os.chmod(target, 0o600)


def digest(path):
    result = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def build_manifest(root):
    return {str(p.relative_to(root)).replace('\\', '/'): digest(p) for p in sorted(Path(root).rglob('*'))
            if p.is_file() and p.name != 'manifest.json'}


def verify_files(root, manifest):
    root = Path(root).resolve()
    for name, expected in manifest.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.is_symlink() or digest(path) != expected:
            raise ValueError('archive_checksum_failed')


def private_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.chmod(path, 0o600)


def snapshot_runtime(config, stage):
    """Capture explicitly configured private files; never recovery identities."""
    files = config.get('private_files', {})
    identity = Path(config['identity_file']).resolve()
    target = Path(stage) / 'runtime'
    target.mkdir(mode=0o700, exist_ok=True)
    for name, source in files.items():
        relative = Path(name)
        path = Path(source)
        if (relative.is_absolute() or '..' in relative.parts or path.is_symlink()
                or not path.is_file() or path.resolve() == identity):
            raise ValueError('invalid_private_backup_file')
        output = target / relative
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.suffix in {'.sqlite', '.sqlite3', '.db'}:
            snapshot_database(path, output)
        else:
            initial = digest(path)
            shutil.copyfile(path, output)
            if digest(path) != initial:
                raise ValueError('private_configuration_changed_during_backup')
        output.chmod(0o600)


def sanitize_workflows(workflows, secrets=()):
    known = set(s for s in secrets if isinstance(s, str) and len(s) >= 8)
    identities = {}

    def discover(value):
        if isinstance(value, dict):
            headers = value.get('headerParameters', {})
            if isinstance(headers, dict):
                for field in headers.get('parameters', []):
                    raw = field.get('value') if isinstance(field, dict) else None
                    if isinstance(raw, str) and raw and not raw.startswith(('=', '__')):
                        known.add(raw)
            field_name = str(value.get('name', ''))
            raw = value.get('value')
            if re.search(r'password|secret|token|api.?key', field_name, re.I) and isinstance(raw, str) and len(raw) >= 8 and not raw.startswith(('=', '__')):
                known.add(raw)
            for k, v in value.items():
                if re.search(r'allowed.*(?:user|channel|guild)|userId|chatId|channelId|guildId|rightValue', k, re.I) and isinstance(v, str) and re.fullmatch(r'-?\d{6,}(?:\s*,\s*-?\d{6,})*', v):
                    for identity in re.findall(r'-?\d{6,}', v):
                        identities.setdefault(identity, str(100000000000000001 + len(identities)))
                discover(v)
            if re.search(r'allowed.*(?:user|channel|guild)', field_name, re.I) and isinstance(raw, str):
                for identity in re.findall(r'-?\d{6,}', raw):
                    identities.setdefault(identity, str(100000000000000001 + len(identities)))
        elif isinstance(value, list):
            for v in value:
                discover(v)
        elif isinstance(value, str):
            if 'userId' in value:
                for array in re.findall(r'\[([\d\s,]+)\]\.includes\((?:Number\()?\$json\.userId', value):
                    for identity in re.findall(r'\d{6,16}', array):
                        identities.setdefault(identity, str(100000001 + len(identities)))
            for identity in re.findall(r'(?<![\dA-Za-z])\d{17,19}(?![\dA-Za-z])', value):
                identities.setdefault(identity, str(100000000000000001 + len(identities)))

    discover(workflows)

    def clean(value):
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, dict):
            result = {}
            for k, v in value.items():
                if k in {'pinData', 'staticData', 'meta', 'shared', 'tags', 'createdAt', 'updatedAt', 'versionId', 'activeVersionId', 'versionCounter', 'webhookId', 'parentFolderId'}:
                    continue
                if k == 'credentials' and isinstance(v, dict):
                    result[k] = {kind: {'id': 'CONFIGURE_' + kind.upper(), 'name': 'Configure ' + kind} for kind in v}
                elif k == 'active':
                    result[k] = False
                elif re.fullmatch(r'password|secret|token|apiKey|accessToken|refreshToken|clientSecret|username', k, re.I) and isinstance(v, str):
                    result[k] = '__CONFIGURE_PRIVATE_VALUE__'
                else:
                    result[k] = clean(v)
            return result
        if isinstance(value, str):
            for secret in sorted(known, key=len, reverse=True):
                value = value.replace(secret, '__CONFIGURE_PRIVATE_CREDENTIAL__')
            for identity, example in sorted(identities.items(), key=lambda x: len(x[0]), reverse=True):
                value = value.replace(identity, example)
            value = re.sub(r'\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))(?:\.\d{1,3}){1,3}\b', '192.168.1.10', value)
            value = re.sub(r'\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b', '100.100.100.100', value)
            value = re.sub(r'\b[a-zA-Z0-9.-]+\.ts\.net\b', 'media.example.ts.net', value)
            value = re.sub(r'https?://[^\s/\"\']+:[^\s/@\"\']+@', 'https://', value)
            return value
        return value

    cleaned = clean(copy.deepcopy(workflows))
    text = json.dumps(cleaned)
    if any(secret in text for secret in known) or any(identity in text for identity in identities if identity not in identities.values()):
        raise ValueError('public_export_private_value_detected')
    return cleaned


def public_settings(kind, rows):
    fields = {
        'qualityprofile': {'name', 'upgradeAllowed', 'cutoff', 'items', 'minFormatScore', 'minUpgradeFormatScore', 'cutoffFormatScore', 'formatItems', 'language'},
        'qualitydefinition': {'quality', 'title', 'weight', 'minSize', 'maxSize', 'preferredSize'},
        'customformat': {'name', 'includeCustomFormatWhenRenaming', 'specifications'},
        'delayprofile': {'enableUsenet', 'enableTorrent', 'preferredProtocol', 'usenetDelay', 'torrentDelay', 'bypassIfHighestQuality', 'bypassIfAboveCustomFormatScore', 'minimumCustomFormatScore', 'order'},
        'appprofile': {'name', 'enableRss', 'enableAutomaticSearch', 'enableInteractiveSearch', 'minimumSeeders'},
        'indexer': {'implementation', 'configContract', 'definitionName', 'protocol', 'enableRss', 'enableAutomaticSearch', 'enableInteractiveSearch', 'priority', 'fields'},
    }
    safe_indexer_fields = {'categories', 'animeCategories', 'minimumSeeders', 'seedRatio', 'seedTime', 'requiredFlags'}
    result = []
    for row in rows:
        item = {key: copy.deepcopy(value) for key, value in row.items() if key in fields[kind]}
        if kind == 'indexer':
            item['name'] = 'Indexer ' + str(len(result) + 1)
            item['fields'] = [{'name': v['name'], 'value': v.get('value')} for v in row.get('fields', []) if v.get('name') in safe_indexer_fields]
        result.append(item)
    return result


def api_read(base, key, endpoint):
    request = urllib.request.Request(base.rstrip('/') + '/' + endpoint, headers={'X-Api-Key': key, 'Accept': 'application/json'})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise ValueError('api_redirect_refused')
    with urllib.request.build_opener(NoRedirect, urllib.request.ProxyHandler({})).open(request, timeout=30) as response:
        raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError('api_response_too_large')
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError('api_response_not_list')
        return data


def public_export(config, snapshot, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    secrets = set()
    for app in ['radarr', 'sonarr', 'prowlarr']:
        root = Path(config['appdata']) / app
        key = ET.parse(root / 'config.xml').getroot().findtext('ApiKey')
        if not key:
            raise ValueError('missing_arr_api_key')
        secrets.add(key)
        kinds = ['appprofile', 'indexer'] if app == 'prowlarr' else ['qualityprofile', 'qualitydefinition', 'customformat', 'delayprofile']
        base = config['api_urls'][app]
        folder = output / app
        folder.mkdir(exist_ok=True)
        for kind in kinds:
            data = public_settings(kind, api_read(base, key, kind))
            private_json(folder / (kind + '.json'), sanitize_workflows(data, secrets))
    for app in config['containers']:
        d = json.loads((snapshot / app / 'container.json').read_text())
        for line in d['Config'].get('Env', []):
            if '=' in line:
                k, v = line.split('=', 1)
                if re.search(r'KEY|TOKEN|SECRET|PASSWORD', k) and len(v) >= 8:
                    secrets.add(v)
    secrets.add((snapshot / 'n8n/encryption-key.txt').read_text(encoding='utf-8'))
    bot_env = config.get('bot_env')
    if bot_env and Path(bot_env).exists():
        for line in Path(bot_env).read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                if re.search(r'KEY|TOKEN|SECRET|PASSWORD', k) and len(v.strip('"\'')) >= 8:
                    secrets.add(v.strip('"\''))
    db = snapshot / 'n8n/database.sqlite'
    with closing(sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        workflows = []
        for row in connection.execute('select id,name,active,nodes,connections,settings from workflow_entity where isArchived=0'):
            if not (row['name'].startswith(('Snake Media', 'Media Request', 'Add Movie - Radarr', 'Add TV Show - Sonarr')) and not re.search(r'TEST|Verify|Verification', row['name'], re.I)):
                continue
            value = dict(row)
            for field in ['nodes', 'connections', 'settings']:
                value[field] = json.loads(value[field] or '{}')
            workflows.append(value)
    public_json = output / 'n8n-current-media-workflows.json'
    private_json(public_json, sanitize_workflows(workflows, secrets))
    for file in output.rglob('*.json'):
        text = file.read_text(encoding='utf-8')
        if any(s in text for s in secrets):
            raise ValueError('public_export_secret_detected')
    print('Public templates prepared:', len(workflows), 'media workflows. Review before publishing.')


def safe_extract(archive, destination):
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar.getmembers():
            if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
                raise ValueError('unsupported_archive_member')
        tar.extractall(destination, filter='data')


def backup(config, public_output=None):
    os.umask(0o077)
    output = Path(config['output']).resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    recipient = Path(config['recipient_file']).read_text().strip()
    if not re.fullmatch(r'age1[a-z0-9]+', recipient):
        raise ValueError('invalid_age_recipient')
    identity = Path(config['identity_file'])
    if not identity.is_file() or identity.stat().st_mode & 0o077:
        raise ValueError('identity_permissions_not_private')
    if shutil.disk_usage(output).free < 4 * 1024**3:
        raise ValueError('backup_space_insufficient')
    databases = {'radarr': 'radarr.db', 'sonarr': 'sonarr.db', 'prowlarr': 'prowlarr.db', 'n8n': 'database.sqlite'}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    archive = output / ('snake-stack-' + stamp + '.tar.gz.age')
    if archive.exists():
        raise ValueError('archive_already_exists')
    with tempfile.TemporaryDirectory(prefix='snapshot-', dir=output) as directory:
        stage = Path(directory) / 'snapshot'
        stage.mkdir(mode=0o700)
        for app, name in databases.items():
            source = Path(config['appdata']) / app
            target = stage / app
            target.mkdir(mode=0o700)
            cfg = source / ('config' if app == 'n8n' else 'config.xml')
            initial = digest(cfg)
            shutil.copyfile(cfg, target / cfg.name)
            snapshot_database(source / name, target / name)
            if digest(cfg) != initial:
                raise ValueError('configuration_changed_during_backup')
            raw = subprocess.check_output(['docker', 'inspect', config['containers'][app]])
            container = json.loads(raw)[0]
            private_json(target / 'container.json', container)
            if app == 'n8n':
                env = dict(line.split('=', 1) for line in container['Config']['Env'] if '=' in line)
                key = env.get('N8N_ENCRYPTION_KEY') or json.loads(cfg.read_text()).get('encryptionKey')
                if not key:
                    raise ValueError('n8n_encryption_key_missing')
                (target / 'encryption-key.txt').write_text(key, encoding='utf-8')
                for extra in ['nodes', 'binaryData', 'custom']:
                    if (source / extra).exists():
                        shutil.copytree(source / extra, target / extra, symlinks=False)
            print('Snapshot checked:', app, flush=True)
        snapshot_runtime(config, stage)
        manifest = build_manifest(stage)
        private_json(stage / 'manifest.json', {'format': 1, 'createdAt': stamp, 'files': manifest})
        compressed = Path(directory) / 'snapshot.tar.gz'
        with tarfile.open(compressed, 'w:gz') as tar:
            for file in sorted(stage.rglob('*')):
                if file.is_file():
                    tar.add(file, arcname=str(file.relative_to(stage)), recursive=False)
        pending = Path(str(archive) + '.partial')
        subprocess.run(['age', '-r', recipient, '-o', str(pending), str(compressed)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        decrypted = Path(directory) / 'verified.tar.gz'
        subprocess.run(['age', '-d', '-i', str(identity), '-o', str(decrypted), str(pending)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        restored = Path(directory) / 'verify'
        restored.mkdir(mode=0o700)
        safe_extract(decrypted, restored)
        verify_files(restored, manifest)
        for app, name in databases.items():
            with closing(sqlite3.connect((restored / app / name).resolve().as_uri() + '?mode=ro', uri=True)) as db:
                if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise ValueError('restored_database_integrity_failed')
        pending.replace(archive)
        Path(str(archive) + '.sha256').write_text(digest(archive) + '  ' + archive.name + '\n', encoding='utf-8')
        print('Encrypted backup and isolated restore verification passed:', archive.name, flush=True)
        if public_output:
            public_export(config, stage, public_output)
    # Prune only completed encrypted archives, never source data or failed runs.
    keep = max(2, int(config.get('keep', 14)))
    completed = sorted(output.glob('snake-stack-*.tar.gz.age'), reverse=True)
    for old in completed[keep:]:
        marker = Path(str(old) + '.sha256')
        if not old.is_symlink() and marker.is_file() and digest(old) == marker.read_text().split()[0]:
            old.unlink()
            marker.unlink()
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--public-output', type=Path)
    args = parser.parse_args()
    try:
        path = args.config
        if path.stat().st_mode & 0o077:
            raise ValueError('config_permissions_not_private')
        archive = backup(json.loads(path.read_text()), args.public_output)
        print('Archive bytes:', archive.stat().st_size)
    except Exception as error:
        print('Backup failed:', type(error).__name__, '(private details withheld)', flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
