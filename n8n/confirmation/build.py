"""Build confirmation workflows from a fresh sanitized server export."""
import copy,json,uuid
from pathlib import Path
R=Path(__file__).parent
W={w['name']:w for w in json.loads((R/'source.json').read_text(encoding='utf-8'))}
OUT=R/'workflows';OUT.mkdir(exist_ok=True)
TABLE='snake_media_pending'
SCHEMA={**dict.fromkeys(['source','userId','destinationId','requestKey','contextJson','mediaType','mediaJson','state','claimId','choice'],'string'),'expiresAt':'date'}
POLICY=(R/'policy.js').read_text(encoding='utf-8-sig')
def n(name,kind,p=None,**extra):return dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL,'snake-confirm/'+name)),name=name,type='n8n-nodes-base.'+kind,typeVersion={'code':2,'if':2.3,'dataTable':1.1,'executeWorkflow':1.3,'httpRequest':4.4,'executeWorkflowTrigger':1.1,'telegram':1.2,'wait':1.1}.get(kind,1),parameters=p or {},position=[0,0],**extra)
def code(name,s):return n(name,'code',{'jsCode':s})
def iff(name,s):return n(name,'if',{'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':3},'conditions':[{'id':'yes','leftValue':'={{ '+s+' }}','rightValue':'','operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}})
def call(name,id):return n(name,'executeWorkflow',{'workflowId':{'__rl':True,'mode':'id','value':id},'workflowInputs':{'mappingMode':'passThrough'},'options':{'waitForSubWorkflow':True}})
def wf(id,name,nodes):return {'id':id,'name':name,'nodes':nodes,'connections':{},'settings':{'executionOrder':'v1','executionTimeout':120},'active':False,'pinData':{}}
def edge(w,a,b,port=0):
 outs=w['connections'].setdefault(a,{}).setdefault('main',[])
 while len(outs)<=port:outs.append([])
 outs[port]=[{'node':b,'type':'main','index':0}]
def chain(w,*names):
 for a,b in zip(names,names[1:]):edge(w,a,b)
def get(w,name):return next(n for n in w['nodes'] if n['name']==name)
def eq(k,v):return {'keyName':k,'condition':'eq','keyValue':v}
def data(name,op,filters=None,values=None):
 p={'resource':'row','operation':op,'dataTableId':{'__rl':True,'mode':'name','value':TABLE},'matchType':'allConditions','filters':{'conditions':filters or []},'options':{}}
 if op=='get':p['returnAll']=True
 if values is not None:p['columns']={'mappingMode':'defineBelow','value':values,'schema':[{'id':k,'displayName':k,'type':SCHEMA[k],'display':True,'required':False,'defaultMatch':False,'canBeUsedToMatch':True} for k in values]}
 return n(name,'dataTable',p,alwaysOutputData=True)
def http(name,media,path,method='GET',query=None,body=None):
 p={'method':method,'url':'http://192.168.1.10:'+('7878' if media=='movie' else '8989')+'/api/v3/'+path,'sendHeaders':True,'headerParameters':{'parameters':[{'name':'X-Api-Key','value':'__SERVER_HEADER__'}]},'options':{'timeout':20000}}
 if query:p.update(sendQuery=True,queryParameters={'parameters':[{'name':k,'value':v} for k,v in query.items()]})
 if body:p.update(sendBody=True,specifyBody='json',jsonBody=body)
 return n(name,'httpRequest',p,alwaysOutputData=True)
def save(w):
 for i,x in enumerate(w['nodes']):x['position']=[(i%8)*250,(i//8)*280]
 for k in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived']:w.pop(k,None)
 w.update(active=False,pinData={})
 (OUT/(w['name']+'.json')).write_text(json.dumps(w,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
render=(R/'render.js').read_text(encoding='utf-8')
preview=wf('snakePreviewMediaV1','Snake Media - Preview Media',[
 n('Preview Input','executeWorkflowTrigger',{'inputSource':'passthrough'}),
 n('Ensure Pending Table','dataTable',{'resource':'table','operation':'create','tableName':TABLE,'columns':{'column':[{'name':k,'type':v} for k,v in SCHEMA.items()]},'options':{'createIfNotExists':True}}),
 code('Validate Preview',"const i=$('Preview Input').first().json,c=i.context;if(!['movie','tv'].includes(i.mediaType)||typeof i.title!=='string'||!i.title.trim()||!c||!['discord','telegram'].includes(c.source)||!/^[-]?[1-9][0-9]*$/.test(c.destinationId)||!/^[0-9]+$/.test(c.userId)||!/^[0-9]+$/.test(c.messageId)||!Number.isFinite(Date.parse(c.requestedAt)))throw new Error('Invalid preview context');return [{json:i}];"),
 iff('Movie Lookup?',"$json.mediaType==='movie'"),
 http('Lookup Movie','movie','movie/lookup',query={'term':"={{ $('Preview Input').first().json.title }}"}),
 http('Lookup Series','tv','series/lookup',query={'term':"={{ $('Preview Input').first().json.title }}"}),
 code('Select Preview',"const i=$('Preview Input').first().json;const m=$input.all().map(x=>x.json).find(x=>Number.isSafeInteger(x[i.mediaType==='movie'?'tmdbId':'tvdbId'])&&(!i.year||x.year===i.year));if(!m)return [{json:{version:1,status:'not_found'}}];const c=i.context;return [{json:{source:c.source,userId:c.userId,destinationId:c.destinationId,requestKey:[c.source,c.destinationId,c.messageId].join(':'),contextJson:JSON.stringify(c),mediaType:i.mediaType,mediaJson:JSON.stringify(m),state:'preview',claimId:'',choice:'',expiresAt:new Date(Date.now()+30*60000).toISOString()}}];"),
 iff('Found Preview?',"!!$json.requestKey"),
 data('Existing Preview','get',[eq('requestKey',"={{ $json.requestKey }}")]),
 code('Resolve Preview',"const rows=$input.all().filter(x=>x.json.id);if(rows.length>1)throw new Error('Duplicate preview');return [{json:{existing:rows.length===1,record:rows[0]?.json||$('Select Preview').first().json}}];"),
 iff('Reuse Preview?',"$json.existing"),code('Existing Card','return [{json:$json.record}];'),
 data('Store Preview','insert',values={k:'={{ $json.record.'+k+' }}' for k in SCHEMA}),
 code('Render Preview',render)])
chain(preview,'Preview Input','Ensure Pending Table','Validate Preview','Movie Lookup?','Lookup Movie','Select Preview','Found Preview?','Existing Preview','Resolve Preview','Reuse Preview?','Existing Card','Render Preview')
edge(preview,'Movie Lookup?','Lookup Series',1);edge(preview,'Lookup Series','Select Preview');edge(preview,'Reuse Preview?','Store Preview',1);edge(preview,'Store Preview','Render Preview');edge(preview,'Found Preview?','Render Preview',1)
save(preview)

act=wf('snakeConfirmMediaV1','Snake Media - Confirm Media',[
 n('Action Input','executeWorkflowTrigger',{'inputSource':'passthrough'}),
 data('Find Pending','get',[eq('id',"={{ Number($json.pendingId) }}")]),
 code('Validate Action',POLICY+"\nconst row=$input.first().json,a=$('Action Input').first().json;try {const state=transition(row,a,Date.now());return [{json:{row,state,choice:a.action,claimId:String($execution.id)}}];}catch{return [{json:{version:1,status:'notice',text:'This choice is expired, already handled, or belongs to another requester. Send a new request if needed.'}}];}"),
 iff('Action Valid?',"!!$json.row"),
 data('Claim Choice','update',[eq('id',"={{ $json.row.id }}"),eq('state',"={{ $json.row.state }}"),eq('claimId',"={{ $json.row.claimId }}")],{'state':'={{ $json.state }}','claimId':'={{ $json.claimId }}','choice':'={{ $json.choice }}'}),
 code('Verify Claim',"const r=$input.first().json;if(r.claimId!==String($execution.id))return [{json:{version:1,status:'notice',text:'This choice was already handled. Please use the latest response.'}}];return [{json:r}];"),
 iff('Run Confirmed Media?',"$json.state==='processing'"),call('Commit Confirmed Media','snakeCommitMediaV1'),
 code('Render Choice',render)])
chain(act,'Action Input','Find Pending','Validate Action','Action Valid?','Claim Choice','Verify Claim','Run Confirmed Media?','Commit Confirmed Media')
edge(act,'Action Valid?','Render Choice',1);edge(act,'Run Confirmed Media?','Render Choice',1);save(act)

# Commit has no public trigger. It requires the claim returned by the action workflow.
commit=wf('snakeCommitMediaV1','Snake Media - Commit Confirmed Media',[
 n('Commit Input','executeWorkflowTrigger',{'inputSource':'passthrough'}),
 code('Confirmed Metadata',"const r=$json;if(r.state!=='processing'||!r.claimId)throw new Error('Unclaimed request');const m=JSON.parse(r.mediaJson);return [{json:{...r,media:m,context:JSON.parse(r.contextJson)}}];"),
 iff('Commit Movie?',"$json.mediaType==='movie'"),
 http('Find Confirmed Movie','movie','movie',query={'tmdbId':"={{ $('Confirmed Metadata').first().json.media.tmdbId }}"}),
 code('Existing Movie',"const m=$('Confirmed Metadata').first().json.media;return [{json:$input.all().map(x=>x.json).find(x=>x.tmdbId===m.tmdbId&&x.id)||{}}];"),
 iff('Movie Exists?',"!!$json.id"),
 code('Build Movie Payload',(R/'add-payload.js').read_text(encoding='utf-8-sig')),
 http('Add Confirmed Movie','movie','movie','POST',body='={{ $json }}'),
 code('Movie Snapshot',"const m=$json;const p=$('Confirmed Metadata').first().json;const c=p.context;if(!m.id||m.tmdbId!==p.media.tmdbId)throw new Error('Movie identity mismatch');return [{json:{...c,mediaType:'movie',mediaId:String(m.id),externalId:String(m.tmdbId),title:m.title,episodeIds:[],preexistingFileIds:m.movieFile?.id?[String(m.movieFile.id)]:[],baselineCaptured:true,retentionDays:null,missing:!m.movieFile?.id}}];"),
 call('Register Movie Before Search','snakeTrackRequestV1'),
 code('Movie Search Plan',"if(!$json.requestKey)throw new Error('Tracking not saved');return [{json:$('Movie Snapshot').first().json}];"),
 iff('Movie Missing?',"$json.missing"),
 http('Search Confirmed Movie','movie','command','POST',body="={{ {name:'MoviesSearch',movieIds:[Number($json.mediaId)]} }}"),
 code('Movie Result',"const r=$('Movie Snapshot').first().json;return [{json:{version:1,status:'notice',text:'🎬 '+r.title+'\\n\\n'+(r.missing?'🔎 Search started.':'✅ Already available in Radarr.')}}];"),
 http('Find Confirmed Series','tv','series',query={'tvdbId':"={{ $('Confirmed Metadata').first().json.media.tvdbId }}"}),
 code('Existing Series',"const m=$('Confirmed Metadata').first().json.media;return [{json:$input.all().map(x=>x.json).find(x=>x.tvdbId===m.tvdbId&&x.id)||{}}];"),
 iff('Series Exists?',"!!$json.id"),
 code('Build Series Payload',(R/'add-payload.js').read_text(encoding='utf-8-sig')),
 http('Add Confirmed Series','tv','series','POST',body='={{ $json }}'),
 code('Series Identity',"const p=$('Confirmed Metadata').first().json;if(!$json.id||$json.tvdbId!==p.media.tvdbId)throw new Error('Series identity mismatch');return [{json:$json}];"),
 http('Read Confirmed Episodes','tv','episode',query={'seriesId':"={{ $('Series Identity').first().json.id }}"}),
 iff('Episodes Ready?',"!!$json.id || $runIndex>=5"),n('Wait Metadata','wait',{'amount':2,'unit':'seconds'}),
 code('Selected Episode Snapshot',POLICY+"\nconst p=$('Confirmed Metadata').first().json;const selected=scope($input.all().map(x=>x.json),p.choice,Date.now());if(!selected.length)return [{json:{version:1,status:'notice',text:'No aired episodes were found for that selection. Nothing was searched. Please try again later.'}}];const s=$('Series Identity').first().json;return [{json:{...p.context,mediaType:'tv',mediaId:String(s.id),externalId:String(s.tvdbId),title:s.title,episodeIds:selected.map(e=>String(e.id)),preexistingFileIds:selected.filter(e=>e.episodeFileId>0).map(e=>String(e.episodeFileId)),baselineCaptured:true,retentionDays:null,missingIds:selected.filter(e=>!e.hasFile&&!e.episodeFileId).map(e=>e.id),seasons:[...new Set(selected.map(e=>e.seasonNumber))]}}];"),
 iff('Has Aired Selection?',"!!$json.episodeIds"),call('Register TV Before Search','snakeTrackRequestV1'),
 code('TV Search Plan',"if(!$json.requestKey)throw new Error('Tracking not saved');return [{json:$('Selected Episode Snapshot').first().json}];"),
 iff('Episodes Missing?',"$json.missingIds.length>0"),
 http('Search Confirmed Episodes','tv','command','POST',body="={{ {name:'EpisodeSearch',episodeIds:$json.missingIds} }}"),
 code('TV Result',"const r=$('Selected Episode Snapshot').first().json;return [{json:{version:1,status:'notice',text:'📺 '+r.title+' — season '+r.seasons.join(', ')+'\\n\\n'+(r.missingIds.length?'🔎 Search started for '+r.missingIds.length+' aired episodes.':'✅ Selected episodes are already in Sonarr.')}}];"),
 code('Save Outcome',"return [{json:{reply:$json}}];"),
 data('Complete Pending','update',[eq('id',"={{ $('Commit Input').first().json.id }}"),eq('claimId',"={{ $('Commit Input').first().json.claimId }}")],{'state':'done'}),
 code('Return Outcome',"return [{json:$('Save Outcome').first().json.reply}];")])
chain(commit,'Commit Input','Confirmed Metadata','Commit Movie?','Find Confirmed Movie','Existing Movie','Movie Exists?','Movie Snapshot','Register Movie Before Search','Movie Search Plan','Movie Missing?','Search Confirmed Movie','Movie Result','Save Outcome','Complete Pending','Return Outcome')
edge(commit,'Movie Exists?','Build Movie Payload',1);edge(commit,'Build Movie Payload','Add Confirmed Movie');edge(commit,'Add Confirmed Movie','Movie Snapshot');edge(commit,'Movie Missing?','Movie Result',1)
edge(commit,'Commit Movie?','Find Confirmed Series',1)
chain(commit,'Find Confirmed Series','Existing Series','Series Exists?','Series Identity','Read Confirmed Episodes','Episodes Ready?','Selected Episode Snapshot','Has Aired Selection?','Register TV Before Search','TV Search Plan','Episodes Missing?','Search Confirmed Episodes','TV Result','Save Outcome')
edge(commit,'Series Exists?','Build Series Payload',1);edge(commit,'Build Series Payload','Add Confirmed Series');edge(commit,'Add Confirmed Series','Series Identity');edge(commit,'Episodes Ready?','Wait Metadata',1);edge(commit,'Wait Metadata','Read Confirmed Episodes');edge(commit,'Has Aired Selection?','Save Outcome',1);edge(commit,'Episodes Missing?','TV Result',1);save(commit)

for platform in ['Discord','Telegram']:
 w=copy.deepcopy(W['Media Request - '+platform]);prep='Validate Discord Request' if platform=='Discord' else 'Prepare Request'
 if platform=='Discord':
  v=get(w,prep)['parameters']['jsCode'];v=v.replace('messageId: b.messageId, requestedAt: b.requestedAt','messageId: b.messageId, requestedAt: b.requestedAt, action:b.action, pendingId:b.pendingId');get(w,prep)['parameters']['jsCode']=v
  ctx="{source:'discord',userId:p.userId,destinationId:p.channelId,messageId:p.messageId,requestedAt:p.requestedAt,text:p.text}"
  auth='Authorized Request?'; output='Respond to Discord'; interp='Validate Interpretation'
 else:
  get(w,'On message')['parameters']['updates']=['message','callback_query']
  get(w,prep).update(type='n8n-nodes-base.code',typeVersion=2,parameters={'jsCode':"const u=$json,q=u.callback_query,m=q?.message||u.message;if(!m)return [];const d=q?.data?.match(/^snake:([1-9][0-9]{0,15}):([a-z_0-9]+)$/);return [{json:{text:q?'confirmation':m.text||'',chatId:m.chat.id,userId:(q?.from||m.from).id,messageId:String(m.message_id),requestedAt:new Date(m.date*1000).toISOString(),action:d?.[2],pendingId:d?.[1],callbackId:q?.id}}];"})
  ctx="{source:'telegram',userId:String(p.userId),destinationId:String(p.chatId),messageId:p.messageId,requestedAt:p.requestedAt,text:p.text}"
  auth='Authorized User?';output='Format Interactive Reply';interp='Interpret Media Request'
  cred=copy.deepcopy(get(w,'Send a text message')['credentials'])
  w['nodes'] += [code(output,"const r=$json;const p=$('Prepare Request').first().json;let text=r.text|| (r.status==='not_found'?'🔎 No matching title was found. Try including the year.':'⚠️ Unable to process that request. Please try again.');return [{json:{...r,chatId:p.chatId,replyText:text,keyboard:{rows:(r.choices||[]).map(c=>({row:{buttons:[{text:c.label,additionalFields:{callback_data:'snake:'+r.pendingId+':'+c.action}}]}}))}}}];"),
   iff('Interactive Poster?',"!!$json.posterUrl"),
   n('Send Interactive Poster','telegram',{'resource':'message','operation':'sendPhoto','chatId':'={{ $json.chatId }}','file':'={{ $json.posterUrl }}','replyMarkup':'inlineKeyboard','inlineKeyboard':'={{ $json.keyboard }}','additionalFields':{'caption':'={{ $json.replyText }}','parse_mode':'HTML','appendAttribution':False}},credentials=cred,onError='continueRegularOutput'),
   iff('Interactive Poster Failed?',"!!$json.error"),
   n('Send Interactive Text','telegram',{'resource':'message','operation':'sendMessage','chatId':"={{ $('Format Interactive Reply').first().json.chatId }}",'text':"={{ $('Format Interactive Reply').first().json.replyText }}",'replyMarkup':'inlineKeyboard','inlineKeyboard':"={{ $('Format Interactive Reply').first().json.keyboard }}",'additionalFields':{'parse_mode':'HTML','appendAttribution':False}},credentials=cred)]
  # Telegram HTML text escaping prevents metadata being interpreted as markup.
  get(w,output)['parameters']['jsCode']=get(w,output)['parameters']['jsCode'].replace('replyText:text,',"replyText:text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'),")
  chain(w,output,'Interactive Poster?','Send Interactive Poster','Interactive Poster Failed?','Send Interactive Text');edge(w,'Interactive Poster?','Send Interactive Text',1)
 w['nodes'] += [iff('Confirmation Callback?',"!!$json.action"),code('Prepare Confirmation Action',"const p=$('"+prep+"').first().json;return [{json:{..."+ctx+",pendingId:p.pendingId,action:p.action}}];"),call('Resolve Confirmation','snakeConfirmMediaV1')]
 edge(w,auth,'Confirmation Callback?');chain(w,'Confirmation Callback?','Prepare Confirmation Action','Resolve Confirmation',output);edge(w,'Confirmation Callback?','Interpret Media Request',1)
 if platform=='Telegram':
  # Acknowledge before slow lookups; retain normalized input by explicit node reference.
  ack=n('Acknowledge Button','telegram',{'resource':'callback','operation':'answerQuery','queryId':"={{ $('Prepare Request').first().json.callbackId }}",'additionalFields':{}},credentials=cred,onError='continueRegularOutput')
  w['nodes'].append(ack);edge(w,'Confirmation Callback?','Acknowledge Button');edge(w,'Acknowledge Button','Prepare Confirmation Action')
 for media,port in [('movie',0),('tv',1)]:
  name='Prepare '+media+' Preview';inv='Preview '+media
  source="$('Validate Interpretation').first().json" if platform=='Discord' else "$('Interpret Media Request').first().json.output"
  w['nodes'] += [code(name,"const p=$('"+prep+"').first().json,m="+source+";return [{json:{context:"+ctx+",mediaType:'"+media+"',title:m.title,year:m.year}}];"),call(inv,'snakePreviewMediaV1')]
  edge(w,'Route Media Type',name,port);chain(w,name,inv,output)
 if platform=='Telegram':
  from telegram_cards import install
  install(w,n,code,iff,call,edge,wf,save)
 # Remove unreachable old add/search and tracking/reply branches; retain credential/model links.
 roots=['Discord Webhook'] if platform=='Discord' else ['On message']
 keep=set(roots)
 while True:
  old=set(keep)
  for src,connections in w['connections'].items():
   if src in keep:
    for ports in connections.values():
     for edges in ports:
      keep.update(e['node'] for e in edges)
  for src,connections in w['connections'].items():
   if 'ai_languageModel' in connections and any(e['node'] in keep for ports in connections.values() for edges in ports for e in edges):keep.add(src)
  if old==keep:break
 w['nodes']=[x for x in w['nodes'] if x['name'] in keep]
 for x in w['nodes']:
  if x['name'] in ['Resolve Confirmation','Preview movie','Preview tv']:x['onError']='continueRegularOutput'
 w['connections']={k:v for k,v in w['connections'].items() if k in keep};save(w)
print('Generated confirmation workflows and Telegram card renderer')
