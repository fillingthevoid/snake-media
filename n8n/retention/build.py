"""Generate retention workflows, patching a current export when supplied.

Private input/output stay on snake. Local artifacts contain placeholder headers.
"""
import copy
import json
import sys
import uuid
from pathlib import Path

R = Path(__file__).parent
OUT = R / 'workflows'
OUT.mkdir(exist_ok=True)
POLICY = (R / 'policy.js').read_text(encoding='utf-8')
ENGINE = (R / 'engine.js').read_text(encoding='utf-8')
if len(sys.argv) > 1:
    source = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
else:
    source = [json.loads(p.read_text(encoding='utf-8')) for p in (R.parent / 'confirmation/workflows').glob('*.json')]
    source += [json.loads(p.read_text(encoding='utf-8')) for p in (R.parent / 'tracking/notification-workflows').glob('*.json')]
S = {w['id']: w for w in source}
RECORDS = 'snake_media_retention_records'
CONTROL = 'snake_media_retention_control'
SCHEMAS = {RECORDS: dict.fromkeys(['key', 'kind', 'payloadJson'], 'string'), CONTROL: dict.fromkeys(['key', 'owner'], 'string')}


def node(name, kind, p=None, **extra):
    return dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL, 'snake-retention/' + name)), name=name,
                type='n8n-nodes-base.' + kind, typeVersion={'code': 2, 'if': 2.3, 'dataTable': 1.1,
                'executeWorkflow': 1.3, 'executeWorkflowTrigger': 1.1, 'httpRequest': 4.4,
                'scheduleTrigger': 1.3, 'webhook': 2.1, 'respondToWebhook': 1.4}.get(kind, 1),
                parameters=p or {}, position=[0, 0], **extra)


def code(name, script): return node(name, 'code', {'jsCode': script})
def trigger(name): return node(name, 'executeWorkflowTrigger', {'inputSource': 'passthrough'})
def get(w, name): return next(n for n in w['nodes'] if n['name'] == name)
def eq(k, v): return {'keyName': k, 'condition': 'eq', 'keyValue': v}


def data(name, table, op, filters=None, values=None):
    p = {'resource': 'row', 'operation': op, 'dataTableId': {'__rl': True, 'mode': 'name', 'value': table},
         'matchType': 'allConditions', 'filters': {'conditions': filters or []}, 'options': {}}
    if op == 'get': p['returnAll'] = True
    if values is not None:
        p['columns'] = {'mappingMode': 'defineBelow', 'value': values,
                        'schema': [{'id': k, 'displayName': k, 'type': SCHEMAS[table][k],
                        'display': True, 'required': False, 'defaultMatch': False, 'canBeUsedToMatch': True} for k in values]}
    return node(name, 'dataTable', p, alwaysOutputData=True)


def iff(name, expression):
    return node(name, 'if', {'conditions': {'options': {'caseSensitive': True, 'leftValue': '',
        'typeValidation': 'strict', 'version': 3}, 'conditions': [{'id': 'condition',
        'leftValue': '={{ ' + expression + ' }}', 'rightValue': '',
        'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}], 'combinator': 'and'}, 'options': {}})


def call(name, wid, each=False):
    return node(name, 'executeWorkflow', {'workflowId': {'__rl': True, 'mode': 'id', 'value': wid},
        'workflowInputs': {'mappingMode': 'passThrough'}, 'mode': 'each' if each else 'once',
        'options': {'waitForSubWorkflow': True}}, alwaysOutputData=True)


def wf(wid, name, nodes):
    return {'id': wid, 'name': name, 'nodes': nodes, 'connections': {}, 'active': False,
            'settings': {'executionOrder': 'v1', 'executionTimeout': 600}, 'pinData': {}}


def edge(w, a, b, port=0):
    ports = w['connections'].setdefault(a, {}).setdefault('main', [])
    while len(ports) <= port: ports.append([])
    ports[port] = [{'node': b, 'type': 'main', 'index': 0}]


def chain(w, *names):
    for a, b in zip(names, names[1:]): edge(w, a, b)


HEADERS = {}
for kind, wid, name in [('movie', 'snakeInspectRequestV1', 'Read Requested Movie'),
                        ('tv', 'snakeInspectRequestV1', 'Read Requested Episodes'),
                        ('jellyfin', 'snakeCompletionScanV1', 'Read Jellyfin Library')]:
    HEADERS[kind] = copy.deepcopy(get(S[wid], name)['parameters']['headerParameters'])
BASE = {'movie': 'http://192.168.1.10:7878/api/v3/', 'tv': 'http://192.168.1.10:8989/api/v3/', 'jellyfin': 'http://192.168.1.10:8096/'}


def http(name, kind, path, method='GET', body=None, query=None, full=False):
    url = '={{ ' + repr(BASE[kind]) + ' + (' + path[1:] + ') }}' if path.startswith('=') else BASE[kind] + path
    p = {'method': method, 'url': url, 'sendHeaders': True, 'headerParameters': copy.deepcopy(HEADERS[kind]), 'options': {'timeout': 20000}}
    if body is not None: p.update(sendBody=True, specifyBody='json', jsonBody=body)
    if query: p.update(sendQuery=True, queryParameters={'parameters': [{'name': k, 'value': v} for k, v in query.items()]})
    if full: p['options']['response'] = {'response': {'fullResponse': True, 'neverError': True}}
    return node(name, 'httpRequest', p, alwaysOutputData=True)


def save(w):
    for i, n in enumerate(w['nodes']): n['position'] = [(i % 7) * 270, (i // 7) * 240]
    for k in ['createdAt', 'updatedAt', 'versionId', 'activeVersionId', 'versionCounter', 'shared', 'triggerCount', 'meta', 'isArchived']: w.pop(k, None)
    w.update(active=False, pinData={})
    path = OUT / (w['name'] + '.json')
    path.write_text(json.dumps(w, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if len(sys.argv) > 1: path.chmod(0o600)


# Only the lock owner may write retention records. Upsert runs under that lock.
store = wf('snakeRetentionStoreV1', 'Snake Media - Store Retention Record', [
    trigger('Record Input'),
    data('Read Store Lock', CONTROL, 'get', [eq('key', 'global')]),
    code('Validate Store Owner', "const rows=$input.all().filter(x=>x.json.key);const r=$('Record Input').first().json;if(rows.length!==1||!r.owner||rows[0].json.owner!==r.owner||!r.key||!r.kind||typeof r.payloadJson!=='string')throw new Error('Retention write requires lock');JSON.parse(r.payloadJson);return [{json:r}];"),
    data('Upsert Retention Record', RECORDS, 'upsert', [eq('key', '={{ $json.key }}')], {k: '={{ $json.'+k+' }}' for k in SCHEMAS[RECORDS]})])
chain(store, *[n['name'] for n in store['nodes']]); save(store)

# Initialize through native Data Table nodes. This authenticated setup endpoint is
# unpublished after deployment; it never invokes media services.
web = copy.deepcopy(get(S['HXtTzVTrpNZMZVt3'], 'Discord Webhook'))
web.update(name='Retention Setup', id=node('Retention Setup', 'webhook')['id'], webhookId='snake-retention-setup-v1')
web['parameters']['path'] = 'snake-retention-setup'
setup = wf('snakeRetentionSetupV1', 'Snake Media - Setup Retention', [web])
for table, schema in SCHEMAS.items():
    setup['nodes'].append(node('Create '+table, 'dataTable', {'resource': 'table', 'operation': 'create', 'tableName': table,
        'columns': {'column': [{'name': k, 'type': v} for k, v in schema.items()]}, 'options': {'createIfNotExists': True}}))
setup['nodes'] += [data('Find Global Lock', CONTROL, 'get', [eq('key', 'global')]),
    code('Check Setup Lock', "const rows=$input.all().filter(x=>x.json.key);if(rows.length>1)throw new Error('Duplicate global lock');return [{json:{exists:rows.length===1}}];"),
    iff('Lock Exists?', '$json.exists'), data('Insert Global Lock', CONTROL, 'insert', values={'key': 'global', 'owner': ''}),
    data('Find Configuration', CONTROL, 'get', [eq('key', 'mode')]),
    iff('Configuration Exists?', "$json.key==='mode'"),
    data('Insert Preview Configuration', CONTROL, 'insert', values={'key': 'mode', 'owner': 'preview'}),
    node('Setup Response', 'respondToWebhook', {'respondWith': 'json', 'responseBody': '={{ {ready:true} }}'})]
chain(setup, *[n['name'] for n in setup['nodes'][:6]])
edge(setup, 'Lock Exists?', 'Find Configuration'); edge(setup, 'Lock Exists?', 'Insert Global Lock', 1)
chain(setup, 'Insert Global Lock', 'Find Configuration', 'Configuration Exists?')
edge(setup, 'Configuration Exists?', 'Setup Response'); edge(setup, 'Configuration Exists?', 'Insert Preview Configuration', 1)
edge(setup, 'Insert Preview Configuration', 'Setup Response'); save(setup)

# One coordinator protects both request commits and scheduled cleanup. A failure
# leaves the owner recorded for explicit recovery after inspecting the execution.
coord = wf('snakeRetentionCoordinatorV1', 'Snake Media - Retention Coordinator', [
    trigger('Coordinator Input'), data('Read Global Lock', CONTROL, 'get', [eq('key', 'global')]),
    code('Validate Global Lock', "const rows=$input.all().filter(x=>x.json.key);if(rows.length!==1)throw new Error('Retention lock not initialized');return [{json:{available:rows[0].json.owner===''}}];"),
    iff('Lock Available?', '$json.available'),
    data('Acquire Global Lock', CONTROL, 'update', [eq('key', 'global'), eq('owner', '')], {'owner': '={{ String($execution.id) }}'}),
    code('Verify Global Lock', "const r=$input.first().json;return [{json:{owned:r.owner===String($execution.id)}}];"),
    iff('Lock Owned?', '$json.owned'),
    code('Locked Input', "return [{json:{...$('Coordinator Input').first().json,owner:String($execution.id)}}];"),
    iff('Commit Job?', "$json.job==='commit'"), call('Run Locked Commit', 'snakeCommitMediaBodyV2'),
    call('Run Locked Scan', 'snakeRetentionScanV1'), code('Save Locked Result', 'return [{json:{result:$json}}];'),
    data('Release Global Lock', CONTROL, 'update', [eq('key', 'global'), eq('owner', '={{ String($execution.id) }}')], {'owner': ''}),
    code('Return Locked Result', "if($json.owner!=='')throw new Error('Lock release failed');return [{json:$('Save Locked Result').first().json.result}];"),
    code('Busy Response', "return [{json:{version:1,status:'notice',text:'Snake Media is processing another request or performing maintenance. Please send a new request in a moment.',busy:true}}];")])
chain(coord, 'Coordinator Input', 'Read Global Lock', 'Validate Global Lock', 'Lock Available?', 'Acquire Global Lock', 'Verify Global Lock', 'Lock Owned?', 'Locked Input', 'Commit Job?', 'Run Locked Commit', 'Save Locked Result', 'Release Global Lock', 'Return Locked Result')
edge(coord, 'Lock Available?', 'Busy Response', 1); edge(coord, 'Lock Owned?', 'Busy Response', 1)
edge(coord, 'Commit Job?', 'Run Locked Scan', 1); edge(coord, 'Run Locked Scan', 'Save Locked Result'); save(coord)

wrapper = wf('snakeCommitMediaV1', 'Snake Media - Commit Confirmed Media', [trigger('Commit Input'),
    code('Commit Job', "return [{json:{...$json,job:'commit'}}];"), call('Coordinate Commit', coord['id'])])
chain(wrapper, *[n['name'] for n in wrapper['nodes']]); save(wrapper)

preview = copy.deepcopy(S['snakePreviewMediaV1'])
select = get(preview, 'Select Preview')['parameters']['jsCode']
select = select.replace('const c=i.context;', "let retentionPolicy;try{retentionPolicy=parseRetention(i.context.text,i.mediaType);}catch{return [{json:{version:1,status:'notice',text:'Please specify one retention choice: keep for 14 days, or keep permanently. Use a whole number from 1 to 3650 days.'}}];}const c={...i.context,retentionPolicy};")
get(preview, 'Select Preview')['parameters']['jsCode'] = POLICY+'\n'+select
render = (R.parent/'confirmation/render.js').read_text(encoding='utf-8')
render = render.replace('let choices=[],text=header;', "const rp=JSON.parse(r.contextJson||'{}').retentionPolicy;let choices=[],text=header+(rp?'\\n\\n'+retentionText(rp,r.mediaType):'');if(r.mediaType==='tv'&&rp)text+='\\nSelected seasons and future seasons will be monitored.';")
render = render.replace('Specials and future episodes are excluded.', 'Specials are excluded; new episodes and future seasons will download automatically.').replace('Only aired episodes will be requested.', 'Aired episodes will be searched now; upcoming episodes will be monitored.')
get(preview, 'Render Preview')['parameters']['jsCode'] = POLICY+'\n'+render
save(preview)
act = copy.deepcopy(S['snakeConfirmMediaV1']); get(act, 'Render Choice')['parameters']['jsCode'] = POLICY+'\n'+render
get(act, 'Verify Claim')['parameters']['jsCode'] = get(act, 'Verify Claim')['parameters']['jsCode'].replace('return [{json:r}];', 'return [{json:{...r,actionAccepted:true}}];')
act['nodes'].append(code('Mark Accepted Action', "const valid=!!$('Validate Action').first().json.row;const accepted=valid&&$('Verify Claim').first().json.actionAccepted===true;return [{json:{...$json,actionAccepted:accepted}}];"))
edge(act, 'Render Choice', 'Mark Accepted Action'); edge(act, 'Commit Confirmed Media', 'Mark Accepted Action'); save(act)

body = copy.deepcopy(S['snakeCommitMediaV1']); body.update(id='snakeCommitMediaBodyV2', name='Snake Media - Commit Media Under Lock')
get(body, 'Confirmed Metadata')['parameters']['jsCode'] = get(body, 'Confirmed Metadata')['parameters']['jsCode'].replace("if(r.state", "if(!r.owner)throw new Error('Missing retention owner');if(r.state")
get(body, 'Movie Snapshot')['parameters']['jsCode'] = get(body, 'Movie Snapshot')['parameters']['jsCode'].replace('retentionDays:null,', 'retentionDays:c.retentionPolicy?.days??null,retentionExplicit:true,')
tv_snapshot = """const p=$('Confirmed Metadata').first().json;const episodes=$input.all().map(x=>x.json);let selected;try{selected=subscription(episodes,p.choice,Date.now());}catch{return [{json:{version:1,status:'notice',text:'Episode metadata is not available yet. Nothing was searched. Please try again later.'}}];}const s=$('Series Identity').first().json;const chosen=episodes.filter(e=>selected.episodeIds.includes(String(e.id)));return [{json:{...p.context,mediaType:'tv',mediaId:String(s.id),externalId:String(s.tvdbId),title:s.title,episodeIds:selected.episodeIds,preexistingFileIds:chosen.filter(e=>e.episodeFileId>0).map(e=>String(e.episodeFileId)),baselineCaptured:true,retentionDays:p.context.retentionPolicy?.days??null,retentionExplicit:true,subscription:selected,missingIds:chosen.filter(e=>!e.hasFile&&!e.episodeFileId&&Number.isFinite(Date.parse(e.airDateUtc))&&Date.parse(e.airDateUtc)<=Date.now()).map(e=>e.id),seasons:selected.selectedSeasons}}];"""
get(body, 'Selected Episode Snapshot')['parameters']['jsCode'] = POLICY+'\n'+tv_snapshot
for kind, snap, register, after in [('Movie', 'Movie Snapshot', 'Register Movie Before Search', 'Movie Search Plan'), ('TV', 'Selected Episode Snapshot', 'Register TV Before Search', 'TV Search Plan')]:
    make = 'Build '+kind+' Subscription'; store_name = 'Save '+kind+' Subscription'
    body['nodes'] += [code(make, "const r=$('"+snap+"').first().json;const owner=$('Commit Input').first().json.owner;return [{json:{owner,key:'request:'+$json.requestKey,kind:'subscription',payloadJson:JSON.stringify({requestKey:$json.requestKey,mediaType:r.mediaType,mediaId:r.mediaId,...(r.subscription||{}),episodeIds:r.episodeIds,protectedFileIds:r.preexistingFileIds})}}];"), call(store_name, store['id'])]
    chain(body, register, make, store_name, after)
    get(body, after)['parameters']['jsCode'] = "const tracked=$('"+register+"').first().json;const saved=$('"+store_name+"').first().json;if(!tracked.requestKey||saved.key!=='request:'+tracked.requestKey)throw new Error('Tracking or subscription not saved');return [{json:$('"+snap+"').first().json}];"
body['nodes'] += [http('Read Series Monitoring', 'tv', "='series/'+$('Selected Episode Snapshot').first().json.mediaId"),
    code('Build Series Monitoring', "if(!$json.id)throw new Error('Missing series');return [{json:{...$json,monitored:true,monitorNewItems:'none'}}];"),
    http('Enable Series Monitoring', 'tv', "='series/'+$json.id", 'PUT', '={{ $json }}'),
    http('Monitor Subscribed Episodes', 'tv', 'episode/monitor', 'PUT', "={{ {episodeIds:$('Selected Episode Snapshot').first().json.episodeIds.map(Number),monitored:true} }}")]
chain(body, 'Save TV Subscription', 'Read Series Monitoring', 'Build Series Monitoring', 'Enable Series Monitoring', 'Monitor Subscribed Episodes', 'TV Search Plan')
get(body, 'TV Result')['parameters']['jsCode'] = get(body, 'TV Result')['parameters']['jsCode'].replace('✅ Selected episodes are already in Sonarr.', '✅ Selected episodes are tracked in Sonarr.').replace("}}];", "+'\\nNew episodes and future seasons will download automatically.'}}];")
save(body)

played = wf('snakeRetentionPlayedV1', 'Snake Media - Read Watched Items', [trigger('User Input'),
    http('Read User Played Items', 'jellyfin', "='Users/'+$json.Id+'/Items'", query={
        'Recursive': 'true', 'IncludeItemTypes': 'Movie,Episode', 'Fields': 'Path', 'Filters': 'IsPlayed',
        'Limit': '500', 'EnableImages': 'false', 'EnableUserData': 'true'}),
    code('Watched Page Result', "const pages=$input.all().map(x=>x.json);if(pages.some(p=>!Array.isArray(p.Items)||!Number.isInteger(p.TotalRecordCount)))throw new Error('Incomplete played response');const items=pages.flatMap(p=>p.Items);if(pages[0].TotalRecordCount>items.length)throw new Error('Incomplete played pagination');return [{json:{Items:items}}];")])
get(played, 'Read User Played Items')['parameters']['options']['pagination'] = {'pagination': {
    'paginationMode': 'updateAParameterInEachRequest', 'parameters': {'parameters': [
        {'type': 'qs', 'name': 'StartIndex', 'value': '={{ $pageCount * 500 }}'}]},
    'paginationCompleteWhen': 'other', 'completeExpression': '={{ $response.body.Items.length < 500 }}',
    'limitPagesFetched': True, 'maxRequests': 100}}
chain(played, *[n['name'] for n in played['nodes']]); save(played)

scan = wf('snakeRetentionScanV1', 'Snake Media - Scan Retention Under Lock', [trigger('Scan Input'),
    data('Read Retention Mode', CONTROL, 'get', [eq('key', 'mode')]),
    code('Validate Scan Mode', "if(!['preview','enabled'].includes($json.owner))throw new Error('Invalid retention mode');return [{json:{mode:$json.owner}}];"),
    data('Read All Requests', 'snake_media_requests', 'get'), code('One Retention Read','return [{json:{}}];'),
    data('Read All Retention Records', RECORDS, 'get'), code('One User Read','return [{json:{}}];'),
    http('Read Jellyfin Users', 'jellyfin', 'Users'),
    code('Validate Jellyfin Users', "const rows=$input.all();if(!rows.length||rows.some(x=>typeof x.json.Id!=='string'))throw new Error('Cannot enumerate Jellyfin users');return rows;"),
    call('Read Each User Played Items', played['id'], True),
    code('Watched Snapshot', "return [{json:{watched:$input.all().flatMap(x=>{if(!Array.isArray(x.json.Items))throw new Error('Incomplete watched snapshot');return x.json.Items;})}}];"),
    http('Read Active Playback', 'jellyfin', 'Sessions'),
    code('Group Retention Requests', "const requests=$('Read All Requests').all().map(x=>x.json).filter(r=>r.requestKey&&r.userId!=='1'&&r.state==='registered');const records=$('Read All Retention Records').all().map(x=>x.json).filter(r=>r.key);const groups=new Map();for(const r of requests){const k=r.mediaType+':'+r.mediaId;if(!groups.has(k))groups.set(k,[]);groups.get(k).push(r);}return [...groups.values()].map(rs=>({json:{owner:$('Scan Input').first().json.owner,mode:$('Validate Scan Mode').first().json.mode,requests:rs,records,watched:$('Watched Snapshot').first().json.watched,sessions:$input.all().map(x=>x.json)}}));"),
    iff('Has Request Group?', '!!$json.requests'), call('Process Each Retention Group', 'snakeRetentionMediaV1', True),
    code('Scan Summary', "const results=$input.all().map(x=>x.json);return [{json:{scanned:results.length,groups:results}}];")])
get(scan, 'Group Retention Requests')['parameters']['jsCode'] = get(scan, 'Group Retention Requests')['parameters']['jsCode'].replace('return [...groups.values()].map', 'const result=[...groups.values()].map').replace("sessions:$input.all().map(x=>x.json)}}));", "sessions:$input.all().map(x=>x.json)}}));return result.length?result:[{json:{skip:true}}];")
chain(scan, *[n['name'] for n in scan['nodes']]); edge(scan, 'Has Request Group?', 'Scan Summary', 1); save(scan)

worker = wf('snakeRetentionMediaV1', 'Snake Media - Reconcile Media Retention', [trigger('Media Input'),
    iff('Retention Movie?', "$json.requests[0].mediaType==='movie'"),
    http('Read Retention Movie', 'movie', "='movie/'+$json.requests[0].mediaId", full=True),
    code('Movie Snapshot Response',POLICY+'\nreturn [{json:mediaSnapshot($json)||{gone:true}}];'),iff('Movie Still Exists?','!$json.gone'),
    http('Read Retention Series', 'tv', "='series/'+$json.requests[0].mediaId", full=True),
    code('Series Snapshot Response',POLICY+'\nreturn [{json:mediaSnapshot($json)||{gone:true}}];'),iff('Series Still Exists?','!$json.gone'),
    http('Read Retention Episodes', 'tv', 'episode', query={'seriesId': "={{ $('Media Input').first().json.requests[0].mediaId }}", 'includeEpisodeFile': 'true'}),
    code('Plan Retention', POLICY+'\n'+ENGINE+"\nconst i=$('Media Input').first().json;const movie=i.requests[0].mediaType==='movie';const media=movie?$input.first().json:$('Series Snapshot Response').first().json;const episodes=movie?[]:$input.all().map(x=>x.json);return [{json:{...planMedia({...i,media,episodes,now:Date.now()}),owner:i.owner,mode:i.mode,mediaType:i.requests[0].mediaType,mediaId:i.requests[0].mediaId,media}}];"),
    code('Records To Persist', "const p=$json;const records=p.mode==='enabled'?p.records:p.records.filter(r=>r.kind==='file');return records.length?records.map(r=>({json:{...r,owner:p.owner}})):[{json:{skip:true}}];"),
    iff('Has Retention Record?', '!!$json.key'), call('Persist Retention Records', store['id'], True),
    code('Monitoring Plan', "return [{json:$('Plan Retention').first().json}];"),
    iff('Enable Episode Monitoring?', "$json.mode==='enabled'&&$json.mediaType==='tv'&&$json.monitorIds.length>0"),
    http('Enable Reconciled Series', 'tv', "='series/'+$json.mediaId", 'PUT', '={{ {...$json.media,monitored:true,monitorNewItems:"none"} }}'),
    http('Enable Reconciled Episodes', 'tv', 'episode/monitor', 'PUT', "={{ {episodeIds:$('Plan Retention').first().json.monitorIds,monitored:true} }}"),
    code('New Episode Search Plan', "return [{json:$('Plan Retention').first().json}];"),
    iff('New Aired Episodes?', "$json.mode==='enabled'&&$json.searchIds.length>0"),
    http('Search New Aired Episodes', 'tv', 'command', 'POST', '={{ {name:"EpisodeSearch",episodeIds:$json.searchIds} }}'),
    code('Due File Plan', "const p=$('Plan Retention').first().json;return p.mode==='enabled'&&p.deletions.length?p.deletions.map(d=>({json:{...d,owner:p.owner}})):[{json:{skip:true}}];"),
    iff('Has Due File?', '!!$json.fileId'), call('Delete Each Due File', 'snakeRetentionDeleteV1', True),
    code('Media Retention Summary', "const p=$('Plan Retention').first().json;return [{json:{mediaType:p.mediaType,mediaId:p.mediaId,mode:p.mode,decisions:p.decisions,plannedMonitorIds:p.monitorIds,plannedSearchIds:p.searchIds}}];")])
worker['nodes'].append(code('Media Already Removed',"const i=$('Media Input').first().json;return [{json:{mediaType:i.requests[0].mediaType,mediaId:i.requests[0].mediaId,mode:i.mode,decisions:[],alreadyRemoved:true}}];"))
chain(worker, 'Media Input', 'Retention Movie?', 'Read Retention Movie', 'Movie Snapshot Response', 'Movie Still Exists?', 'Plan Retention', 'Records To Persist', 'Has Retention Record?', 'Persist Retention Records', 'Monitoring Plan', 'Enable Episode Monitoring?', 'Enable Reconciled Series', 'Enable Reconciled Episodes', 'New Episode Search Plan', 'New Aired Episodes?', 'Search New Aired Episodes', 'Due File Plan', 'Has Due File?', 'Delete Each Due File', 'Media Retention Summary')
edge(worker, 'Retention Movie?', 'Read Retention Series', 1); chain(worker, 'Read Retention Series', 'Series Snapshot Response','Series Still Exists?', 'Read Retention Episodes', 'Plan Retention')
edge(worker,'Movie Still Exists?','Media Already Removed',1);edge(worker,'Series Still Exists?','Media Already Removed',1)
edge(worker, 'Has Retention Record?', 'Monitoring Plan', 1); edge(worker, 'Enable Episode Monitoring?', 'New Episode Search Plan', 1)
edge(worker, 'New Aired Episodes?', 'Due File Plan', 1); edge(worker, 'Has Due File?', 'Media Retention Summary', 1); save(worker)

delete = wf('snakeRetentionDeleteV1', 'Snake Media - Delete Expired File', [trigger('Deletion Input'),
    data('Verify Deletion Lock', CONTROL, 'get', [eq('key', 'global')]),
    code('Check Deletion Owner', "const d=$('Deletion Input').first().json;const locks=$input.all().filter(x=>x.json.key);if(locks.length!==1||!d.owner||locks[0].json.owner!==d.owner||d.due!==true||Date.parse(d.expiresAt)>Date.now())throw new Error('Deletion lock or deadline invalid');return [{json:d}];"),
    http('Recheck Active Playback', 'jellyfin', 'Sessions'),
    code('Playback Clear', "const d=$('Deletion Input').first().json;const blocked=$input.all().some(x=>x.json.NowPlayingItem&&(!x.json.NowPlayingItem.Path||x.json.NowPlayingItem.Path==='/data'+d.path));return [{json:{...d,blocked}}];"),
    iff('Playback Safe?', '!$json.blocked'), iff('Delete Movie File?', "$json.mediaType==='movie'"),
    http('Recheck Movie File', 'movie', "='moviefile/'+$json.fileId"),
    http('Recheck Episode File', 'tv', "='episodefile/'+$json.fileId"),
    code('Validate File Identity', "const d=$('Deletion Input').first().json;const f=$json;if(f.id!==d.fileId||f.path!==d.path||Date.parse(f.dateAdded)!==Date.parse(d.importedAt))throw new Error('File changed after retention snapshot');return [{json:{owner:d.owner,key:d.key,kind:'file',payloadJson:JSON.stringify({...d,state:'deleting'})}}];"),
    call('Record Deletion Intent', store['id']), code('Unmonitor Plan', "return [{json:$('Deletion Input').first().json}];"),
    iff('Unmonitor Movie?', "$json.mediaType==='movie'"),
    http('Unmonitor Expiring Movie', 'movie', 'movie/editor', 'PUT', '={{ {movieIds:[Number($json.mediaId)],monitored:false} }}'),
    http('Unmonitor Expiring Episodes', 'tv', 'episode/monitor', 'PUT', '={{ {episodeIds:$json.episodeIds.map(Number),monitored:false} }}'),
    http('Verify Movie Unmonitored', 'movie', "='movie/'+$('Deletion Input').first().json.mediaId"),
    http('Verify Episodes Unmonitored', 'tv', 'episode', query={'seriesId': "={{ $('Deletion Input').first().json.mediaId }}", 'includeEpisodeFile': 'true'}),
    code('Verify Unmonitor And Coverage', "const d=$('Deletion Input').first().json;const rows=$input.all().map(x=>x.json);if(d.mediaType==='movie'){if(rows.length!==1||rows[0].monitored!==false||rows[0].movieFile?.id!==d.fileId||rows[0].movieFile?.path!==d.path)throw new Error('Movie verification failed');}else{const covered=rows.filter(e=>e.episodeFileId===d.fileId);if(covered.length!==d.episodeIds.length||covered.some(e=>e.monitored!==false||!d.episodeIds.includes(String(e.id))||e.episodeFile?.path!==d.path))throw new Error('Episode verification failed');}return [{json:d}];"),
    iff('Remove Movie File?', "$json.mediaType==='movie'"),
    http('Remove Expired Movie File', 'movie', "='moviefile/'+$json.fileId", 'DELETE', full=True),
    http('Remove Expired Episode File', 'tv', "='episodefile/'+$json.fileId", 'DELETE', full=True),
    code('Check Delete Response', "if(![200,202,204,404].includes($json.statusCode))throw new Error('File removal not confirmed');return [{json:$('Deletion Input').first().json}];"),
    iff('Verify Movie Gone?', "$json.mediaType==='movie'"),
    http('Verify Movie File Gone', 'movie', "='moviefile/'+$json.fileId", full=True),
    http('Verify Episode File Gone', 'tv', "='episodefile/'+$json.fileId", full=True),
    code('Build Deleted Record', "if($json.statusCode!==404)throw new Error('File still present after removal');const d=$('Deletion Input').first().json;return [{json:{owner:d.owner,key:d.key,kind:'file',payloadJson:JSON.stringify({...d,state:'deleted',deletedAt:new Date().toISOString()})}}];"),
    call('Persist Deleted Record', store['id']), code('Deletion Result', "return [{json:{processed:true}}];"),
    code('Playback Deferred', "return [{json:{deferred:true,reason:'active playback'}}];")])
chain(delete, 'Deletion Input', 'Verify Deletion Lock', 'Check Deletion Owner', 'Recheck Active Playback', 'Playback Clear', 'Playback Safe?', 'Delete Movie File?', 'Recheck Movie File', 'Validate File Identity', 'Record Deletion Intent', 'Unmonitor Plan', 'Unmonitor Movie?', 'Unmonitor Expiring Movie', 'Verify Movie Unmonitored', 'Verify Unmonitor And Coverage', 'Remove Movie File?', 'Remove Expired Movie File', 'Check Delete Response', 'Verify Movie Gone?', 'Verify Movie File Gone', 'Build Deleted Record', 'Persist Deleted Record', 'Deletion Result')
edge(delete, 'Playback Safe?', 'Playback Deferred', 1)
edge(delete, 'Delete Movie File?', 'Recheck Episode File', 1); edge(delete, 'Recheck Episode File', 'Validate File Identity')
edge(delete, 'Unmonitor Movie?', 'Unmonitor Expiring Episodes', 1); chain(delete, 'Unmonitor Expiring Episodes', 'Verify Episodes Unmonitored', 'Verify Unmonitor And Coverage')
edge(delete, 'Remove Movie File?', 'Remove Expired Episode File', 1); edge(delete, 'Remove Expired Episode File', 'Check Delete Response')
edge(delete, 'Verify Movie Gone?', 'Verify Episode File Gone', 1); edge(delete, 'Verify Episode File Gone', 'Build Deleted Record'); save(delete)

schedule = wf('snakeRetentionScheduleV1', 'Snake Media - Retention and Future Episodes', [
    node('Every Fifteen Minutes', 'scheduleTrigger', {'rule': {'interval': [{'field': 'minutes', 'minutesInterval': 15}]}}),
    code('Scan Job', "return [{json:{job:'scan'}}];"), call('Coordinate Retention Scan', coord['id'])])
chain(schedule, *[n['name'] for n in schedule['nodes']]); save(schedule)

admin_web = copy.deepcopy(web)
admin_web.update(name='Retention Admin', id=node('Retention Admin','webhook')['id'], webhookId='snake-retention-admin-v1')
admin_web['parameters']['path']='snake-retention-admin'
admin = wf('snakeRetentionAdminV1','Snake Media - Retention Administration',[
    admin_web,code('Validate Admin Action',"const action=$json.body?.action;if(!['scan','enable','preview','status'].includes(action))throw new Error('Invalid retention action');return [{json:{action}}];"),
    iff('Run Admin Scan?',"$json.action==='scan'"),code('Admin Scan Job',"return [{json:{job:'scan'}}];"),call('Run Admin Coordinator',coord['id']),
    data('Admin Lock Status',CONTROL,'get',[eq('key','global')]),
    code('Validate Mode Change',"const rows=$input.all().filter(x=>x.json.key);if(rows.length!==1)throw new Error('Invalid control state');const action=$('Validate Admin Action').first().json.action;if(action!=='status'&&rows[0].json.owner!=='')throw new Error('Cannot change mode while retention is running');return [{json:{action}}];"),
    iff('Change Retention Mode?',"$json.action!=='status'"),
    data('Set Retention Mode',CONTROL,'update',[eq('key','mode')],{'owner':"={{ $json.action==='enable'?'enabled':'preview' }}"}),
    data('Read Admin Mode',CONTROL,'get',[eq('key','mode')]),
    code('Admin Mode Result',"return [{json:{mode:$json.owner}}];"),
    node('Admin Response','respondToWebhook',{'respondWith':'json','responseBody':'={{ $json }}'})])
chain(admin,'Retention Admin','Validate Admin Action','Run Admin Scan?','Admin Scan Job','Run Admin Coordinator','Admin Response')
edge(admin,'Run Admin Scan?','Admin Lock Status',1)
chain(admin,'Admin Lock Status','Validate Mode Change','Change Retention Mode?','Set Retention Mode','Read Admin Mode','Admin Mode Result','Admin Response')
edge(admin,'Change Retention Mode?','Read Admin Mode',1);save(admin)
print('Generated retention workflows in', OUT)
