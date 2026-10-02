"""Check publishable files for common credential/export mistakes; hide all values."""
import argparse
import json
from pathlib import Path
import re
import subprocess

TOKEN = re.compile(r'(?:mfa\.[A-Za-z0-9_-]{60,}|[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{25,}|sk-(?:proj-)?[A-Za-z0-9_-]{32,})')
SENSITIVE = re.compile(r'key|token|authorization|secret|password', re.I)


def placeholder(value):
    return not value or isinstance(value, str) and value.startswith(('__', 'CONFIGURE_', '={{'))


def export_issues(value):
    issues = []
    if isinstance(value, list):
        for item in value:
            issues.extend(export_issues(item))
    elif isinstance(value, dict):
        if value.get('pinData') or value.get('staticData'):
            issues.append('pinned/runtime data')
        if isinstance(value.get('meta'), dict) and value['meta'].get('instanceId'):
            issues.append('instance metadata')
        if 'nodes' in value and value.get('active') is True:
            issues.append('active workflow template')
        credentials = value.get('credentials', {})
        if isinstance(credentials, dict):
            for ref in credentials.values():
                if isinstance(ref, dict) and not str(ref.get('id', '')).startswith('CONFIGURE_'):
                    issues.append('instance credential reference')
        headers = value.get('headerParameters', {})
        if isinstance(headers, dict):
            for header in headers.get('parameters', []):
                if isinstance(header, dict) and SENSITIVE.search(str(header.get('name', ''))) and not placeholder(header.get('value')):
                    issues.append('literal credential header')
        for key, item in value.items():
            if re.fullmatch(r'apiKey|accessToken|refreshToken|clientSecret|password|secret|token', key, re.I) and isinstance(item, str) and not placeholder(item):
                issues.append('literal credential field')
            issues.extend(export_issues(item))
    return issues


def scan(root, paths=None):
    root = Path(root)
    paths = paths if paths is not None else [p.relative_to(root) for p in root.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts]
    findings = []
    for relative in paths:
        path = root / relative
        name = path.name
        forbidden = (name == '.env' or name.startswith('.env.') and name != '.env.example'
                     or path.suffix in {'.db', '.sqlite', '.sqlite3', '.gz', '.zip', '.tar', '.png', '.jpg'}
                     or 'private' in name and path.suffix == '.json')
        if forbidden:
            findings.append(f'{relative}: private configuration/state/archive')
            continue
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding='utf-8-sig')
        except UnicodeError:
            findings.append(f'{relative}: unexpected binary file')
            continue
        if TOKEN.search(text):
            findings.append(f'{relative}: token-shaped string')
        if path.suffix == '.json':
            try:
                reasons = export_issues(json.loads(text))
                findings.extend(f'{relative}: {reason}' for reason in sorted(set(reasons)))
            except ValueError:
                findings.append(f'{relative}: malformed JSON')
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    paths = None
    if (args.root / '.git').exists():
        raw = subprocess.check_output(['git', '-C', str(args.root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'])
        paths = sorted(set(raw.decode('utf-8').strip('\0').split('\0')) - {''})
    findings = scan(args.root, paths)
    for finding in findings:
        print(finding)
    if findings:
        raise SystemExit(1)
    print('PASS public-file checks. Also review changes manually; this scan cannot prove all secrets are absent.')


if __name__ == '__main__':
    main()
