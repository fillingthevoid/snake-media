"""Native amendment integration with separate tables and simulated media only."""
from pathlib import Path
ROOT=Path(__file__).parent
exec(compile((ROOT/'build.py').read_text(encoding='utf-8-sig').split('pending_fields=')[0],str(ROOT/'build.py'),'exec'),globals())
PROD=R/'workflows';OUT=R/'test-workflows';OUT.mkdir(exist_ok=True)
W={w['id']:w for w in [json.loads(p.read_text(encoding='utf-8-sig')) for p in PROD.glob('*.json')]}
tables={'snake_media_requests':'amendcheck_requests','snake_media_pending':'amendcheck_pending','snake_media_retention_control':'amendcheck_control','snake_media_retention_records':'amendcheck_records'}
ids={'snakeRetentionChangeApplyV1':'snakeAmendApplyTest','snakeRetentionChangeSnapshotV1':'snakeAmendSnapshotTest','snakeRetentionStoreV1':'snakeAmendStoreTest','snakeRetentionCoordinatorV1':'snakeAmendCoordinatorTest'}
def adapt(w):
 w=copy.deepcopy(w);w['id']=ids[w['id']];w['name']+=' TEST'
 for n in w['nodes']:
  p=n['parameters']
  if n['type'].endswith('.dataTable'):
   # Production generated references may already be bound IDs; use node's known purpose.
   table='snake_media_pending' if n['name'] in ['Read Claimed Change','Complete Retention Choice'] else 'snake_media_requests' if n['name']=='Read Amend Requests' else 'snake_media_retention_records' if n['name'] in ['Read Amend Records','Upsert Retention Record'] else 'snake_media_retention_control'
   p['dataTableId']={'__rl':True,'mode':'name','value':tables[table]}
  if n['type'].endswith('.executeWorkflow'):
   old=p['workflowId']['value']
   if old in ids:p['workflowId']['value']=ids[old]
   else:n.update(type='n8n-nodes-base.code',typeVersion=2,parameters={'jsCode':"throw Error('Unexpected integration branch');"})
 return w
store=adapt(S['snakeRetentionStoreV1']);apply=adapt(W['snakeRetentionChangeApplyV1']);coord=adapt(W['snakeRetentionCoordinatorV1'])
snapshot=wf('snakeAmendSnapshotTest','Snake Media - Amendment Snapshot TEST',[
 trigger('Scan Input'),data('Test Snapshot Requests',tables['snake_media_requests']),code('One Test Snapshot','return [{json:{}}];'),data('Test Snapshot Records',tables['snake_media_retention_records']),
 code('Fake Media Decisions',RP+'\n'+ENGINE+"\nconst input=$('Scan Input').first().json;const req=$('Test Snapshot Requests').all().map(x=>x.json).filter(r=>r.requestKey);const now=Date.now();const out=planMedia({requests:req,records:$input.all().map(x=>x.json).filter(x=>x.key),media:{id:9001,movieFile:{id:400,path:'/movies/Synthetic/test.mkv',dateAdded:req[0].requestedAt}},episodes:[],watched:[],sessions:[],now});return [{json:{groups:[{decisions:out.decisions}]}}];")])
chain(snapshot,*[n['name'] for n in snapshot['nodes']])
web=copy.deepcopy(get(S['HXtTzVTrpNZMZVt3'],'Discord Webhook'));web.update(name='Amend Test Webhook',webhookId='amend-test-webhook');web['parameters']['path']='snake-retention-controls-check'
run=wf('snakeAmendRunTest','Snake Media - Amendment Check TEST',[web])
schemas={'amendcheck_requests':json.loads((R.parent/'tracking/schema.json').read_text())['snake_media_requests'],'amendcheck_pending':{**dict.fromkeys(['source','userId','destinationId','requestKey','contextJson','mediaType','mediaJson','state','claimId','choice'],'string'),'expiresAt':'date'},'amendcheck_records':{'key':'string','kind':'string','payloadJson':'string'},'amendcheck_control':{'key':'string','owner':'string'}}
for table,schema in schemas.items():run['nodes'].append(node('Create '+table,'dataTable',{'resource':'table','operation':'create','tableName':table,'columns':{'column':[{'name':k,'type':v} for k,v in schema.items()]},'options':{'createIfNotExists':True}}))
run['nodes'] += [native('Test Global Lock',tables['snake_media_retention_control'],'upsert',[eq('key','global')],{'key':'global','owner':''}),
 code('Test Fixture',"const b=$('Amend Test Webhook').first().json.body;if(!['extend','permanent'].includes(b.operation)||!/^case[0-9]+$/.test(b.nonce))throw Error('Invalid test');const stamp='2026-10-01T12:00:00.000Z';return [{json:{requestKey:'discord:2:3',source:'discord',userId:'2',destinationId:'2',messageId:'3',text:'SYNTHETIC',mediaType:'movie',mediaId:'9001',externalId:'9001',title:'SYNTHETIC',episodeIdsJson:'[]',preexistingFileIdsJson:'[]',state:'registered',requestedAt:stamp,retentionDays:7,baselineCaptured:true,deletionEligible:true}}];"),
 native('Seed Test Request',tables['snake_media_requests'],'upsert',[eq('requestKey','discord:2:3')],{k:'={{ $json.'+k+' }}' for k in schemas[tables['snake_media_requests']]},schemas[tables['snake_media_requests']]),
 native('Seed Test Profile',tables['snake_media_retention_records'],'upsert',[eq('key','request:discord:2:3')],{'key':'request:discord:2:3','kind':'subscription','payloadJson':json.dumps({'requestKey':'discord:2:3','mediaType':'movie','mediaId':'9001','episodeIds':[],'protectedFileIds':[]})}),
 code('Test Pending Fixture',"const b=$('Amend Test Webhook').first().json.body;const retentionChange={operation:b.operation,days:7,requestKeys:['discord:2:3'],source:'discord',userId:'2',mediaType:'movie',mediaId:'9001',title:'SYNTHETIC'};return [{json:{source:'discord',userId:'2',destinationId:'2',requestKey:b.nonce,contextJson:JSON.stringify({retentionChange}),mediaType:'movie',mediaJson:'{}',state:'processing',claimId:'native-test',choice:'confirm',expiresAt:new Date(Date.now()+600000).toISOString()}}];"),
 native('Seed Test Pending',tables['snake_media_pending'],'upsert',[eq('requestKey','={{ $json.requestKey }}')],{k:'={{ $json.'+k+' }}' for k in schemas[tables['snake_media_pending']]},schemas[tables['snake_media_pending']]),
 code('Test Amend Job',"return [{json:{...$json,job:'amend'}}];"),strictcall('Execute Native Amendment',coord['id'])]
response=copy.deepcopy(get(S['HXtTzVTrpNZMZVt3'],'Respond to Discord'));response.update(name='Amend Test Response');run['nodes'].append(response)
chain(run,*[n['name'] for n in run['nodes']])
for w in [store,apply,coord,snapshot,run]:save(w)
print('Generated isolated amendment integration workflows')
