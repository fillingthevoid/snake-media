"""Read-only status overlay. Supply a current private export on snake."""
import copy,json,sys,uuid
from pathlib import Path
R=Path(__file__).parent;OUT=R/'workflows';OUT.mkdir(exist_ok=True)
P=(R/'policy.js').read_text(encoding='utf-8-sig')
source=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig')) if len(sys.argv)>1 else [json.loads(p.read_text(encoding='utf-8-sig')) for folder in ['confirmation/workflows','tracking/notification-workflows'] for p in (R.parent/folder).glob('*.json')]
S={w['id']:w for w in source}
def get(w,n):return next(x for x in w['nodes'] if x['name']==n)
def node(name,kind,p,**extra):return dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL,'snake-status/'+name)),name=name,type='n8n-nodes-base.'+kind,typeVersion={'code':2,'if':2.3,'executeWorkflow':1.3,'executeWorkflowTrigger':1.1,'dataTable':1.1,'httpRequest':4.4}[kind],parameters=p,position=[0,0],**extra)
def code(n,s):return node(n,'code',{'jsCode':s})
def trigger(n):return node(n,'executeWorkflowTrigger',{'inputSource':'passthrough'})
def wf(i,n,nodes):return dict(id=i,name=n,nodes=nodes,connections={},settings={'executionOrder':'v1','executionTimeout':120},active=False,pinData={})
def edge(w,a,b,port=0):
 ports=w['connections'].setdefault(a,{}).setdefault('main',[])
 while len(ports)<=port:ports.append([])
 ports[port]=[{'node':b,'type':'main','index':0}]
def chain(w,*names):
 for a,b in zip(names,names[1:]):edge(w,a,b)
def iff(n,s):return node(n,'if',{'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':3},'conditions':[{'id':'test','leftValue':'={{ '+s+' }}','rightValue':'','operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}})
def call(n,i,each=False):return node(n,'executeWorkflow',{'workflowId':{'__rl':True,'mode':'id','value':i},'workflowInputs':{'mappingMode':'passThrough'},'mode':'each' if each else 'once','options':{'waitForSubWorkflow':True}},alwaysOutputData=True,onError='continueRegularOutput')
def data(n,t):return node(n,'dataTable',{'resource':'row','operation':'get','dataTableId':{'__rl':True,'mode':'name','value':t},'returnAll':True,'matchType':'allConditions','filters':{'conditions':[]},'options':{}},alwaysOutputData=True)
def http(n,kind,path,query=None,full=False):
 template=get(S['snakeCompletionScanV1'],'Read Jellyfin Library') if kind=='jellyfin' else get(S['snakeInspectRequestV1'],'Read Requested Movie' if kind=='movie' else 'Read Requested Episodes')
 base={'movie':'http://192.168.1.10:7878/api/v3/','tv':'http://192.168.1.10:8989/api/v3/','jellyfin':'http://192.168.1.10:8096/'}[kind]
 p={'method':'GET','url':'={{ '+repr(base)+' + ('+path[1:]+') }}' if path.startswith('=') else base+path,'sendHeaders':True,'headerParameters':copy.deepcopy(template['parameters']['headerParameters']),'options':{'timeout':12000}}
 if query:p.update(sendQuery=True,queryParameters={'parameters':[{'name':k,'value':v} for k,v in query.items()]})
 if full:p['options']['response']={'response':{'fullResponse':True,'neverError':True}}
 return node(n,'httpRequest',p,alwaysOutputData=True)
def pages(n,param,value,complete,maxpages=100):n['parameters']['options']['pagination']={'pagination':{'paginationMode':'updateAParameterInEachRequest','parameters':{'parameters':[{'type':'qs','name':param,'value':value}]},'paginationCompleteWhen':'other','completeExpression':complete,'limitPagesFetched':True,'maxRequests':maxpages}}
def save(w):
 for k in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived']:w.pop(k,None)
 w.update(active=False,pinData={})
 for i,n in enumerate(w['nodes']):n['position']=[i%7*270,i//7*250]
 f=OUT/(w['name']+'.json');f.write_text(json.dumps(w,indent=2,ensure_ascii=False),encoding='utf-8');f.chmod(0o600)
status=wf('snakeStatusV1','Snake Media - Request Status',[
 trigger('Status Input'),data('Read Status Requests','snake_media_requests'),
 code('Select Status Requests',P+"\nconst a=$('Status Input').first().json;const selected=select($input.all().map(x=>x.json),a);return [{json:{selected}}];"),
 iff('Status Has Matches?',"!!$json.selected[0].requests"),data('Read Status Retention','snake_media_retention_records'),
 code('One Status Library Read','return [{json:{}}];'),
 http('Read Status Library','jellyfin','Items',{'Recursive':'true','IncludeItemTypes':'Movie,Episode','Fields':'Path','Limit':'500','EnableImages':'false','EnableUserData':'false'}),
 code('Status Groups',"const pages=$input.all().map(x=>x.json);if(pages.some(p=>!Array.isArray(p.Items)||!Number.isInteger(p.TotalRecordCount))||pages.reduce((n,p)=>n+p.Items.length,0)<pages[0].TotalRecordCount)throw new Error('Incomplete Jellyfin status');const library=pages.flatMap(p=>p.Items).map(x=>({Id:x.Id,Path:x.Path}));const records=$('Read Status Retention').all().map(x=>x.json);return $('Select Status Requests').first().json.selected.map(g=>({json:{...g,records,library}}));"),
 call('Inspect Status Groups','snakeStatusInspectV1',True),
 code('Format Status Result',"const text=$input.all().map(x=>x.json.text||'⚠️ Status temporarily unavailable for one title.').join('\\n\\n');return [{json:{version:1,status:'notice',text:text.slice(0,1740)+(text.length>1740?'\\nUse status with a title for details.':'')}}];"),
 code('Status No Matches',"return [{json:{version:1,status:'notice',text:$('Select Status Requests').first().json.selected[0].notice}}];")])
pages(get(status,'Read Status Library'),'StartIndex','={{ $pageCount * 500 }}','={{ $response.body.Items.length < 500 }}')
chain(status,*[n['name'] for n in status['nodes'][:-1]]);edge(status,'Status Has Matches?','Status No Matches',1);save(status)
inspect=wf('snakeStatusInspectV1','Snake Media - Inspect Request Status',[
 trigger('Inspect Status Input'),iff('Status Movie?',"$json.requests[0].mediaType==='movie'"),
 http('Read Status Movie','movie',"='movie/'+$json.requests[0].mediaId",full=True),
 http('Read Status Series','tv',"='series/'+$json.requests[0].mediaId",full=True),
 code('Status Media Snapshot',"const r=$json;if(r.statusCode!==404&&(r.statusCode!==200||!r.body?.id))throw new Error('Media status unavailable');return [{json:{media:r.statusCode===404?null:r.body}}];"),
 iff('Status Needs Episodes?',"!!$json.media&&$('Inspect Status Input').first().json.requests[0].mediaType==='tv'"),
 http('Read Status Episodes','tv','episode',{'seriesId':"={{ $('Inspect Status Input').first().json.requests[0].mediaId }}",'includeEpisodeFile':'true'}),
 code('Status Episode Snapshot',"const movie=$('Inspect Status Input').first().json.requests[0].mediaType==='movie';const rows=$input.all().map(x=>x.json);return [{json:{episodes:movie||!$('Status Media Snapshot').first().json.media?[]:rows.filter(x=>x.id)}}];"),
 iff('Status Movie Queue?',"$('Inspect Status Input').first().json.requests[0].mediaType==='movie'"),
 http('Read Status Movie Queue','movie','queue',{'pageSize':'500','includeUnknownMovieItems':'false'}),
 http('Read Status TV Queue','tv','queue',{'pageSize':'500','includeUnknownSeriesItems':'false'}),
 code('Describe Status',P+"\nconst pages=$input.all().map(x=>x.json);if(pages.some(p=>!Array.isArray(p.records)||!Number.isInteger(p.totalRecords))||pages.reduce((n,p)=>n+p.records.length,0)<pages[0].totalRecords)throw new Error('Incomplete queue status');const i=$('Inspect Status Input').first().json;return [{json:{text:describe({...i,media:$('Status Media Snapshot').first().json.media,episodes:$('Status Episode Snapshot').first().json.episodes,queue:pages.flatMap(p=>p.records),now:Date.now()})}}];")])
for n in ['Read Status Movie Queue','Read Status TV Queue']:pages(get(inspect,n),'page','={{ $pageCount + 1 }}','={{ ($pageCount + 1) * 500 >= $response.body.totalRecords }}',20)
chain(inspect,'Inspect Status Input','Status Movie?','Read Status Movie','Status Media Snapshot','Status Needs Episodes?','Read Status Episodes','Status Episode Snapshot','Status Movie Queue?','Read Status Movie Queue','Describe Status')
edge(inspect,'Status Movie?','Read Status Series',1);edge(inspect,'Read Status Series','Status Media Snapshot');edge(inspect,'Status Needs Episodes?','Status Episode Snapshot',1);edge(inspect,'Status Movie Queue?','Read Status TV Queue',1);edge(inspect,'Read Status TV Queue','Describe Status');save(inspect)
for platform,wid,prep,output in [('Discord','HXtTzVTrpNZMZVt3','Validate Discord Request','Respond to Discord'),('Telegram','0e67KTcphqxEKNsh','Prepare Request','Format Interactive Reply')]:
 w=copy.deepcopy(S[wid]);assert not any(n['name']=='Status Command?' for n in w['nodes']),'Already patched'
 parse="const p=$('"+prep+"').first().json;return [{json:{...p,statusQuery:command(p.text)}}];"
 w['nodes'] += [code('Parse Status Command',P+'\n'+parse),iff('Status Command?',"$json.statusQuery!==null"),code('Prepare Status Actor',"const p=$json;return [{json:{source:'"+platform.lower()+"',userId:String(p.userId),query:p.statusQuery}}];"),call('Read Request Status','snakeStatusV1')]
 edge(w,'Confirmation Callback?','Parse Status Command',1);chain(w,'Parse Status Command','Status Command?','Prepare Status Actor','Read Request Status',output);edge(w,'Status Command?','Interpret Media Request',1);save(w)
print('Generated four status workflows')
