"""Run a private application recovery drill without production mounts/network."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from stack_backup import digest, safe_extract, verify_files

APPS = {'radarr': 7878, 'sonarr': 8989, 'prowlarr': 9696, 'n8n': 5678}


def container_command(app, image, root, name):
    if app not in APPS or not re.fullmatch(r'drill-[a-z0-9-]{1,64}', name):
        raise ValueError('invalid_isolated_container')
    source = (Path(root) / app).resolve()
    if not source.is_relative_to(Path(root).resolve()) or not source.is_dir():
        raise ValueError('missing_restored_application')
    target = '/home/node/.n8n' if app == 'n8n' else '/config'
    args = ['docker', 'run', '-d', '--pull', 'never', '--name', name,
            '--network', 'none', '--memory', '1g', '--cpus', '2',
            '--mount', f'type=bind,src={source},dst={target}']
    if app == 'n8n':
        args += ['--env-file', str(Path(root) / 'n8n.env')]
    else:
        args += ['-e', 'PUID=1000', '-e', 'PGID=1000']
    return args + [image]


def run_drill(config, report_path):
    os.umask(0o077)
    report_path = Path(report_path).resolve()
    archives = sorted(Path(config['output']).glob('snake-stack-*.tar.gz.age'))
    if not archives:
        raise ValueError('no_completed_archive')
    archive = archives[-1]
    marker = Path(str(archive) + '.sha256')
    if not marker.is_file() or digest(archive) != marker.read_text().split()[0]:
        raise ValueError('archive_checksum_failed')
    report = {'archive': archive.name, 'applications': {}, 'network': 'none',
              'productionMounts': False, 'containersRemoved': False}
    names = []
    with tempfile.TemporaryDirectory(prefix='restore-drill-', dir=report_path.parent) as tmp:
        root = Path(tmp)
        encrypted_output = root / 'archive.tar.gz'
        subprocess.run(['age', '-d', '-i', config['identity_file'], '-o', str(encrypted_output),
                        str(archive)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        data = root / 'restored'
        data.mkdir()
        safe_extract(encrypted_output, data)
        manifest = json.loads((data / 'manifest.json').read_text())
        verify_files(data, manifest['files'])
        report['checksumsVerified'] = True
        report['privateRuntimeIncluded'] = (data / 'runtime').is_dir()
        report['customNodesIncluded'] = (data / 'n8n/custom').is_dir()
        key = (data / 'n8n/encryption-key.txt').read_text()
        if '\n' in key or '\r' in key:
            raise ValueError('invalid_encryption_key')
        (data / 'n8n.env').write_text('N8N_ENCRYPTION_KEY=' + key + '\nN8N_DIAGNOSTICS_ENABLED=false\nN8N_VERSION_NOTIFICATIONS_ENABLED=false\n')
        for app in APPS:
            for path in [data / app, *(data / app).rglob('*')]:
                os.chown(path, 1000, 1000)
        with (root / 'private.log').open('w') as log:
            def run(args, capture=False):
                return subprocess.run(args, check=True, stdout=subprocess.PIPE if capture else log,
                                      stderr=log, text=True, timeout=180)
            try:
                for app in APPS:
                    image = run(['docker', 'inspect', config['containers'][app], '--format', '{{.Image}}'], True).stdout.strip()
                    name = 'drill-snake-' + app + '-' + str(os.getpid())
                    # Deactivate only the restored database using the native CLI.
                    if app == 'n8n':
                        args = container_command(app, image, data, name)
                        args[2] = '--rm'
                        args[-1:] = ['--entrypoint', 'n8n', image, 'unpublish:workflow', '--all']
                        run(args)
                    run(container_command(app, image, data, name))
                    names.append(name)
                    endpoint = '/healthz' if app == 'n8n' else '/ping'
                    healthy = False
                    for attempt in range(30):
                        probe = subprocess.run(['docker', 'exec', name, 'sh', '-c',
                                                'wget -q -O /dev/null http://127.0.0.1:' + str(APPS[app]) + endpoint],
                                               stdout=log, stderr=log, timeout=10)
                        if probe.returncode == 0:
                            healthy = True
                            break
                        time.sleep(2)
                    if not healthy:
                        raise ValueError('restored_application_not_healthy_' + app)
                    report['applications'][app] = {'startup': 'passed'}
                    if app == 'n8n':
                        run(['docker', 'exec', name, 'n8n', 'export:credentials', '--all', '--decrypted', '--output=/tmp/drill-credentials.json'])
                        count = run(['docker', 'exec', name, 'node', '-e',
                                     "const fs=require('fs');const r=JSON.parse(fs.readFileSync('/tmp/drill-credentials.json'));console.log(r.length);fs.unlinkSync('/tmp/drill-credentials.json');"], True).stdout.strip()
                        report['applications'][app]['credentialsDecrypted'] = int(count)
                    run(['docker', 'rm', '-f', name])
                    names.remove(name)
            finally:
                removed = True
                for name in names:
                    removed = subprocess.run(['docker', 'rm', '-f', name], stdout=log, stderr=log, timeout=30).returncode == 0 and removed
                report['containersRemoved'] = removed
                report_path.write_text(json.dumps(report, indent=2) + '\n')
                report_path.chmod(0o600)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_drill(json.loads(args.config.read_text()), args.report)
        print('Isolated restored application checks passed:', ', '.join(result['applications']))
    except Exception as exc:
        print('Restore drill failed:', type(exc).__name__, '(private details withheld)')
        raise SystemExit(1)
