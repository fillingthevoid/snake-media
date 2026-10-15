"""Add owned /status search navigation without changing media write paths."""
import copy
import importlib.util
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('status_match_cards', ROOT/'n8n/my-requests-simplification/patch.py')
cards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cards)


def build(source):
    rows = cards.build(source)
    by = {w['id']:w for w in rows}
    for wid, prep, dest in [('HXtTzVTrpNZMZVt3','Validate Discord Request','channelId'), ('0e67KTcphqxEKNsh','Prepare Request','chatId')]:
        nodes = {n['name']:n for n in by[wid]['nodes']}
        nodes['My Requests Command?']['parameters']['conditions']['conditions'][0]['leftValue'] = (
            "={{ /^\\/?status(?:@[A-Za-z0-9_]+)?(?:\\s+.*)?$/i.test($('"+prep+"').first().json.text.trim()) }}")
        params = nodes['Prepare My Requests Actor']['parameters']
        code = params['jsCode']
        anchor = 'messageId:p.messageId,requestedAt:p.requestedAt'
        if anchor+',query:' not in code:
            if anchor not in code:
                raise ValueError('Unknown My Requests actor')
            code = code.replace(anchor, anchor+",query:(p.text.trim().match(/^\\/?status(?:@[A-Za-z0-9_]+)?(?:\\s+(.*))?$/i)?.[1]||'').trim().slice(0,200)")
        params['jsCode'] = code
        cond = nodes['My Requests Callback?']['parameters']['conditions']['conditions'][0]
        if '|next|previous|' not in cond['leftValue']:
            if '|refresh|' not in cond['leftValue']:
                raise ValueError('Unknown My Requests callback')
            cond['leftValue'] = cond['leftValue'].replace('|refresh|','|next|previous|refresh|',1)

    w = by['snakeMyRequestsV1']
    nodes = {n['name']:n for n in w['nodes']}
    read = nodes['Read My Requests']['parameters']
    read['returnAll'] = True
    read.pop('limit',None)
    # Repeated delivery reuses the owned menu and refreshes its selected title.
    existing = nodes['Existing Request Menu']['parameters']
    marker = "\nif(typeof module!=='undefined')module.exports="
    end = existing['jsCode'].index(';',existing['jsCode'].index(marker))+1
    existing['jsCode'] = existing['jsCode'][:end]+"\nreturn [{json:$json.row}];"

    def cloned(name, template, params):
        n = copy.deepcopy(nodes[template])
        n.update(id=str(uuid.uuid5(uuid.NAMESPACE_URL,'snake-status-match:'+name)),name=name,position=[1820,1320+len(additions)*180])
        n['parameters'] = params
        return n

    additions = []
    condition = copy.deepcopy(nodes['Request Status Needed?']['parameters'])
    condition['conditions']['conditions'][0].update(
        id='Initial Request Status?',
        leftValue="={{ !$json.version && $json.state==='preview' && Date.parse($json.expiresAt)>Date.now() && Number.isInteger(JSON.parse($json.contextJson).myRequests.selected) }}")
    additions.append(cloned('Initial Request Status?','Request Status Needed?',condition))
    additions.append(cloned('Prepare Initial Request Status','Prepare Exact Request Status',{'jsCode':
        "const row=$json,b=JSON.parse(row.contextJson).myRequests,t=b.titles[b.selected];if(!t)throw Error('Invalid selected request');return [{json:{source:row.source,userId:row.userId,query:'',mediaType:t.mediaType,mediaId:t.mediaId}}];"}))
    additions.append(cloned('Read Initial Request Status','Read Exact Request Status',copy.deepcopy(nodes['Read Exact Request Status']['parameters'])))
    code = cards.policy('my-requests/policy.js')+"\nreturn [{json:card($('Initial Request Status?').first().json,Date.now(),$json)}];"
    additions.append(cloned('Render Initial Request Status','Render Request Menu',{'jsCode':code}))
    for n in additions:
        if n['name'] in nodes:
            # Preserve native identity and canvas position on repeated overlays.
            nodes[n['name']]['parameters'] = n['parameters']
        else:
            w['nodes'].append(n)

    def connect(parent, *targets):
        w['connections'][parent] = {'main':[[{'node':target,'type':'main','index':0}] for target in targets]}
    connect('Store Request Menu','Initial Request Status?')
    connect('Existing Request Menu','Initial Request Status?')
    connect('Initial Request Status?','Prepare Initial Request Status','Render Request Menu')
    connect('Prepare Initial Request Status','Read Initial Request Status')
    connect('Read Initial Request Status','Render Initial Request Status')
    return rows


if __name__=='__main__':
    import sys
    source = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    rows = build(source)
    changed = [w for w, old in zip(rows,source) if w != old]
    for w in changed:
        for key in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived']:
            w.pop(key,None)
        w.update(active=False,pinData={})
    target = Path(sys.argv[2])
    target.write_text(json.dumps(changed,indent=2)+'\n',encoding='utf-8')
    target.chmod(0o600)
    print('Scoped status navigation updates:',len(changed))
