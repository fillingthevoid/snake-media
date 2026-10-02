"""Test recovery with synthetic owners in disjoint native tables only."""
import runpy,copy,json
from pathlib import Path
ROOT=Path(__file__).parent
globals().update(runpy.run_path(str(ROOT/'build.py')))
OUT=ROOT/'test-workflows';OUT.mkdir(exist_ok=True);save.__globals__['OUT']=OUT
TABLE='lockcheck_control'
child=copy.deepcopy(w);child.update(id='snakeLockRecoveryTestChild',name='Snake Media - Recovery TEST Child')
for n in child['nodes']:
 if n['name']=='Recovery Webhook':n.update(type='n8n-nodes-base.executeWorkflowTrigger',typeVersion=1.1,parameters={'inputSource':'passthrough'});n.pop('webhookId',None);n.pop('credentials',None)
 if n['name']=='Recovery Response':n.update(type='n8n-nodes-base.code',typeVersion=2,parameters={'jsCode':'return [{json:$json}];'})
 if 'dataTableId' in n.get('parameters',{}):n['parameters']['dataTableId']={'__rl':True,'mode':'name','value':TABLE}
save(child)
def native(name,op,conditions,values):
 n=write(name,op,conditions,values);n['parameters']['dataTableId']={'__rl':True,'mode':'name','value':TABLE};return n
def read(name):
 n=data(name,TABLE);return n
web=copy.deepcopy(get(S['HXtTzVTrpNZMZVt3'],'Discord Webhook'));web.update(name='Recovery Test Webhook',webhookId='snake-recovery-test');web['parameters']['path']='snake-lock-recovery-check'
runner=wf('snakeLockRecoveryTestRun','Snake Media - Recovery TEST Run',[
 web,node('Create Recovery Test Table','dataTable',{'resource':'table','operation':'create','tableName':TABLE,'columns':{'column':[{'name':'key','type':'string'},{'name':'owner','type':'string'}]},'options':{'createIfNotExists':True}}),
 native('Seed Locked Owner','upsert',[eq('key','global')],{'key':'global','owner':'123'}),
 native('Seed Enabled Mode','upsert',[eq('key','mode')],{'key':'mode','owner':'enabled'}),
 code('Changed Owner Proof',"return [{json:{body:{owner:'122',workflowId:'snakeRetentionCoordinatorV1',status:'error',stoppedAt:new Date(Date.now()-300000).toISOString(),checkedAt:new Date().toISOString(),activeExecutions:0}}}];"),
 call('Try Wrong Owner',child['id']),code('Assert Wrong Owner',"if($json.recovered!==false||$json.reason!=='owner_changed')throw Error('Wrong owner not rejected');return [{json:{}}];"),read('Read Still Locked'),
 code('Valid Recovery Proof',"const rows=$input.all().map(x=>x.json);if(!rows.some(r=>r.key==='global'&&r.owner==='123')||!rows.some(r=>r.key==='mode'&&r.owner==='enabled'))throw Error('Wrong owner mutated state');return [{json:{body:{owner:'123',workflowId:'snakeRetentionCoordinatorV1',status:'error',stoppedAt:new Date(Date.now()-300000).toISOString(),checkedAt:new Date().toISOString(),activeExecutions:0}}}];"),
 call('Recover Test Owner',child['id']),code('Assert Recovered',"if($json.recovered!==true||$json.cleanupPaused!==true)throw Error('Recovery failed');return [{json:{}}];"),read('Read Recovery Results'),
 code('Assert Paused And Audited',"const rows=$input.all().map(x=>x.json);if(!rows.some(r=>r.key==='global'&&r.owner==='')||!rows.some(r=>r.key==='mode'&&r.owner==='preview')||!rows.some(r=>r.key==='recovery'&&JSON.parse(r.owner).owner==='123'))throw Error('Incomplete recovery');return [{json:{body:{...$('Valid Recovery Proof').first().json.body,checkedAt:new Date().toISOString()}}}];"),
 call('Repeat Recovered Proof',child['id']),code('Assert Replay Rejected',"if($json.recovered!==false||$json.reason!=='owner_changed')throw Error('Replay not rejected');return [{json:{passed:true,checks:['changed owner rejected','cleanup paused','audit saved','lock released','repeat proof rejected']}}];")])
for n in runner['nodes']:
 if n['type']=='n8n-nodes-base.executeWorkflow':n.pop('onError',None)
response=copy.deepcopy(get(S['HXtTzVTrpNZMZVt3'],'Respond to Discord'));response.update(name='Recovery Test Response');runner['nodes'].append(response)
chain(runner,*[n['name'] for n in runner['nodes']]);save(runner)
print('Generated isolated native recovery tests')
