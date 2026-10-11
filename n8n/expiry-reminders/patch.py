"""Apply shared expiry reminders to a fresh native n8n export; no deployment."""
import copy,json,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ID='snakeExpiryRemindersV1'
def node(name,kind,parameters,version=2):
 return dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL,'snake-expiry-reminders/'+name)),name=name,type='n8n-nodes-base.'+kind,typeVersion=version,position=[0,0],parameters=parameters)
def edge(w,a,b,port=0):
 m=w['connections'].setdefault(a,{}).setdefault('main',[])
 while len(m)<=port:m.append([])
 m[port]=[dict(node=b,type='main',index=0)]
def read(template,name):
 n=copy.deepcopy(template);n.update(name=name,id=node(name,'code',{})['id'],alwaysOutputData=True);return n
def code(name,body):return node(name,'code',dict(jsCode=body))
def gate(name,expression):return node(name,'if',{'conditions':{'options':{'typeValidation':'strict','version':3},'conditions':[{'id':name,'leftValue':'={{ '+expression+' }}','operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}},2.3)
def apply(rows):
 rows=copy.deepcopy(rows);ws={w['id']:w for w in rows}
 get=lambda w,name:next(n for n in w['nodes'] if n['name']==name)
 policy=(ROOT/'n8n/expiry-reminders/policy.js').read_text(encoding='utf-8-sig')
 scan=ws['snakeRetentionScanV1'];queue=ws['snakeNotificationQueueV1'];sender=ws['snakeTelegramNoticeSendV1']
 mode=get(scan,'Read Retention Mode');records=get(scan,'Read All Retention Records');requests=get(scan,'Read All Requests')
 notices=read(get(queue,'Pending Discord Notices'),'Reminder Notices');notices['parameters']['filters']['conditions']=[]
 store=copy.deepcopy(get(ws['snakeQueueCandidateV1'],'Store Completion Notice'))
 store.update(id=node('Store Expiry Reminder','code',{})['id'],name='Store Expiry Reminder');store['parameters']['operation']='upsert'
 store['parameters']['filters']['conditions']=[{'keyName':'notificationKey','condition':'eq','keyValue':'={{ $json.notificationKey }}'}]
 w=dict(id=ID,name='Snake Media - 24 Hour Expiry Reminders',nodes=[node('Reminder Input','executeWorkflowTrigger',{'inputSource':'passthrough'},1.1)],connections={},settings={'executionOrder':'v1','executionTimeout':120})
 # Collapse each table result before the next reader to avoid repeated full reads.
 for name,template in [('Reminder Mode',mode),('Reminder Requests',requests),('Reminder Records',records),('Reminder Notices',notices)]:
  w['nodes'] += [code('One '+name,'return [{json:{}}];'),read(template,name)]
 w['nodes'] += [code('Plan Expiry Reminders',policy+"\nconst modes=$('Reminder Mode').all().map(x=>x.json).filter(r=>r.key==='mode');return planReminders({mode:modes.length===1?modes[0].owner:null,requests:$('Reminder Requests').all().map(x=>x.json),records:$('Reminder Records').all().map(x=>x.json),notices:$('Reminder Notices').all().map(x=>x.json)}).map(json=>({json}));"),store]
 for a,b in zip(w['nodes'],w['nodes'][1:]):edge(w,a['name'],b['name'])
 rows=[x for x in rows if x['id']!=ID]+[w]
 if not any(n['name']=='Queue Expiry Reminders' for n in scan['nodes']):
  scan['nodes'] += [node('Queue Expiry Reminders','executeWorkflow',{'workflowId':{'__rl':True,'mode':'id','value':ID},'mode':'once','options':{'waitForSubWorkflow':True}},1.3),code('Restore Scan Summary',"return [{json:$('Scan Summary').first().json}];")]
  get(scan,'Queue Expiry Reminders').update(alwaysOutputData=True,onError='continueRegularOutput')
 edge(scan,'Scan Summary','Queue Expiry Reminders');edge(scan,'Queue Expiry Reminders','Restore Scan Summary')
 # Validate queued warnings at delivery using current native retention records/mode.
 for target,start,end,prefix in [(queue,'Pending Discord Notices','Queue Batch','Discord Reminder'),(sender,'Notice Input','Prepare Completion Text','Telegram Reminder')]:
  nodes=[code(prefix+' Input','return [{json:{}}];'),read(mode,prefix+' Mode'),code(prefix+' One Record Read','return [{json:{}}];'),read(records,prefix+' Records')]
  for n in nodes:
   if not any(x['name']==n['name'] for x in target['nodes']):target['nodes'].append(n)
  edge(target,start,nodes[0]['name'])
  for a,b in zip(nodes,nodes[1:]):edge(target,a['name'],b['name'])
  edge(target,nodes[-1]['name'],end)
  n=get(target,end);body=n['parameters']['jsCode']
  if 'const expiryDeliveryMode=' not in body:
   guard=policy+f"\nconst expiryModes=$('{prefix} Mode').all().map(x=>x.json).filter(r=>r.key==='mode');const expiryDeliveryMode=expiryModes.length===1?expiryModes[0].owner:null;const expiryRecords=$('{prefix} Records').all().map(x=>x.json);\n"
   if target is queue:body=body.replace('$input.all().map(x=>x.json)',"$('Pending Discord Notices').all().map(x=>x.json).filter(r=>reminderValid(r,expiryRecords,expiryDeliveryMode))")
   else:body=body.replace('const r=$input.first().json;',"const r=$('Notice Input').first().json;if(!reminderValid(r,expiryRecords,expiryDeliveryMode))return [];")
   n['parameters']['jsCode']=guard+body
 # Reminder posts bypass original-card edits but retain existing presentation/receipt handling.
 if not any(n['name']=='New Telegram Reminder?' for n in sender['nodes']):sender['nodes'].append(gate('New Telegram Reminder?',"JSON.parse($('Notice Input').first().json.payloadJson).newMessage===true"))
 edge(sender,'Completion Card Metadata','New Telegram Reminder?');edge(sender,'New Telegram Reminder?','Completion Retention Controls?');edge(sender,'New Telegram Reminder?','Update Original Telegram Request',1)
 # Replace embedded shared policies while preserving native tails/dependency inlining.
 for target in rows:
  for n in target['nodes']:
   if n['type']!='n8n-nodes-base.code':continue
   s=n['parameters']['jsCode']
   s=s.replace("!n.notificationKey.includes(':progress:')","!n.notificationKey.includes(':progress:')&&!n.notificationKey.includes(':expiry:')") if "!n.notificationKey.includes(':expiry:')" not in s else s
   if "Array.isArray(actor.requestKeys)" not in s:s=s.replace("(!actor.requestKey||r.requestKey===actor.requestKey)","(Array.isArray(actor.requestKeys)?actor.requestKeys.includes(r.requestKey):(!actor.requestKey||r.requestKey===actor.requestKey))")
   if 'function noticeActor(' in s:
    tail=s[s.index('\nreturn [{json:noticeActor('):]
    s=(ROOT/'n8n/notification-buttons/policy.js').read_text(encoding='utf-8-sig')+tail
   n['parameters']['jsCode']=s
 return rows
if __name__=='__main__':
 import sys
 inp,out=map(Path,sys.argv[1:]);out.write_text(json.dumps(apply(json.loads(inp.read_text(encoding='utf-8-sig'))),indent=2,ensure_ascii=True)+'\n',encoding='utf-8')
