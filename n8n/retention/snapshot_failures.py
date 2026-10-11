"""Defer only failed snapshot reads, before any media mutation can run."""
import copy
import json
from pathlib import Path
import uuid

READS = ('Read Retention Movie', 'Read Retention Series', 'Read Retention Episodes')
SUMMARY = "const i=$('Media Input').first().json;console.warn('Retention snapshot unavailable: '+i.requests[0].mediaType+':'+i.requests[0].mediaId);return [{json:{mediaType:i.requests[0].mediaType,mediaId:i.requests[0].mediaId,mode:i.mode,decisions:[],snapshotUnavailable:true}}];"


def build(source):
    rows = copy.deepcopy(source)
    worker = next(w for w in rows if w['id'] == 'snakeRetentionMediaV1')
    nodes = {n['name']: n for n in worker['nodes']}
    for name in READS:
        n = nodes[name]
        if n['type'] != 'n8n-nodes-base.httpRequest' or n['parameters'].get('method', 'GET') != 'GET':
            raise ValueError('Unexpected snapshot reader; nothing prepared')
        if n.get('onError') not in (None, 'continueErrorOutput'):
            raise ValueError('Unexpected error route; nothing prepared')
        n['onError'] = 'continueErrorOutput'
        edges = worker['connections'][name]['main']
        route = [{'node': 'Media Read Unavailable', 'type': 'main', 'index': 0}]
        if len(edges) == 1:
            edges.append(route)
        elif len(edges) != 2 or edges[1] != route:
            raise ValueError('Conflicting snapshot error route')
    for name in ('Movie Snapshot Response', 'Series Snapshot Response'):
        p = nodes[name]['parameters']
        old = 'return [{json:mediaSnapshot($json)||{gone:true}}];'
        new = 'try{' + old + '}catch(error){return [{json:{unavailable:true}}];}'
        if new not in p['jsCode']:
            if p['jsCode'].count(old) != 1:
                raise ValueError('Unexpected snapshot validator')
            p['jsCode'] = p['jsCode'].replace(old, new)
    for name in ('Movie Still Exists?', 'Series Still Exists?'):
        p = nodes[name]['parameters']['conditions']['conditions'][0]
        expr = p['leftValue']
        if '!$json.unavailable' not in expr:
            if '!$json.gone' not in expr:
                raise ValueError('Unexpected snapshot gate')
            p['leftValue'] = expr.replace('!$json.gone', '!$json.gone&&!$json.unavailable')
    nodes['Media Already Removed']['parameters']['jsCode'] = (
        "if($json.unavailable){" + SUMMARY + "}const i=$('Media Input').first().json;"
        "return [{json:{mediaType:i.requests[0].mediaType,mediaId:i.requests[0].mediaId,mode:i.mode,decisions:[],alreadyRemoved:true}}];")
    if 'Media Read Unavailable' not in nodes:
        worker['nodes'].append({
            'id': str(uuid.uuid5(uuid.NAMESPACE_URL, 'snake-retention/read-unavailable')),
            'name': 'Media Read Unavailable', 'type': 'n8n-nodes-base.code',
            'typeVersion': 2, 'position': [1500, 600], 'parameters': {'jsCode': SUMMARY},
        })
    elif nodes['Media Read Unavailable']['parameters'].get('jsCode') != SUMMARY:
        raise ValueError('Conflicting snapshot summary')
    return rows


if __name__ == '__main__':
    import sys
    result = build(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
