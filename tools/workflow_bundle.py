"""Validate the canonical bundle or apply the current efficiency overlay privately."""
import argparse
import importlib.util
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CURRENT=ROOT/'config-templates/n8n-current-media-workflows.json'


def compare(expected, actual):
    """Return changed runtime paths, never the potentially private values.

    Literal HTTP endpoints and native table IDs are installation bindings.
    Expressions, code, policy constants, credential kinds and graph edges remain
    significant. This is a drift check, not proof of runtime equivalence.
    """
    def normalize(value, key=''):
        if isinstance(value, dict):
            if key == 'credentials':
                return {kind: True for kind in value}
            if key == 'dataTableId':
                return {'binding': 'native_table'}
            return {k: normalize(v, k) for k, v in value.items()
                    if k not in {'cachedResultName', 'cachedResultUrl', '__rl'}}
        if isinstance(value, list):
            return [normalize(v) for v in value]
        if key == 'url' and isinstance(value, str) and value.startswith(('http://', 'https://')):
            return '__INSTALLATION_ENDPOINT__'
        if key == 'jsCode' and isinstance(value, str):
            # Only the Telegram adapter's final configured username argument.
            return re.sub(r'return prepare\(\$json,\s*"[A-Za-z0-9_]+"\);',
                          'return prepare($json,"__TELEGRAM_BOT_USERNAME__");', value)
        return value

    def runtime(rows):
        out = {}
        for w in rows:
            out[w['id']] = {
                'nodes': {n['name']: normalize({k: v for k, v in n.items()
                          if k not in {'id', 'position', 'notes', 'notesInFlow', 'webhookId'}}) for n in w['nodes']},
                'connections': normalize(w['connections']),
                'settings': normalize(w.get('settings', {}))}
        return out

    changed = []
    def visit(left, right, path):
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(left.keys() | right.keys()):
                child = path + '.' + key if path else key
                if key not in left or key not in right:
                    changed.append(child)
                else:
                    visit(left[key], right[key], child)
        elif left != right:
            changed.append(path)
    visit(runtime(expected), runtime(actual), '')
    return changed


def validate(workflows):
    if not isinstance(workflows,list) or not workflows:
        raise ValueError('Expected a nonempty workflow list')
    ids=[w.get('id') for w in workflows]
    if any(not isinstance(i,str) or not i for i in ids) or len(set(ids))!=len(ids):
        raise ValueError('Missing or duplicate workflow IDs')
    for w in workflows:
        names=[n['name'] for n in w['nodes']]
        node_ids=[n['id'] for n in w['nodes']]
        if len(set(names))!=len(names) or len(set(node_ids))!=len(node_ids):
            raise ValueError('Duplicate node identity in '+w['id'])
        for source,ports in w['connections'].items():
            if source not in names:raise ValueError('Unknown edge source in '+w['id'])
            for groups in ports.values():
                for edges in groups:
                    for edge in edges:
                        if edge['node'] not in names:raise ValueError('Unknown edge target in '+w['id'])
        for n in w['nodes']:
            if not n['type'].endswith('.executeWorkflow'):continue
            ref=n['parameters'].get('workflowId')
            if isinstance(ref,dict):ref=ref.get('value')
            if ref not in ids:raise ValueError('Unknown child workflow in '+w['id'])
    return len(workflows)


def apply_efficiency(workflows):
    validate(workflows)
    spec=importlib.util.spec_from_file_location('efficiency_patch',ROOT/'n8n/efficiency-pass/patch.py')
    patch=importlib.util.module_from_spec(spec);spec.loader.exec_module(patch)
    result=patch.patch_workflows(workflows)
    validate(result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    check=sub.add_parser('validate');check.add_argument('input',nargs='?',type=Path,default=CURRENT)
    drift=sub.add_parser('compare');drift.add_argument('actual',type=Path)
    drift.add_argument('--expected',type=Path,default=CURRENT)
    apply=sub.add_parser('apply-efficiency');apply.add_argument('input',type=Path);apply.add_argument('output',type=Path)
    args=parser.parse_args()
    if args.command=='compare':
        expected=json.loads(args.expected.read_text(encoding='utf-8'))
        actual=json.loads(args.actual.read_text(encoding='utf-8'))
        validate(expected);validate(actual)
        changed=compare(expected,actual)
        for path in changed:print('Changed:',path)
        print('Runtime drift paths:',len(changed))
        raise SystemExit(1 if changed else 0)
    rows=json.loads(args.input.read_text(encoding='utf-8'))
    if args.command=='validate':print('Valid bundle:',validate(rows),'workflows')
    else:
        rows=apply_efficiency(rows)
        args.output.write_text(json.dumps(rows,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')
        args.output.chmod(0o600)
        print('Prepared private overlay:',len(rows),'workflows; nothing imported or published')


if __name__=='__main__':main()
