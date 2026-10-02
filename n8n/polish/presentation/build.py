"""Overlay presentation on a fresh private native workflow export. No deployment."""
import copy,json,sys,os
from pathlib import Path
ROOT=Path(__file__).parent
if len(sys.argv)<2:raise SystemExit('Usage: build.py CURRENT_EXPORT.json [JELLYFIN_PUBLIC_BASE] [OUTPUT_DIR] [NATIVE_TABLE_IDS_JSON]')
helpers=ROOT.parent.parent/'status/build.py'
original_file=__file__;__file__=str(helpers)
exec(compile(helpers.read_text(encoding='utf-8-sig').split('status=wf(')[0],str(helpers),'exec'),globals())
__file__=original_file
OUT=Path(sys.argv[3]) if len(sys.argv)>3 else ROOT/'workflows'
OUT.mkdir(exist_ok=True)
P=(ROOT/'policy.js').read_text(encoding='utf-8-sig')
base=(sys.argv[2] if len(sys.argv)>2 else os.environ.get('JELLYFIN_PUBLIC_URL','http://192.168.1.10:8096')).rstrip('/')
from urllib.parse import urlsplit
import ipaddress,re
def validate_base(value):
 u=urlsplit(value)
 safe_http=False
 if u.scheme=='http' and u.hostname and u.port==8096:
  try:safe_http=u.hostname=='192.168.1.10' or ipaddress.ip_address(u.hostname) in ipaddress.ip_network('100.64.0.0/10')
  except ValueError:pass
 if not (u.scheme=='https' and u.port in (None,443) or safe_http) or not u.hostname or not re.fullmatch(r'[A-Za-z0-9.-]+',u.hostname) or not re.fullmatch(r'[A-Za-z0-9_./%~-]*',u.path) or u.username or u.password or u.query or u.fragment or '..' in u.path.split('/') or any(c.isspace() or ord(c)<32 for c in value):raise ValueError('Invalid Jellyfin base URL')
validate_base(base)
local_base=os.environ.get('JELLYFIN_LOCAL_URL','').rstrip('/')
if local_base:validate_base(local_base)
P=P.replace('http://192.168.1.10:8096',base)
P=P.replace("const LOCAL_JELLYFIN_BASE='';",'const LOCAL_JELLYFIN_BASE='+json.dumps(local_base)+';')
# Discover real IDs from existing native nodes, never resolve production by name.
bindings={}
def register_binding(table,reference):
 if table in bindings and bindings[table]['value']!=reference['value']:
  raise ValueError('Conflicting native table ID: '+table)
 bindings[table]=copy.deepcopy(reference)

for w in S.values():
 for n in w['nodes']:
  t=n.get('parameters',{}).get('dataTableId',{})
  if t.get('mode')=='id':
   label=t.get('cachedResultName','')
   if label.startswith('snake_media_'):register_binding(label,t)
for table,wid,name in [('snake_media_requests','snakeStatusV1','Read Status Requests'),('snake_media_requests','snakeCompletionScanV1','Tracked Requests'),('snake_media_notifications','snakeQueueCandidateV1','Store Completion Notice'),('snake_media_retention_records','snakeStatusV1','Read Status Retention')]:
 t=get(S[wid],name)['parameters']['dataTableId']
 if t.get('mode')=='id':register_binding(table,t)
mapping_path=sys.argv[4] if len(sys.argv)>4 else os.environ.get('SNAKE_NATIVE_TABLE_IDS_JSON')
if mapping_path:
 mapping=json.loads(Path(mapping_path).read_text(encoding='utf-8-sig'))
 if not isinstance(mapping,dict):raise ValueError('Native table map must be an object of table names to exact IDs')
 for table,identifier in mapping.items():
  if not isinstance(table,str) or not table.startswith('snake_media_') or not isinstance(identifier,str) or not identifier or len(identifier)>128 or not identifier.isascii() or not identifier.replace('-','').replace('_','').isalnum():raise ValueError('Invalid native table mapping')
  register_binding(table,{'__rl':True,'mode':'id','value':identifier,'cachedResultName':table})
for table in ['snake_media_requests','snake_media_notifications','snake_media_retention_records']:
 if table not in bindings:raise ValueError('Unresolved native table '+table+'; provide NATIVE_TABLE_IDS_JSON from read-only native metadata')
original_data=data
original_save=save

def data(n,t):
 result=original_data(n,t);result['parameters']['dataTableId']=copy.deepcopy(bindings[t]);return result

def save(w):
 for n in w['nodes']:
  t=n.get('parameters',{}).get('dataTableId',{})
  if t.get('mode')=='name':
   table=t.get('value')
   if table not in bindings:raise ValueError('Unresolved native table '+str(table)+'; provide NATIVE_TABLE_IDS_JSON')
   n['parameters']['dataTableId']=copy.deepcopy(bindings[table])
 original_save(w)

def patch(wid):return copy.deepcopy(S[wid])

# Enrich completion only after the original exact Jellyfin verification and dedup.
inspect=patch('snakeInspectRequestV1')
n=get(inspect,'Imported Candidates');old=n['parameters']['jsCode']
needle='jellyfinItems,request:originalRequest'
if needle not in old:raise ValueError('Unknown candidate implementation')
n['parameters']['jsCode']=old.replace(needle,"quality:f.quality?.quality?.name,jellyfinItems,request:originalRequest")
save(inspect)
queue=patch('snakeQueueCandidateV1')
get(queue,'No Existing Notice')['parameters']['jsCode']=P+"\nconst c=$('Candidate Input').first().json;return completionExists(c,$input.all().map(x=>x.json))?[]:[{json:c}];"
metadata=http('Read Completion Media','movie',"='movie/'+$('Candidate Input').first().json.request.mediaId")
series=http('Read Completion Series','tv',"='series/'+$('Candidate Input').first().json.request.mediaId")
queue['nodes'] += [data('Read Completion Retention','snake_media_retention_records'),
 iff('Completion Movie?',"$('Candidate Input').first().json.request.mediaType==='movie'"),metadata,series,
 code('Enrich Completion Notice',P+"\nconst c=$('Candidate Input').first().json;const original=$('Build Completion Notice').first().json;const item=c.jellyfinItems.find(x=>x.Path===c.jellyfinPath&&x.Id);const meta=completion(c,$('Read Completion Retention').all().map(x=>x.json),item,$json);const payload=JSON.parse(original.payloadJson);payload.text+='\\n'+(meta.quality?'Quality: '+meta.quality+'\\n':'')+meta.expiryText;Object.assign(payload,meta);return [{json:{...original,payloadJson:JSON.stringify(payload)}}];")]
chain(queue,'Build Completion Notice','Read Completion Retention','Completion Movie?','Read Completion Media','Enrich Completion Notice','Store Completion Notice')
edge(queue,'Completion Movie?','Read Completion Series',1);edge(queue,'Read Completion Series','Enrich Completion Notice');save(queue)

# Rich status uses the same verified library and file ledger as the existing reads.
statusinspect=patch('snakeStatusInspectV1');n=get(statusinspect,'Describe Status')
old=n['parameters']['jsCode'];needle="text:describe({"
# Add queue detail only for this requested movie or the selected TV episode IDs.
n['parameters']['jsCode']=P+'\n'+old+"\n"
n['parameters']['jsCode']=n['parameters']['jsCode'].replace("return [{json:{text:describe({...i,media:","const media=$('Status Media Snapshot').first().json.media;const scope=new Set(i.requests.flatMap(r=>JSON.parse(r.episodeIdsJson||'[]')).map(String));const qs=scopedQueue(i.requests,$('Status Episode Snapshot').first().json.episodes,pages.flatMap(p=>p.records),i.records);const details=qs.slice(0,5).map(q=>progress(q)).filter(Boolean);let result=describe({...i,media:")
end="now:Date.now()})}}];"
if end not in n['parameters']['jsCode']:raise ValueError('Unknown status description')
n['parameters']['jsCode']=n['parameters']['jsCode'].replace(end,"now:Date.now()});if(details.length)result+='\\n⬇️ '+details.join('\\n');if(result.includes('Waiting for a release')||result.includes('waiting for a release'))result+='\\nNo acceptable release is downloading yet.';const paths=new Set(i.requests[0].mediaType==='movie'?(media?.movieFile?.path?['/data'+media.movieFile.path]:[]):$('Status Episode Snapshot').first().json.episodes.filter(e=>scope.has(String(e.id))).map(e=>'/data'+e.episodeFile?.path));const item=i.library.find(x=>x.Id&&paths.has(x.Path));return [{json:{text:result,progressState:qs.some(q=>String(q.status).toLowerCase()==='downloading')?'downloading':/waiting for a release/i.test(result)?'waiting':null,posterUrl:poster(media||{}),...jellyfinLinks(item,'"+base+"',LOCAL_JELLYFIN_BASE),requests:i.requests}}];")
n['parameters']['jsCode']=n['parameters']['jsCode'].replace("$('Status Episode Snapshot').first().json.episodes", "(i.requests[0].mediaType==='tv'?$('Status Episode Snapshot').first().json.episodes:[])")
save(statusinspect)
status=patch('snakeStatusV1')
status['nodes'] += [data('Read Status Notices','snake_media_notifications')]
edge(status,'Inspect Status Groups','Read Status Notices');edge(status,'Read Status Notices','Format Status Result')
n=get(status,'Format Status Result')
n['parameters']['jsCode']="const groups=$('Inspect Status Groups').all().map(x=>x.json);const text=groups.map(x=>x.text||'Status temporarily unavailable for one title.').join('\\n\\n');const single=groups.length===1?groups[0]:{};const keys=new Set((single.requests||[]).map(x=>x.requestKey));const notices=$input.all().map(x=>x.json).filter(x=>keys.has(x.requestKey)&&x.state==='delivered').sort((a,b)=>b.id-a.id);return [{json:{version:1,status:'notice',text:text.slice(0,1740)+(text.length>1740?'\\nUse /status with a title for details.':''),posterUrl:single.posterUrl,jellyfinUrl:single.jellyfinUrl,localJellyfinUrl:single.localJellyfinUrl,noticeId:notices[0]?String(notices[0].id):undefined}}];"
save(status)

# Native Telegram fixed collections: expressions only in individual leaves.
sender=patch('snakeTelegramNoticeSendV1')
prep=get(sender,'Prepare Completion Text')
prep['parameters']['jsCode'] += "\n" # retain original validation; metadata is decoded in following node.
sender['nodes'] += [code('Completion Card Metadata',"const r=$json;const p=JSON.parse(r.payloadJson);return [{json:{...r,posterUrl:p.posterUrl,jellyfinUrl:p.jellyfinUrl,localJellyfinUrl:p.localJellyfinUrl,caption:p.text.slice(0,1000)}}];"),iff('Completion Has Poster?',"!!$json.posterUrl"),iff('Completion Has Link?',"!!$json.jellyfinUrl")]
original=get(sender,'Send Telegram Completion');original['parameters']['replyMarkup']='inlineKeyboard'

def keyboard(link=False):
 rows=[]
 if link:rows.append({'row':{'buttons':[{'text':'Open in Jellyfin','additionalFields':{'url':"={{ $('Completion Card Metadata').first().json.jellyfinUrl }}"}}]}})
 rows += [{'row':{'buttons':[{'text':'Extend 7 days','additionalFields':{'callback_data':"={{ 'snake:' + $('Completion Card Metadata').first().json.id + ':notice_7' }}"}},{'text':'Extend 30 days','additionalFields':{'callback_data':"={{ 'snake:' + $('Completion Card Metadata').first().json.id + ':notice_30' }}"}}]}},{'row':{'buttons':[{'text':'Keep permanently','additionalFields':{'callback_data':"={{ 'snake:' + $('Completion Card Metadata').first().json.id + ':notice_keep' }}"}}]}}]
 return {'rows':rows}
original['parameters']['inlineKeyboard']=keyboard(False)
linked=copy.deepcopy(original);linked.update(name='Send Telegram Linked Completion',id=node('Send Telegram Linked Completion','code',{})['id']);linked['parameters']['inlineKeyboard']=keyboard(True)
photo=copy.deepcopy(linked);photo.update(name='Send Telegram Completion Poster',id=node('Send Telegram Completion Poster','code',{})['id'],onError='continueRegularOutput');photo['parameters'].update(operation='sendPhoto',file="={{ $('Completion Card Metadata').first().json.posterUrl }}");photo['parameters'].pop('text',None);photo['parameters']['additionalFields']['caption']="={{ $('Completion Card Metadata').first().json.caption }}"
sender['nodes'] += [linked,photo,iff('Completion Photo Failed?',"!!$json.error"),code('Restore Completion Text',"return [{json:$('Completion Card Metadata').first().json}];")]
chain(sender,'Prepare Completion Text','Completion Card Metadata','Completion Has Poster?','Send Telegram Completion Poster','Completion Photo Failed?','Restore Completion Text','Completion Has Link?','Send Telegram Linked Completion','Validate Telegram Delivery')
edge(sender,'Completion Has Poster?','Completion Has Link?',1);edge(sender,'Completion Photo Failed?','Validate Telegram Delivery',1);edge(sender,'Completion Has Link?','Send Telegram Completion',1)
save(sender)

for wid in ['HXtTzVTrpNZMZVt3','0e67KTcphqxEKNsh']:
 w=patch(wid)
 if wid=='HXtTzVTrpNZMZVt3':
  output='Respond to Discord'
  # Wrap every existing producer reaching the response without moving authorization.
  w['nodes'].append(code('Present Media Feedback',P+"\nconst r=$json;const text=feedback(r);return [{json:text?{...r,status:['added','already_added'].includes(r.status)?'notice':r.status,text}:r}];"))
  for c in w['connections'].values():
   for ports in c.values():
    for es in ports:
     for e in es:
      if e['node']==output:e['node']='Present Media Feedback'
  edge(w,'Present Media Feedback',output)
 else:
  n=get(w,'Format Interactive Reply')
  n['parameters']['jsCode']=P+'\n'+n['parameters']['jsCode'].replace('const r=$json;',"const r={...$json,text:feedback($json)||$json.text};if(r.noticeId){r.pendingId=r.noticeId;r.choices=[{label:'Extend 7 days',action:'notice_7'},{label:'Extend 30 days',action:'notice_30'},{label:'Keep permanently',action:'notice_keep'}];}")
 save(w)
print('Generated presentation overlays from current native export')

# Retention choices on status cards reuse the durable notice ownership endpoint.
card=patch('snakeTelegramCardV1')
credential=copy.deepcopy(next(n['credentials'] for n in card['nodes'] if n['type'].endswith('.telegram')))
card['nodes'] += [iff('Status Card Has Link?',"!!$json.jellyfinUrl"),iff('Status Card Has Controls?',"!!$json.noticeId")]
edge(card,'Validate Card','Status Card Has Link?');edge(card,'Status Card Has Link?','Poster Preview?',1);edge(card,'Status Card Has Link?','Status Card Has Controls?')
prefix="$('Card Input').first().json"
for controls in [False,True]:
 suffix=' With Controls' if controls else ''
 k={'rows':[{'row':{'buttons':[{'text':'Open in Jellyfin','additionalFields':{'url':'={{ '+prefix+'.jellyfinUrl }}'}}]}}]}
 if controls:
  k['rows'] += [{'row':{'buttons':[{'text':label,'additionalFields':{'callback_data':"={{ 'snake:' + "+prefix+".noticeId + ':"+action+"' }}"}} for label,action in [('Extend 7 days','notice_7'),('Extend 30 days','notice_30'),('Keep permanently','notice_keep')]]}}]
 name='Send Linked Status'+suffix
 p={'resource':'message','operation':'sendMessage','chatId':'={{ '+prefix+'.chatId }}','text':'={{ '+prefix+'.replyText }}','replyMarkup':'inlineKeyboard','inlineKeyboard':k,'additionalFields':{'parse_mode':'HTML','appendAttribution':False}}
 send=node(name,'code',{});send.update(type='n8n-nodes-base.telegram',typeVersion=1.2,parameters=p,credentials=copy.deepcopy(credential))
 photo=copy.deepcopy(send);photo.update(name=name+' Poster',id=node(name+' Poster','code',{})['id'],onError='continueRegularOutput');photo['parameters']=copy.deepcopy(p);photo['parameters'].update(operation='sendPhoto',file='={{ '+prefix+'.posterUrl }}');photo['parameters'].pop('text',None);photo['parameters']['additionalFields']['caption']='={{ '+prefix+'.replyText.slice(0,1000) }}'
 has=iff('Status Card Has Poster'+suffix+'?',"!!$json.posterUrl && $('Card Input').first().json.replyText.length<=1000")
 failed=iff('Status Photo Failed'+suffix+'?',"!!$json.error")
 card['nodes'] += [send,photo,has,failed]
 edge(card,'Status Card Has Controls?',has['name'],0 if controls else 1)
 chain(card,has['name'],photo['name'],failed['name'],name);edge(card,has['name'],name,1)
save(card)

# Expiry can clear only an owned card; an active busy action keeps its controls.
for original in [S['snakeConfirmMediaV1']]:
 w=copy.deepcopy(original);n=get(w,'Validate Action');old=n['parameters']['jsCode']
 needle="catch{return [{json:{version:1,status:'notice',text:"
 if needle in old:
  ownership="['source','userId','destinationId'].every(k=>row?.[k]===a[k])"
  n['parameters']['jsCode']=old.replace(needle,"catch{return [{json:{version:1,status:'notice',clearControls:"+ownership+"&&Number.isFinite(Date.parse(row.expiresAt))&&Date.parse(row.expiresAt)<=Date.now(),text:")
  save(w)

# Queue durable progress milestones, once per original request, through existing transports.
progresswf=wf('snakeProgressNoticeV1','Snake Media - Inspect Request Progress',[
 trigger('Progress Input'),
 code('Prepare Progress Status',"const r=$json;if(!r.baselineCaptured||r.userId==='1'||r.state!=='registered')return [];return [{json:{requests:[r],records:[],library:r.jellyfinLibrary||[]}}];"),
 call('Read Progress Snapshot','snakeStatusInspectV1'),
 data('Read Progress Notices','snake_media_notifications'),
 code('Build Progress Notice',P+"\nconst row=progressNotice($('Progress Input').first().json,$('Read Progress Snapshot').first().json,$input.all().map(x=>x.json),Date.now());return row?[{json:row}]:[];")])
store=copy.deepcopy(get(S['snakeQueueCandidateV1'],'Store Completion Notice'));store.update(name='Store Progress Notice',id=node('Store Progress Notice','code',{})['id'])
progresswf['nodes'].append(store);chain(progresswf,*[n['name'] for n in progresswf['nodes']]);save(progresswf)
scan=patch('snakeCompletionScanV1');scan['nodes'] += [call('Inspect Each Progress','snakeProgressNoticeV1',True)]
# A second branch reads the same original rows; completion dedup still runs unchanged.
ports=scan['connections']['Real Requests Only']['main'][0]
ports.append({'node':'Inspect Each Progress','type':'main','index':0});save(scan)

# Milestones carry no expiry controls, while completion cards retain all three.
sender=next(json.loads(p.read_text(encoding='utf-8')) for p in OUT.glob('*.json') if json.loads(p.read_text(encoding='utf-8'))['id']=='snakeTelegramNoticeSendV1')
metadata=get(sender,'Completion Card Metadata')
metadata['parameters']['jsCode']=metadata['parameters']['jsCode'].replace('posterUrl:p.posterUrl,','retentionControls:p.retentionControls!==false,posterUrl:p.posterUrl,').replace('caption:p.text.slice(0,1000)',"caption:p.text.slice(0,700).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')")
plain=copy.deepcopy(get(sender,'Send Telegram Completion'));plain.update(name='Send Telegram Progress',id=node('Send Telegram Progress','code',{})['id']);plain['parameters']['replyMarkup']='none';plain['parameters'].pop('inlineKeyboard',None)
sender['nodes'] += [iff('Completion Retention Controls?',"$json.retentionControls!==false"),plain]
edge(sender,'Completion Card Metadata','Completion Retention Controls?');edge(sender,'Completion Retention Controls?','Completion Has Poster?');edge(sender,'Completion Retention Controls?','Send Telegram Progress',1);edge(sender,'Send Telegram Progress','Validate Telegram Delivery');save(sender)

# Native Telegram can safely clear text-card keyboards. Photo caption edits are
# not supported by its native node; preserve those cards without exposing tokens.
telegram=next(json.loads(p.read_text(encoding='utf-8')) for p in OUT.glob('*.json') if json.loads(p.read_text(encoding='utf-8'))['id']=='0e67KTcphqxEKNsh')
triggername=next(n['name'] for n in telegram['nodes'] if n['type'].endswith('.telegramTrigger'))
callback="$('"+triggername+"').first().json.callback_query"
telegram['nodes'] += [code('Preserve Telegram Reply','return [{json:$json}];'),
 iff('Owned Text Card Cleanup?',"$json.busy!==true && ($json.actionAccepted===true || $json.clearControls===true) && !!("+callback+"?.message?.text)"),
 code('Restore Telegram Reply',"return [{json:$('Preserve Telegram Reply').first().json}];")]
clear=node('Clear Telegram Text Controls','code',{})
clear.update(type='n8n-nodes-base.telegram',typeVersion=1.2,credentials=copy.deepcopy(credential),onError='continueRegularOutput',parameters={'resource':'message','operation':'editMessageText','messageType':'message','chatId':'={{ '+callback+'.message.chat.id }}','messageId':'={{ '+callback+'.message.message_id }}','text':'={{ '+callback+'.message.text }}','replyMarkup':'inlineKeyboard','inlineKeyboard':{'rows':[]},'additionalFields':{'appendAttribution':False}})
telegram['nodes'].append(clear)
for c in telegram['connections'].values():
 for ports in c.values():
  for es in ports:
   for e in es:
    if e['node']=='Format Interactive Reply':e['node']='Preserve Telegram Reply'
chain(telegram,'Preserve Telegram Reply','Owned Text Card Cleanup?','Clear Telegram Text Controls','Restore Telegram Reply','Format Interactive Reply');edge(telegram,'Owned Text Card Cleanup?','Restore Telegram Reply',1);save(telegram)
print('Presentation, progress milestones and owned text-card cleanup generated')

# Guard dual-link variants per payload, so older/single-link notices keep working.
def install_local_link_variants(workflow,prefix,names):
 for name in names:
  original=get(workflow,name)
  dual=copy.deepcopy(original)
  dual_name=name+' Local and Tailscale'
  dual.update(name=dual_name,id=node(dual_name,'code',{})['id'])
  dual['parameters']['inlineKeyboard']['rows'][0]={'row':{'buttons':[
   {'text':'Open locally','additionalFields':{'url':'={{ '+prefix+'.localJellyfinUrl }}'}},
   {'text':'Open via Tailscale','additionalFields':{'url':'={{ '+prefix+'.jellyfinUrl }}'}}]}}
  guard=iff('Dual Links '+name+'?','!!('+prefix+'.localJellyfinUrl && '+prefix+'.localJellyfinUrl !== '+prefix+'.jellyfinUrl)')
  outgoing=copy.deepcopy(workflow['connections'].get(name,{}))
  for connection in workflow['connections'].values():
   for ports in connection.values():
    for edges in ports:
     for edgevalue in edges:
      if edgevalue['node']==name:edgevalue['node']=guard['name']
  workflow['nodes'] += [guard,dual]
  if outgoing:workflow['connections'][dual_name]=outgoing
  edge(workflow,guard['name'],dual_name);edge(workflow,guard['name'],name,1)
 save(workflow)

sender_path=OUT/'Snake Media - Deliver Telegram Completion.json'
sender=json.loads(sender_path.read_text(encoding='utf-8'))
install_local_link_variants(sender,"$('Completion Card Metadata').first().json",['Send Telegram Linked Completion','Send Telegram Completion Poster'])
card_path=OUT/'Snake Media - Telegram Interactive Reply.json'
card=json.loads(card_path.read_text(encoding='utf-8'))
install_local_link_variants(card,"$('Card Input').first().json",['Send Linked Status','Send Linked Status Poster','Send Linked Status With Controls','Send Linked Status With Controls Poster'])
