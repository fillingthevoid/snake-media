"""Build integration against a workflow export; headers are restored only on snake."""
import copy, json, sys, uuid
from pathlib import Path
ROOT=Path(__file__).parent
source=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
byname={w['name']:copy.deepcopy(w) for w in source}
out=ROOT/'integration-workflows'; out.mkdir(exist_ok=True)
ID='snakeIntegrateRequestV1'
def node(name,kind,params,x=0,y=0,version=2,**extra):
 return dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL,'snake-integration/'+name)),name=name,type='n8n-nodes-base.'+kind,typeVersion=version,parameters=params,position=[x,y],**extra)
def code(name,script,x=0,y=0,**extra): return node(name,'code',{'jsCode':script},x,y,**extra)
def edge(w,a,b,port=0):
 outs=w.setdefault('connections',{}).setdefault(a,{}).setdefault('main',[])
 while len(outs)<=port: outs.append([])
 outs[port]=[{'node':b,'type':'main','index':0}]
def iff(name,expr,x,y=0):
 return node(name,'if',{'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':3},'conditions':[{'id':'condition','leftValue':expr,'rightValue':'','operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}},x,y,version=2.3)
def lookup(w,name): return next(n for n in w['nodes'] if n['name']==name)
def call(name,wid,x,y=0):
 return node(name,'executeWorkflow',{'workflowId':{'__rl':True,'mode':'id','value':wid},'workflowInputs':{'mappingMode':'passThrough'},'options':{'waitForSubWorkflow':True}},x,y,version=1.3)
def clean(w):
 for key in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived'] : w.pop(key,None)
 w['active']=False; w['pinData']={}
 return w

# Preserve the exact existing lookup/add branches; retain metadata in the existing branch.
children=[]
for name,check in [('Add Movie - Radarr','Check If Movie Exists'),('Add TV Show - Sonarr','Check If Series Exists')]:
 w=byname[name]; old=lookup(w,'Already Added')
 old.update(type='n8n-nodes-base.code',typeVersion=2,parameters={'jsCode':"const r=$('"+check+"').first().json; return [{json:{...r,status:'already_added',movie:r.title}}];"})
 children.append(clean(w))

shared={'id':ID,'name':'Snake Media - Track Media Result','nodes':[],'connections':{},'settings':{'executionOrder':'v1','executionTimeout':40}}
s=shared['nodes']
s += [node('Integration Input','executeWorkflowTrigger',{'inputSource':'passthrough'},version=1.1),code('Unwrap Media Result','return [{json:$input.first().json.result || {}}];',200),code('Normalize Media Metadata',(ROOT/'code/media-result.js').read_text(),400),iff('Resolved Media?',"={{ ['added','already_added'].includes($json.status) }}",600),iff('TV Scope?',"={{ $json.mediaType === 'tv' }}",800)]
http=copy.deepcopy(lookup(byname['Add TV Show - Sonarr'],'Check If Series Exists'))
http.update(id=str(uuid.uuid4()),name='Get Requested Episodes',position=[1000,-100],alwaysOutputData=True,onError='continueRegularOutput',retryOnFail=True,maxTries=3,waitBetweenTries=1000)
http['parameters'].update(url='http://192.168.1.10:8989/api/v3/episode',queryParameters={'parameters':[{'name':'seriesId','value':"={{ $('Normalize Media Metadata').first().json.mediaId }}"}]},options={'timeout':10000})
s += [http,code('Build Tracking Input',(ROOT/'code/tracking-input.js').read_text(),1200,onError='continueRegularOutput'),iff('Tracking Input Valid?',"={{ !$json.error && !!$json.messageId }}",1400),call('Register Original Request','snakeTrackRequestV1',1600),code('Return Media Result',"const r=$('Normalize Media Metadata').first().json; const t=$input.first().json; const {raw,context,...result}=r; return [{json:{...result,trackingRegistered:!!t.requestKey}}];",1800),code('Return Unresolved Result','return $input.all();',800,300)]
lookup(shared,'Register Original Request')['onError']='continueRegularOutput'
for a,b in [('Integration Input','Unwrap Media Result'),('Unwrap Media Result','Normalize Media Metadata'),('Normalize Media Metadata','Resolved Media?'),('Resolved Media?','TV Scope?'),('TV Scope?','Get Requested Episodes'),('Get Requested Episodes','Build Tracking Input'),('Build Tracking Input','Tracking Input Valid?'),('Tracking Input Valid?','Register Original Request'),('Register Original Request','Return Media Result')]: edge(shared,a,b)
edge(shared,'Resolved Media?','Return Unresolved Result',1);edge(shared,'TV Scope?','Build Tracking Input',1);edge(shared,'Tracking Input Valid?','Return Media Result',1)
s += [iff('Episode Metadata Ready?',"={{ !!$json.id || !!$json.error || $runIndex >= 4 }}",1100,-100),node('Wait For Episode Metadata','wait',{'amount':2,'unit':'seconds'},1100,-300,version=1.1)]
edge(shared,'Get Requested Episodes','Episode Metadata Ready?');edge(shared,'Episode Metadata Ready?','Build Tracking Input');edge(shared,'Episode Metadata Ready?','Wait For Episode Metadata',1);edge(shared,'Wait For Episode Metadata','Get Requested Episodes')

# Parents retain authorization, interpretation, original child calls and reply destinations.
parents=[]
for name,platform in [('Media Request - Discord','discord'),('Media Request - Telegram','telegram')]:
 w=byname[name]
 if platform=='discord':
  n=lookup(w,'Validate Discord Request')
  n['parameters']['jsCode']=n['parameters']['jsCode'].replace('channelId: b.channelId, guildId: b.guildId','channelId: b.channelId, guildId: b.guildId, messageId: b.messageId, requestedAt: b.requestedAt')
  ctx="{source:'discord',userId:p.userId,destinationId:p.channelId,messageId:p.messageId,requestedAt:p.requestedAt,text:p.text}"
  prep='Validate Discord Request'
 else:
  prep='Prepare Request'; n=lookup(w,prep)
  for key,value in [('messageId','={{ String($json.message.message_id) }}'),('requestedAt','={{ new Date($json.message.date * 1000).toISOString() }}')]:
   n['parameters']['assignments']['assignments'].append({'id':str(uuid.uuid4()),'name':key,'type':'string','value':value})
  ctx="{source:'telegram',userId:String(p.userId),destinationId:String(p.chatId),messageId:p.messageId,requestedAt:p.requestedAt,text:p.text}"
 for media,child,normal,send in [('movie','Add Movie - Radarr','Normalize Movie Result','Send a text message'),('tv','Add TV Show - Sonarr','Normalize TV Result','Send a text message1')]:
  lookup(w,child).update(alwaysOutputData=True,onError='continueRegularOutput')
  suffix='Movie' if media=='movie' else 'TV'; base=2000 if media=='movie' else 2400
  make='Prepare '+suffix+' Tracking'; track='Track '+suffix+' Request'
  w['nodes'] += [code(make,"const p=$('"+prep+"').first().json; return [{json:{context:"+ctx+",mediaType:'"+media+"',result:$input.first().json}}];",base),call(track,ID,base+200)]
  edge(w,child,make);edge(w,make,track)
  if platform=='discord':
   lookup(w,normal)['parameters']['jsCode']='return $input.all();'
   edge(w,track,normal)
  else:
   text='Format '+suffix+' Reply'; photo='Send '+suffix+' Poster'; has='Has '+suffix+' Poster?'; fallback='Poster '+suffix+' Failed?'
   w['nodes'] += [code(text,"const r=$input.first().json; const icon=r.mediaType==='movie'?'🎬':'📺'; const app=r.mediaType==='movie'?'Radarr':'Sonarr'; let text=r.status==='already_added'?`${icon} ${r.title}\\n\\n✅ Already in ${app}.`:r.status==='added'?`${icon} ${r.title}\\n\\n🔎 Added to ${app}.\\nSearch started.`:'⚠️ Snake Media could not process that request right now.'; if(['added','already_added'].includes(r.status)&&!r.trackingRegistered)text+='\\nCompletion tracking is temporarily unavailable.'; return [{json:{...r,replyText:text}}];",base+400),iff(has,'={{ !!$json.posterUrl }}',base+600)]
   original=lookup(w,send)
   original['parameters']['text']="={{ $('"+text+"').first().json.replyText }}"
   original['parameters']['additionalFields'].update(parse_mode='HTML')
   # Escape plain text for the explicitly chosen HTML parse mode.
   original['parameters']['text']="={{ $('"+text+"').first().json.replyText.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }}"
   p=node(photo,'telegram',{'resource':'message','operation':'sendPhoto','chatId':"={{ $('Prepare Request').first().json.chatId }}",'file':'={{ $json.posterUrl }}','additionalFields':{'caption':"={{ $json.replyText.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }}",'parse_mode':'HTML','appendAttribution':False}},base+800,version=original['typeVersion'],credentials=copy.deepcopy(original['credentials']),onError='continueRegularOutput')
   w['nodes'] += [p,iff(fallback,'={{ !!$json.error }}',base+1000)]
   edge(w,track,text);edge(w,text,has);edge(w,has,photo);edge(w,has,send,1);edge(w,photo,fallback);edge(w,fallback,send)
 parents.append(clean(w))
for w in children+[clean(shared)]+parents:
 (out/(w['name']+'.json')).write_text(json.dumps(w,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('Generated',len(children)+1+len(parents),'integration workflows')

verify={'id':'snakeIntegrationVerifyV1','name':'Snake Media - Verify Request Integration','nodes':[node('Run Integration Test','manualTrigger',{},version=1)],'connections':{},'settings':{'executionOrder':'v1'}}
last='Run Integration Test'
for i,source in enumerate(['discord','telegram']):
 name='Synthetic '+source
 fixture={'context':{'source':source,'userId':'1','destinationId':'1','messageId':'2','requestedAt':'2026-09-29T00:00:00.000Z','text':'synthetic integration test'},'mediaType':'movie','result':{'id':1,'tmdbId':1,'title':'SYNTHETIC TEST - NOT MEDIA','status':'already_added','movieFile':{'id':1},'images':[{'coverType':'poster','remoteUrl':'https://image.tmdb.org/t/p/w500/test.jpg'}]}}
 verify['nodes'].append(code(name,'return [{json:'+json.dumps(fixture)+'}];',200+i*600))
 invoke='Integrate '+source
 verify['nodes'].append(call(invoke,ID,400+i*600))
 check='Assert '+source
 verify['nodes'].append(code(check,"const r=$input.first().json; if(!r.trackingRegistered || r.status!=='already_added' || !r.posterUrl || r.mediaId!=='1') throw new Error('Integration assertion failed'); return [{json:{platform:'"+source+"',passed:true}}];",600+i*600))
 edge(verify,last,name);edge(verify,name,invoke);edge(verify,invoke,check);last=check
(out/(verify['name']+'.json')).write_text(json.dumps(clean(verify),indent=2)+'\n',encoding='utf-8')
