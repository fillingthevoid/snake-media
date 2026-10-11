"""Build an internal, one-time native retention enable job. Deployment is separate."""
import uuid

def build(when,table_id):
 if when.tzinfo is None or not table_id or not table_id.isalnum():raise ValueError('UTC time and bound native table required')
 from datetime import timezone
 when=when.astimezone(timezone.utc)
 def node(name,kind,parameters,version):return {'id':str(uuid.uuid5(uuid.NAMESPACE_URL,'snake-enable-retention/'+name)),'name':name,'type':'n8n-nodes-base.'+kind,'typeVersion':version,'position':[0,0],'parameters':parameters}
 def cond(k,v):return {'keyName':k,'condition':'eq','keyValue':v}
 def data(name,op,filters,values=None):
  p={'resource':'row','operation':op,'dataTableId':{'__rl':True,'mode':'id','value':table_id},'matchType':'allConditions','filters':{'conditions':filters},'options':{}}
  if op=='get':p['returnAll']=True
  else:p['columns']={'mappingMode':'defineBelow','value':values,'schema':[{'id':k,'displayName':k,'type':'string','display':True,'required':False,'defaultMatch':False,'canBeUsedToMatch':True} for k in values]}
  n=node(name,'dataTable',p,1.1);n['alwaysOutputData']=True;return n
 def gate(name,expr):return node(name,'if',{'conditions':{'options':{'typeValidation':'strict','version':3},'conditions':[{'id':name,'leftValue':'={{ '+expr+' }}','operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}},2.3)
 ns=[node('One-Time Enable','scheduleTrigger',{'rule':{'interval':[{'field':'cronExpression','expression':f'{when.second} {when.minute} {when.hour} {when.day} {when.month} *'}]}},1.3),
 data('Read Enable Lock','get',[cond('key','global')]),gate('Unique Free Lock?',"$('Read Enable Lock').all().length===1&&$json.key==='global'&&$json.owner===''") ,
 data('Acquire Enable Lock','update',[cond('key','global'),cond('owner','')],{'owner':'={{ String($execution.id) }}'}),
 gate('Enable Lock Owned?',"$('Acquire Enable Lock').all().length===1&&$json.key==='global'&&$json.owner===String($execution.id)"),
 data('Read Enable Mode','get',[cond('key','mode')]),gate('Preview Mode?',"$('Read Enable Mode').all().length===1&&$json.key==='mode'&&$json.owner==='preview'"),
 data('Enable Deletion','update',[cond('key','mode'),cond('owner','preview')],{'owner':'enabled'}),
 data('Release Enable Lock','update',[cond('key','global'),cond('owner','={{ String($execution.id) }}')],{'owner':''})]
 w={'id':'snakeEnableRetentionOnceV1','name':'Snake Media - Enable Retention Once','nodes':ns,'connections':{},'settings':{'executionOrder':'v1','executionTimeout':60,'timezone':'UTC'}}
 def edge(a,b,port=0):
  m=w['connections'].setdefault(a,{}).setdefault('main',[])
  while len(m)<=port:m.append([])
  m[port]=[{'node':b,'type':'main','index':0}]
 for a,b in zip(ns,ns[1:]):edge(a['name'],b['name'])
 edge('Preview Mode?','Release Enable Lock',1)
 for name in ['Read Enable Mode','Enable Deletion']:
  next(n for n in ns if n['name']==name)['onError']='continueErrorOutput';edge(name,'Release Enable Lock',1)
 # Verify enabled state after releasing the lock, then run the existing cleanup engine.
 ns.extend([data('Read Enabled Mode','get',[cond('key','mode')]),gate('Deletion Enabled?',"$('Read Enabled Mode').all().length===1&&$json.key==='mode'&&$json.owner==='enabled'"),node('Enabled Scan Input','set',{'mode':'raw','jsonOutput':'{"job":"scan"}','options':{}},3.4),node('Run First Enabled Scan','executeWorkflow',{'workflowId':{'__rl':True,'mode':'id','value':'snakeRetentionCoordinatorV1'},'workflowInputs':{'mappingMode':'passThrough'},'mode':'once','options':{'waitForSubWorkflow':True}},1.3)])
 for a,b in [('Release Enable Lock','Read Enabled Mode'),('Read Enabled Mode','Deletion Enabled?'),('Deletion Enabled?','Enabled Scan Input'),('Enabled Scan Input','Run First Enabled Scan')]:edge(a,b)
 w['settings']['executionTimeout']=600
 return w
