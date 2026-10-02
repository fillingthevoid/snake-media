"""Generate completion scanning and outbound delivery workflows (no deletion)."""
import json, copy
from integration_build import node,code,call,iff,edge,lookup,clean,byname,ROOT
OUT=ROOT/'notification-workflows';OUT.mkdir(exist_ok=True)
SCHEMA=json.loads((ROOT/'schema.json').read_text())
TABLE='snake_media_notifications'
def wf(id,name,nodes):return {'id':id,'name':name,'nodes':nodes,'connections':{},'settings':{'executionOrder':'v1','executionTimeout':240}}
def data(name,table,operation,conditions=None,values=None,x=0):
 p={'resource':'row','operation':operation,'dataTableId':{'__rl':True,'mode':'name','value':table},'matchType':'allConditions','filters':{'conditions':conditions or []},'options':{}}
 if operation=='get':p['returnAll']=True
 if values is not None:p['columns']={'mappingMode':'defineBelow','value':values,'schema':[{'id':k,'displayName':k,'type':SCHEMA[table][k],'display':True,'required':False,'defaultMatch':False,'canBeUsedToMatch':True} for k in values]}
 return node(name,'dataTable',p,x,version=1.1)
def eq(k,v):return {'keyName':k,'condition':'eq','keyValue':v}
def http(name,original,url,query,x):
 n=copy.deepcopy(original);n.update(name=name,id=node(name,'httpRequest',{})['id'],position=[x,0],alwaysOutputData=True,onError='continueRegularOutput')
 n['parameters']={'method':'GET','url':url,'sendHeaders':True,'headerParameters':original['parameters']['headerParameters'],'sendQuery':True,'queryParameters':{'parameters':[{'name':k,'value':v} for k,v in query.items()]},'options':{'timeout':15000}}
 return n
rad=lookup(byname['Add Movie - Radarr'],'Check If Movie Exists');son=lookup(byname['Add TV Show - Sonarr'],'Check If Series Exists');jelly=lookup(byname['Media Imported - Jellyfin Refresh'],'Refresh Jellyfin Library')
inspect=wf('snakeInspectRequestV1','Snake Media - Inspect Requested Imports',[
 node('Inspect Request','executeWorkflowTrigger',{'inputSource':'passthrough'},version=1.1),iff('Movie Request?',"={{ $json.mediaType==='movie' }}",200),
 http('Read Requested Movie',rad,"={{ 'http://192.168.1.10:7878/api/v3/movie/'+$json.mediaId }}",{},400),
 http('Read Requested Episodes',son,'http://192.168.1.10:8989/api/v3/episode',{'seriesId':'={{ $json.mediaId }}','includeEpisodeFile':'true'},400),
 code('Imported Candidates',(ROOT/'code/notification-candidates.js').read_text(),600),call('Queue Verified Candidate','snakeQueueCandidateV1',800)])
lookup(inspect,'Queue Verified Candidate')['parameters']['mode']='each'
for a,b in [('Inspect Request','Movie Request?'),('Movie Request?','Read Requested Movie'),('Read Requested Movie','Imported Candidates'),('Read Requested Episodes','Imported Candidates'),('Imported Candidates','Queue Verified Candidate')]:edge(inspect,a,b)
edge(inspect,'Movie Request?','Read Requested Episodes',1)
queue=wf('snakeQueueCandidateV1','Snake Media - Queue Verified Completion',[
 node('Candidate Input','executeWorkflowTrigger',{'inputSource':'passthrough'},version=1.1),
 data('Find Existing Notice',TABLE,'get',[eq('requestKey',"={{ $json.request.requestKey }}")],x=200),
 code('No Existing Notice',(ROOT/'code/notice-dedup.js').read_text(encoding='utf-8'),400),
 code('Confirm Jellyfin File',"return [{json:{Items:$('Candidate Input').first().json.jellyfinItems || []}}];",600),
 code('Build Completion Notice',(ROOT/'code/confirm-jellyfin.js').read_text(),800),
 data('Store Completion Notice',TABLE,'insert',values={k:'={{ $json.'+k+' }}' for k in SCHEMA[TABLE]},x=1000)])
lookup(queue,'Find Existing Notice')['alwaysOutputData']=True
for a,b in zip(queue['nodes'],queue['nodes'][1:]):edge(queue,a['name'],b['name'])
scan=wf('snakeCompletionScanV1','Snake Media - Check Requested Imports',[
 node('Every Five Minutes','scheduleTrigger',{'rule':{'interval':[{'field':'minutes','minutesInterval':5}]}},version=1.3),
 data('Tracked Requests','snake_media_requests','get',x=200),
 code('Real Requests Only',"const library=$input.all().flatMap(x=>x.json.Items || []).filter(x=>x.Path&&x.Id).map(x=>({Path:x.Path,Id:x.Id}));return $('Tracked Requests').all().filter(x=>x.json.baselineCaptured&&x.json.userId!=='1'&&x.json.state==='registered').map(x=>({json:{...x.json,jellyfinLibrary:library}}));",400),
 call('Inspect Each Request','snakeInspectRequestV1',600)])
lookup(scan,'Inspect Each Request')['parameters']['mode']='each';lookup(scan,'Inspect Each Request')['onError']='continueRegularOutput'
library=http('Read Jellyfin Library',jelly,'http://192.168.1.10:8096/Items',{'Recursive':'true','IncludeItemTypes':'Movie,Episode','Fields':'Path','Limit':'500','EnableImages':'false','EnableUserData':'false'},300)
library['parameters']['options']['pagination']={'pagination':{'paginationMode':'updateAParameterInEachRequest','parameters':{'parameters':[{'type':'qs','name':'StartIndex','value':'={{ $pageCount * 500 }}'}]},'paginationCompleteWhen':'other','completeExpression':'={{ $response.body.Items.length < 500 }}','limitPagesFetched':True,'maxRequests':100}}
# Run one library query for the scan, not once per tracked request.
scan['nodes'].insert(2,code('One Library Read','return [{json:{}}];',250))
scan['nodes'].insert(3,library)
for a,b in zip(scan['nodes'],scan['nodes'][1:]):edge(scan,a['name'],b['name'])

# Authenticated bot queue: polling and acknowledgements only. No inbound bot listener.
web=copy.deepcopy(lookup(byname['Media Request - Discord'],'Discord Webhook'))
web.update(name='Discord Queue',id=node('Discord Queue','webhook',{})['id'],webhookId='snake-notifications-v1',position=[0,0])
web['parameters']['path']='snake-media-notifications'
api=wf('snakeNotificationQueueV1','Snake Media - Discord Notification Queue',[
 web,code('Validate Queue Action',"const b=$input.first().json.body; if(b?.action==='poll')return [{json:{action:'poll'}}]; if(b?.action==='ack' && typeof b.notificationKey==='string' && b.notificationKey.startsWith('discord:') && b.notificationKey.length<=300 && typeof b.messageId==='string' && /^[1-9][0-9]{0,19}$/.test(b.messageId))return [{json:b}]; throw new Error('Invalid queue action');",200),
 iff('Poll Queue?',"={{ $json.action==='poll' }}",400),
 data('Pending Discord Notices',TABLE,'get',[eq('source','discord'),eq('state','pending')],x=600),
 code('Queue Batch',(ROOT/'code/discord-queue-batch.js').read_text(encoding='utf-8'),800),
 data('Acknowledge Discord Notice',TABLE,'update',[eq('source','discord'),eq('notificationKey','={{ $json.notificationKey }}')],values={'state':'delivered','deliveredAt':'={{ $now.toISO() }}','deliveredMessageId':'={{ $json.messageId }}'},x=600),
 code('Acknowledgement Result',"return [{json:{version:1,acknowledged:true}}];",800),
 node('Queue Response','respondToWebhook',{'respondWith':'json','responseBody':'={{ $json }}','options':{'responseCode':200}},1000,version=1.4)])
lookup(api,'Pending Discord Notices')['alwaysOutputData']=True;lookup(api,'Acknowledge Discord Notice')['alwaysOutputData']=True
for a,b in [('Discord Queue','Validate Queue Action'),('Validate Queue Action','Poll Queue?'),('Poll Queue?','Pending Discord Notices'),('Pending Discord Notices','Queue Batch'),('Queue Batch','Queue Response'),('Acknowledge Discord Notice','Acknowledgement Result'),('Acknowledgement Result','Queue Response')]:edge(api,a,b)
edge(api,'Poll Queue?','Acknowledge Discord Notice',1)

# Telegram uses its existing n8n credential. A send must succeed before marking delivered.
sender=wf('snakeTelegramNoticeSendV1','Snake Media - Deliver Telegram Completion',[
 node('Notice Input','executeWorkflowTrigger',{'inputSource':'passthrough'},version=1.1),
 code('Prepare Completion Text',"const r=$input.first().json;const p=JSON.parse(r.payloadJson);if(r.source!=='telegram'||!/^[-]?[1-9][0-9]*$/.test(r.destinationId)||p.userId==='1')return [];return [{json:{...r,text:String(p.text).slice(0,1800),messageId:p.messageId}}];",200)])
send=copy.deepcopy(lookup(byname['Media Request - Telegram'],'Send a text message'));send.update(name='Send Telegram Completion',id=node('Send Telegram Completion','telegram',{})['id'],position=[400,0]);send['parameters']={'resource':'message','operation':'sendMessage','chatId':'={{ $json.destinationId }}','text':"={{ $json.text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }}",'additionalFields':{'parse_mode':'HTML','appendAttribution':False}}
sender['nodes'] += [send,code('Validate Telegram Delivery',(ROOT/'code/telegram-delivery-result.js').read_text(encoding='utf-8-sig'),500),data('Acknowledge Telegram Notice',TABLE,'update',[eq('notificationKey',"={{ $('Notice Input').first().json.notificationKey }}"),eq('source','telegram')],values={'state':'delivered','deliveredAt':'={{ $now.toISO() }}','deliveredMessageId':'={{ $json.deliveredMessageId }}'},x=600)]
for a,b in zip(sender['nodes'],sender['nodes'][1:]):edge(sender,a['name'],b['name'])
telegram=wf('snakeTelegramNoticesV1','Snake Media - Telegram Completion Delivery',[
 node('Every Two Minutes','scheduleTrigger',{'rule':{'interval':[{'field':'minutes','minutesInterval':2}]}},version=1.3),
 data('Pending Telegram Notices',TABLE,'get',[eq('source','telegram'),eq('state','pending')],x=200),
 code('Unique Telegram Notices',(ROOT/'code/telegram-queue-batch.js').read_text(encoding='utf-8'),400),
 call('Deliver Each Telegram Notice','snakeTelegramNoticeSendV1',600)])
telegram['settings']['executionTimeout']=90
lookup(telegram,'Deliver Each Telegram Notice')['parameters']['mode']='each';lookup(telegram,'Deliver Each Telegram Notice')['onError']='continueRegularOutput'
for a,b in zip(telegram['nodes'],telegram['nodes'][1:]):edge(telegram,a['name'],b['name'])
for w in [inspect,queue,scan,api,sender,telegram]:(OUT/(w['name']+'.json')).write_text(json.dumps(clean(w),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Generated 6 inactive completion workflows')

# Synthetic test exercises the real Data Table insertion and duplicate suppression.
verify=wf('snakeNotificationVerifyV1','Snake Media - Verify Completion Queue',[
 node('Run Queue Test','manualTrigger',{},version=1),
 code('Synthetic Completed File',"return [{json:{request:{requestKey:'discord:1:3',source:'discord',destinationId:'1',userId:'1',messageId:'3'},fileKey:'movie:1',label:'SYNTHETIC TEST - NOT MEDIA',jellyfinPath:'/data/movies/synthetic.mkv',jellyfinItems:[{Path:'/data/movies/synthetic.mkv',Id:'synthetic'}]}}];",200),
 call('Queue Synthetic Notice','snakeQueueCandidateV1',400),
 data('Find Synthetic Notice',TABLE,'get',[eq('notificationKey','discord:1:3:movie:1')],x=600),
 code('Assert Notice Stored',"const rows=$input.all();if(rows.length!==1||rows[0].json.source!=='discord'||JSON.parse(rows[0].json.payloadJson).userId!=='1')throw new Error('Queue storage failed');return [{json:{passed:true}}];",800)])
for a,b in zip(verify['nodes'],verify['nodes'][1:]):edge(verify,a['name'],b['name'])
(OUT/(verify['name']+'.json')).write_text(json.dumps(clean(verify),indent=2)+'\n',encoding='utf-8')
