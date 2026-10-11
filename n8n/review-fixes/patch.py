"""Targeted, idempotent review fixes over the current bundle or a private export."""
import copy
import importlib.util
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[2]
RETENTION_MARKER = "if(typeof module!=='undefined')module.exports={parseChange,prepareChange,planChange,changeCard,guideAction,titleKey};"


def build(source):
    rows = copy.deepcopy(source)
    spec = importlib.util.spec_from_file_location('review_policy_embed', ROOT / 'n8n/request-usability/patch.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    policy = helper.policy('n8n/retention-controls/policy.js')
    for workflow in rows:
        for node in workflow['nodes']:
            code = node.get('parameters', {}).get('jsCode', '')
            if RETENTION_MARKER in code:
                node['parameters']['jsCode'] = helper.embed(
                    code, '// Confirmation and immutable retention amendments.', [RETENTION_MARKER], policy)

    commit = next(w for w in rows if w['name'] == 'Snake Media - Commit Media Under Lock')
    nodes = {n['name']: n for n in commit['nodes']}
    search = nodes['Search Confirmed Movie']
    endpoint = search['parameters']['url']
    if not isinstance(endpoint, str) or not endpoint.startswith(('http://', 'https://')) or not endpoint.endswith('/command'):
        raise ValueError('Unknown movie command endpoint; review the installation URL before applying')
    base = endpoint[:-len('command')]
    restore_name = 'Restore Requested Movie Monitoring'
    verify_name = 'Read Requested Movie Monitoring'
    check_name = 'Verify Requested Movie Monitoring'
    branch = commit['connections']['Movie Missing?']['main'][0]
    if len(branch) != 1 or branch[0]['node'] not in ('Search Confirmed Movie', restore_name):
        raise ValueError('Unknown missing-movie route; nothing prepared')

    def install(template, name, parameters, x):
        identity = str(uuid.uuid5(uuid.NAMESPACE_URL, 'snake-review-fixes/' + name))
        previous = nodes.get(name)
        if previous and previous['id'] != identity:
            raise ValueError('Conflicting review-fix node identity')
        node = copy.deepcopy(template)
        node.update(id=identity, name=name, parameters=parameters, position=[x, 0])
        # Monitoring writes/verification must stop the branch on an unknown result.
        node.pop('continueOnFail', None)
        node.pop('onError', None)
        if previous:
            commit['nodes'][commit['nodes'].index(previous)] = node
        else:
            commit['nodes'].append(node)

    restore = copy.deepcopy(search['parameters'])
    restore.update(method='PUT', url=base + 'movie/editor',
                   jsonBody="={{ {movieIds:[Number($json.mediaId)],monitored:true} }}")
    install(search, restore_name, restore, 2400)

    reader = nodes['Find Confirmed Movie']
    verify = copy.deepcopy(reader['parameters'])
    verify.update(method='GET', url="={{ " + json.dumps(base + 'movie/') +
                  " + $('Movie Search Plan').first().json.mediaId }}")
    verify.pop('sendQuery', None)
    verify.pop('queryParameters', None)
    install(reader, verify_name, verify, 2600)

    code = """const p=$('Movie Search Plan').first().json;
const rows=$input.all().map(x=>x.json);
if(rows.length!==1||rows[0].id!==Number(p.mediaId)||rows[0].tmdbId!==Number(p.externalId)||rows[0].monitored!==true)throw Error('Requested movie monitoring not verified');
return [{json:p}];"""
    template = {'type': 'n8n-nodes-base.code', 'typeVersion': 2}
    install(template, check_name, {'jsCode': code}, 2800)

    def edge(target):
        return {'node': target, 'type': 'main', 'index': 0}
    commit['connections']['Movie Missing?']['main'][0] = [edge(restore_name)]
    for start, end in [(restore_name, verify_name), (verify_name, check_name), (check_name, 'Search Confirmed Movie')]:
        commit['connections'][start] = {'main': [[edge(end)]]}
    return rows


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('Keep the original export: use a separate output path')
    rows = build(json.loads(args.input.read_text(encoding='utf-8-sig')))
    args.output.write_text(json.dumps(rows, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    args.output.chmod(0o600)
    print('Prepared review fixes:', len(rows), 'workflows; nothing imported or published')
