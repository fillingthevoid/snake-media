"""Native busy/claim test on an isolated table; no calls to media services."""
import runpy,copy,json
from pathlib import Path
ROOT=Path(__file__).parent
globals().update(runpy.run_path(str(ROOT/'build.py')))
OUT=ROOT/'test-workflows';OUT.mkdir(exist_ok=True)
save.__globals__['OUT']=OUT
TABLE='retrycheck_choices'
child=copy.deepcopy(w);child.update(id='snakeBusyRetryTestChild',name='Snake Media - Busy Retry TEST Child')
for n in child['nodes']:
 if 'dataTableId' in n.get('parameters',{}):n['parameters']['dataTableId']={'__rl':True,'mode':'name','value':TABLE}
 if n['type']=='n8n-nodes-base.executeWorkflow':
  assert n['name'] in ['Commit Confirmed Media','Apply Retention Choice']
  n.update(type='n8n-nodes-base.code',typeVersion=2,parameters={'jsCode':"const busy=$('Action Input').first().json.simulateBusy===true;return [{json:{version:1,status:'notice',busy,text:busy?'Synthetic busy':'Synthetic success'}}];"})
save(child)
web=copy.deepcopy(get(S['HXtTzVTrpNZMZVt3'],'Discord Webhook'));web.update(name='Retry Test Webhook',webhookId='snake-busy-retry-test');web['parameters']['path']='snake-busy-retry-check'
schema={**dict.fromkeys(['source','userId','destinationId','requestKey','contextJson','mediaType','mediaJson','state','claimId','choice'],'string'),'expiresAt':'date'}
seed=copy.deepcopy(get(child,'Restore Busy Choice'));seed.update(name='Seed Retry Fixture',id='seed-retry');p=seed['parameters'];p['operation']='upsert';p['filters']['conditions']=[{'keyName':'requestKey','condition':'eq','keyValue':'={{ $json.requestKey }}'}];p['columns']={'mappingMode':'defineBelow','value':{k:'={{ $json.'+k+' }}' for k in schema},'schema':[{'id':k,'displayName':k,'type':v,'display':True,'required':False,'defaultMatch':False,'canBeUsedToMatch':True} for k,v in schema.items()]}
reader=data('Read Restored Fixture',TABLE);reader['parameters']['filters']['conditions']=[{'keyName':'id','condition':'eq','keyValue':"={{ $('Seed Retry Fixture').first().json.id }}"}]
runner=wf('snakeBusyRetryTestRun','Snake Media - Busy Retry TEST Run',[
 web,node('Create Retry Table','dataTable',{'resource':'table','operation':'create','tableName':TABLE,'columns':{'column':[{'name':k,'type':v} for k,v in schema.items()]},'options':{'createIfNotExists':True}}),
 code('Retry Fixture',"const b=$('Retry Test Webhook').first().json.body;if(!['preview','scope','seasons','retention'].includes(b.kind))throw Error('Unknown fixture');return [{json:{source:'discord',userId:'2',destinationId:'3',requestKey:'retry:'+b.kind,contextJson:JSON.stringify(b.kind==='retention'?{retentionChange:{operation:'extend',days:7,title:'SYNTHETIC'}}:{}),mediaType:b.kind==='preview'?'movie':'tv',mediaJson:'{}',state:b.kind==='retention'?'preview':b.kind,claimId:'original',choice:'choose',expiresAt:new Date(Date.now()+600000).toISOString()}}];"),seed,
 code('Busy Test Actor',"const r=$json;return [{json:{source:r.source,userId:r.userId,destinationId:r.destinationId,pendingId:String(r.id),action:r.state==='scope'?'latest':r.state==='seasons'?'season_1':'confirm',simulateBusy:true}}];"),call('Call Busy Confirmation',child['id']),
 code('Assert Busy Response',"if($json.busy!==true||$json.actionAccepted!==false)throw Error('Busy must be retryable');return [{json:{}}];"),reader,
 code('Retry Test Actor',"const initial=$('Seed Retry Fixture').first().json;if($json.state!==initial.state||$json.claimId!==initial.claimId||$json.choice!==initial.choice)throw Error('Original selection not restored');return [{json:{...$('Busy Test Actor').first().json,simulateBusy:false}}];"),call('Call Retried Confirmation',child['id']),
 code('Assert Retried Result',"if($json.actionAccepted!==true||$json.busy===true)throw Error('Retry failed');return [{json:{passed:true,kind:$('Retry Test Webhook').first().json.body.kind}}];")])
for n in runner['nodes']:
 if n['type']=='n8n-nodes-base.executeWorkflow':n.pop('onError',None)
response=copy.deepcopy(get(S['HXtTzVTrpNZMZVt3'],'Respond to Discord'));response.update(name='Retry Test Response');runner['nodes'].append(response)
chain(runner,*[n['name'] for n in runner['nodes']]);save(runner)
print('Generated isolated native retry test')
