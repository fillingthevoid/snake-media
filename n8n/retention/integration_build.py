"""Isolated native n8n tests: separate tables and loopback-only fake services."""
import copy
import datetime
import json
from pathlib import Path
import build as b

T = b.R / 'test-workflows'
T.mkdir(exist_ok=True)
now = datetime.datetime.now(datetime.timezone.utc)
def stamp(days): return (now + datetime.timedelta(days=days)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
fixture = {'requestedAt': stamp(-41), 'importedAt': stamp(-40), 'tvImportedAt': stamp(-10),
           'watchedAt': stamp(-8), 'futureAt': stamp(7)}
(b.R / 'test-fixture.json').write_text(json.dumps(fixture), encoding='utf-8')
ids = ['snakeRetentionStoreV1', 'snakeRetentionCoordinatorV1', 'snakeRetentionPlayedV1',
       'snakeRetentionScanV1', 'snakeRetentionMediaV1', 'snakeRetentionDeleteV1', 'snakeRetentionSetupV1']


def test_table(name): return 'isolated_retention_' + name.removeprefix('snake_media_') + '_test'


def adapt(w):
    w = copy.deepcopy(w)
    w['id'] += 'Test'; w['name'] += ' TEST'
    for n in w['nodes']:
        p = n['parameters']
        if n['type'].endswith('.dataTable'):
            if 'tableName' in p: p['tableName'] = test_table(p['tableName'])
            if 'dataTableId' in p: p['dataTableId']['value'] = test_table(p['dataTableId']['value'])
        if n['type'].endswith('.executeWorkflow'):
            old = p['workflowId']['value']
            p['workflowId']['value'] = old+'Test' if old in ids else 'snakeRetentionProbeTest'
        if n['type'].endswith('.httpRequest'):
            for kind, prefix in b.BASE.items():
                p['url'] = p['url'].replace(prefix, 'http://127.0.0.1:19187/'+kind+'/')
            p['headerParameters'] = {'parameters': []}
            assert '192.168.' not in p['url']
        if n['type'].endswith('.webhook'):
            p['path'] += '-test'; n['webhookId'] += '-test'
    return w


workflows = {}
for path in b.OUT.glob('*.json'):
    w = json.loads(path.read_text(encoding='utf-8'))
    if w['id'] in ids: workflows[w['id']] = adapt(w)

setup = workflows['snakeRetentionSetupV1']
schema = json.loads((b.R.parent/'tracking/schema.json').read_text())['snake_media_requests']
table = test_table('snake_media_requests')
b.SCHEMAS[table] = schema
setup['nodes'].append(b.node('Create Test Requests', 'dataTable', {'resource': 'table', 'operation': 'create', 'tableName': table,
    'columns': {'column': [{'name': k, 'type': v} for k,v in schema.items()]}, 'options': {'createIfNotExists': True}}))
requests = []
for mid, typ, days, episodes in [('9001','movie',7,[]),('9002','tv',30,['10','11']),('9003','movie',None,[])]:
    requests.append({'requestKey': 'discord:2:'+mid, 'source':'discord','userId':'2','destinationId':'2','messageId':mid,
        'text':'ISOLATED RETENTION TEST','mediaType':typ,'mediaId':mid,'externalId':mid,'title':'SYNTHETIC '+mid,
        'episodeIdsJson':json.dumps(episodes),'preexistingFileIdsJson':'[]','state':'registered',
        'requestedAt':fixture['requestedAt'],'retentionDays':days,'baselineCaptured':True,'deletionEligible':days is not None})
setup['nodes'] += [b.code('Test Request Fixtures', 'return '+json.dumps([{'json':r} for r in requests])+';'),
    b.data('Seed Test Requests',table,'upsert',[b.eq('requestKey','={{ $json.requestKey }}')],{k:'={{ $json.'+k+' }}' for k in schema})]
profiles=[]
for r in requests[:2]:
    p={'requestKey':r['requestKey'],'mediaType':r['mediaType'],'mediaId':r['mediaId'],'episodeIds':json.loads(r['episodeIdsJson']),
       'protectedFileIds':[],'historicalSeasons':[1,2],'selectedSeasons':[1]}
    profiles.append({'json':{'key':'request:'+r['requestKey'],'kind':'subscription','payloadJson':json.dumps(p)}})
b.SCHEMAS[test_table(b.RECORDS)]=b.SCHEMAS[b.RECORDS]
setup['nodes'] += [b.code('Test Profile Fixtures','return '+json.dumps(profiles)+';'),
    b.data('Seed Test Profiles',test_table(b.RECORDS),'upsert',[b.eq('key','={{ $json.key }}')],{k:'={{ $json.'+k+' }}' for k in b.SCHEMAS[b.RECORDS]})]
b.edge(setup,'Configuration Exists?','Create Test Requests')
b.SCHEMAS[test_table(b.CONTROL)]=b.SCHEMAS[b.CONTROL]
setup['nodes'].append(b.data('Reset Isolated Test Lock',test_table(b.CONTROL),'update',[b.eq('key','global')],{'owner':''}))
b.chain(setup,'Insert Preview Configuration','Create Test Requests','Test Request Fixtures','Seed Test Requests','Test Profile Fixtures','Seed Test Profiles','Reset Isolated Test Lock','Setup Response')

web=copy.deepcopy(b.web);web.update(name='Test Run',webhookId='snake-retention-run-test');web['parameters']['path']='snake-retention-run-test'
b.SCHEMAS[test_table(b.CONTROL)]=b.SCHEMAS[b.CONTROL]
run=b.wf('snakeRetentionRunTest','Snake Media - Run Retention TEST',[web,
    b.code('Validate Test Mode',"const mode=$json.body?.mode;if(!['preview','enabled','probe'].includes(mode))throw new Error('Invalid test mode');return [{json:{mode}}];"),
    b.iff('Probe Only?',"$json.mode==='probe'"),
    b.code('Probe Job',"return [{json:{job:'commit'}}];"),
    b.data('Set Test Mode',test_table(b.CONTROL),'update',[b.eq('key','mode')],{'owner':'={{ $json.mode }}'}),
    b.code('Test Scan Job',"return [{json:{job:'scan'}}];"),
    b.call('Run Test Coordinator','snakeRetentionCoordinatorV1Test'),
    b.node('Test Run Response','respondToWebhook',{'respondWith':'json','responseBody':'={{ $json }}'})])
b.chain(run,'Test Run','Validate Test Mode','Probe Only?','Probe Job','Run Test Coordinator','Test Run Response')
b.edge(run,'Probe Only?','Set Test Mode',1);b.chain(run,'Set Test Mode','Test Scan Job','Run Test Coordinator')
probe=b.wf('snakeRetentionProbeTest','Snake Media - Lock Probe TEST',[b.trigger('Probe Input'),
    b.node('Hold Test Lock','wait',{'amount':2,'unit':'seconds'}),b.code('Probe Result','return [{json:{probe:true}}];')])
probe['nodes'][1]['typeVersion']=1.1
b.chain(probe,*[n['name'] for n in probe['nodes']])
for w in [*workflows.values(),run,probe]:
    for i,n in enumerate(w['nodes']):n['position']=[i%7*270,i//7*240]
    (T/(w['name']+'.json')).write_text(json.dumps(w,indent=2),encoding='utf-8')
print('Generated isolated test workflows and fixture')
