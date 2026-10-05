"""Overlay download events and targeted Jellyfin reads on a current workflow export."""
import copy
import json
from pathlib import Path

HERE=Path(__file__).parent
POLICY=(HERE/'policy.js').read_text(encoding='utf-8')
EVENT_FIELDS={'eventKey':'string','mediaType':'string','mediaId':'string','fileId':'string',
              'episodeIdsJson':'string','state':'string','payloadJson':'string',
              'importedAt':'date','receivedAt':'date'}


def node(name,kind,parameters,version=2,x=0):
    return {'name':name,'id':'tracking-'+name.lower().replace(' ','-').replace('?',''),
            'type':'n8n-nodes-base.'+kind,'typeVersion':version,'position':[x,0],'parameters':parameters}


def code(name,body,x=0):return node(name,'code',{'jsCode':POLICY+'\n'+body},x=x)


def connect(w,a,b,output=0):
    ports=w['connections'].setdefault(a,{'main':[]})['main']
    while len(ports)<=output:ports.append([])
    ports[output].append({'node':b,'type':'main','index':0})


def boolean(name,expression):
    return node(name,'if',{'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':3},
        'conditions':[{'id':'tracking-condition','leftValue':expression,'rightValue':'',
        'operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}},2.3)


def workflow(wid,name,nodes):
    return {'id':wid,'name':name,'nodes':nodes,'connections':{},'active':False,
            'settings':{'executionOrder':'v1','executionTimeout':120,'saveDataErrorExecution':'all'}}


def data(name,operation,table,conditions,values=None):
    p={'resource':'row','operation':operation,'dataTableId':table,'matchType':'allConditions',
       'filters':{'conditions':conditions},'options':{}}
    if operation=='get':p['returnAll']=True
    if values is not None:
        p['columns']={'mappingMode':'defineBelow','value':values,'schema':[
            {'id':k,'displayName':k,'type':EVENT_FIELDS[k],'display':True,'required':False,
             'defaultMatch':False,'canBeUsedToMatch':True} for k in values]}
    return node(name,'dataTable',p,1.1)


def eq(key,value,condition='eq'):return {'keyName':key,'condition':condition,'keyValue':value}


def jellyfin_read(original,name,query,page_size=100):
    n=copy.deepcopy(original)
    n.update(name=name,id='tracking-'+name.lower().replace(' ','-'),position=[400,0])
    for key in ['alwaysOutputData','onError','continueOnFail']:n.pop(key,None)
    p=n['parameters']
    p.update(method='GET',sendQuery=True,queryParameters={'parameters':[
        {'name':k,'value':v} for k,v in query.items()]})
    p['options']={'timeout':15000,'pagination':{'pagination':{
        'paginationMode':'updateAParameterInEachRequest','parameters':{'parameters':[
        {'type':'qs','name':'StartIndex','value':'={{ $pageCount * '+str(page_size)+' }}'}]},
        'paginationCompleteWhen':'other','completeExpression':
        '={{ ($pageCount + 1) * '+str(page_size)+' >= $response.body.TotalRecordCount }}',
        'limitPagesFetched':True,'maxRequests':100}}}
    return n


def patch_workflows(workflows,event_table_id=None):
    result=copy.deepcopy(workflows);by_id={w['id']:w for w in result}
    scan=by_id['snakeCompletionScanV1'];inspect=by_id['snakeInspectRequestV1']
    library=next((n for n in scan['nodes'] if n['name']=='Read Jellyfin Library'),None)
    if library is None:
        library=next(n for n in by_id['snakeTargetLibraryV1']['nodes'] if n['name']=='Read Target Movies')
    table={'__rl':True,'mode':'id','value':event_table_id or 'CONFIGURE_IMPORT_EVENTS_TABLE',
           'cachedResultName':'snake_media_import_events'}

    # Store only compact validated event metadata. Acknowledgement follows storage.
    webhook=next(n for n in by_id['snakeNotificationQueueV1']['nodes'] if n['type'].endswith('.webhook'))
    for kind,app in [('tv','Sonarr'),('movie','Radarr')]:
        hook=copy.deepcopy(webhook);hook.update(name='Download Event',id='tracking-'+app.lower()+'-event',
            webhookId='snake-'+app.lower()+'-events-v1',position=[0,0])
        hook['parameters']['path']='snake-media-'+app.lower()+'-events'
        normalize=code('Normalize Download Event',
            "const event=normalizeEvent($input.first().json.body,'"+kind+"',Date.now());return [{json:event||{ignored:true}}];")
        store=data('Store Download Event','upsert',table,[eq('eventKey','={{ $json.eventKey }}')],
            {k:'={{ $json.'+k+' }}' for k in EVENT_FIELDS})
        response=node('Event Response','respondToWebhook',{'respondWith':'json',
            'responseBody':'={{ {accepted:true} }}','options':{'responseCode':200}},1.4)
        w=workflow('snake'+app+'EventsV1','Snake Media - '+app+' Download Events',
            [hook,normalize,boolean('Store Event?','={{ Boolean($json.eventKey) }}'),store,response])
        # The incoming request contains a private authentication header and raw
        # release metadata. Keep the compact event record, not execution payloads.
        w['settings'].update(saveDataSuccessExecution='none',saveDataErrorExecution='none')
        for a,b in [('Download Event','Normalize Download Event'),('Normalize Download Event','Store Event?'),
                    ('Store Event?','Store Download Event'),('Store Download Event','Event Response')]:connect(w,a,b)
        connect(w,'Store Event?','Event Response',1)
        by_id[w['id']]=w

    # Read only the matched movie directory or the exact matched series parent.
    trigger=node('Target Input','executeWorkflowTrigger',{'inputSource':'passthrough'},1.1)
    common={'Recursive':'true','Fields':'Path','EnableImages':'false','EnableUserData':'false','Limit':'100'}
    search={'SearchTerm':'={{ $json.title }}',**common}
    target=workflow('snakeTargetLibraryV1','Snake Media - Read Target Library',[
        trigger,boolean('Target Movie?',"={{ $json.mediaType==='movie' }}"),
        jellyfin_read(library,'Read Target Movies',{**search,'IncludeItemTypes':'Movie'}),
        jellyfin_read(library,'Read Target Series',{**search,'IncludeItemTypes':'Series'}),
        code('Select Series Root',"return [{json:{parentId:targetRoot('tv',$('Target Input').first().json.mediaPath,$input.all().map(x=>x.json))}}];"),
        boolean('Series Indexed?','={{ Boolean($json.parentId) }}'),
        jellyfin_read(library,'Read Series Files',{**common,'Limit':'500','IncludeItemTypes':'Episode','ParentId':'={{ $json.parentId }}'},500),
        code('Target File Snapshot',"return [{json:{jellyfinLibrary:targetFiles($('Target Input').first().json.mediaPath,$input.all().map(x=>x.json))}}];"),
        node('Empty Target Snapshot','code',{'jsCode':'return [{json:{jellyfinLibrary:[]}}];'})])
    for a,b in [('Target Input','Target Movie?'),('Target Movie?','Read Target Movies'),('Read Target Movies','Target File Snapshot'),
                ('Read Target Series','Select Series Root'),('Select Series Root','Series Indexed?'),
                ('Series Indexed?','Read Series Files'),('Read Series Files','Target File Snapshot')]:connect(target,a,b)
    connect(target,'Target Movie?','Read Target Series',1);connect(target,'Series Indexed?','Empty Target Snapshot',1)
    target['settings']['saveDataSuccessExecution']='none'
    by_id[target['id']]=target

    # Match imports against the original immutable request, using the scoped library.
    nodes={n['name']:n for n in inspect['nodes']}
    series=copy.deepcopy(nodes['Read Requested Episodes'])
    base=series['parameters']['url'].split('/api/v3/')[0]
    series.update(name='Read Requested Series',id='tracking-read-requested-series',position=[400,200])
    series['parameters']['url']="={{ '"+base+"/api/v3/series/'+$json.mediaId }}"
    series['parameters']['queryParameters']={'parameters':[]}
    episodes=nodes['Read Requested Episodes']
    next(q for q in episodes['parameters']['queryParameters']['parameters'] if q['name']=='seriesId')['value']="={{ $('Inspect Request').first().json.mediaId }}"
    prepare=node('Prepare Library Target','code',{'jsCode':
        "const request=$('Inspect Request').first().json;const media=request.mediaType==='movie'?$input.first().json:$('Read Requested Series').first().json;"
        "if(typeof media.title!=='string'||!media.title.trim()||typeof media.path!=='string')throw new Error('Media target unavailable');"
        "return [{json:{request,mediaType:request.mediaType,title:media.title,mediaPath:media.path,mediaSnapshot:$input.all().map(x=>x.json)}}];"})
    call=node('Read Target Library','executeWorkflow',{'workflowId':{'__rl':True,'mode':'id','value':target['id']},
        'workflowInputs':{'mappingMode':'passThrough'},'mode':'once','options':{'waitForSubWorkflow':True}},1.3)
    candidate=nodes['Imported Candidates']['parameters']['jsCode']
    if "const r=$('Inspect Request').first().json;" in candidate:
        candidate=candidate.replace("const r=$('Inspect Request').first().json;",
            "const target=$('Prepare Library Target').first().json;const r={...target.request,jellyfinLibrary:$input.first().json.jellyfinLibrary};")
        candidate=candidate.replace('let items=$input.all();','let items=target.mediaSnapshot.map(json=>({json}));')
    nodes['Imported Candidates']['parameters']['jsCode']=candidate
    extra=[series,prepare,call]
    inspect['nodes']=[n for n in inspect['nodes'] if n['name'] not in {x['name'] for x in extra}]+extra
    inspect['connections']['Movie Request?']['main'][1]=[{'node':series['name'],'type':'main','index':0}]
    for a,b in [('Read Requested Series','Read Requested Episodes'),('Read Requested Movie','Prepare Library Target'),
                ('Read Requested Episodes','Prepare Library Target'),('Prepare Library Target','Read Target Library'),('Read Target Library','Imported Candidates')]:
        inspect['connections'][a]={'main':[[{'node':b,'type':'main','index':0}]]}

    # Sole periodic producer: event targeting plus slower reconciliation.
    event_read=data('Recent Download Events','get',table,
        [eq('receivedAt','={{ $now.minus({hours:24}).toISO() }}','gt')]);event_read['alwaysOutputData']=True
    affected=code('Affected Requests',"return affectedRequests($('Unfinished Requests').all().map(x=>x.json),$input.all().map(x=>x.json),Date.now()).map(json=>({json}));")
    prune=data('Prune Old Download Events','deleteRows',table,[eq('receivedAt','={{ $now.minus({days:7}).toISO() }}','lt')])
    remove={'One Library Read','Read Jellyfin Library','Real Requests Only','Recent Download Events','Affected Requests','Prune Old Download Events'}
    scan['nodes']=[n for n in scan['nodes'] if n['name'] not in remove]+[event_read,affected,prune]
    for name in remove:scan['connections'].pop(name,None)
    scan['connections']['Unfinished Requests']={'main':[[{'node':'Recent Download Events','type':'main','index':0}]]}
    connect(scan,'Recent Download Events','Affected Requests')
    connect(scan,'Affected Requests','Inspect Each Request');connect(scan,'Affected Requests','Inspect Each Progress')
    # Cleanup stays active even when there are no outstanding requests.
    trigger=next(n['name'] for n in scan['nodes'] if n['type'].endswith('.scheduleTrigger'))
    scan['connections'][trigger]['main'][0]=[e for e in scan['connections'][trigger]['main'][0] if e['node']!='Prune Old Download Events']
    connect(scan,trigger,'Prune Old Download Events')
    next(n for n in scan['nodes'] if n['name']=='Inspect Each Request')['onError']='continueRegularOutput'
    next(n for n in scan['nodes'] if n['name']=='Inspect Each Progress')['onError']='continueRegularOutput'

    result=[by_id[w['id']] for w in result]
    existing={w['id'] for w in result}
    result.extend(w for wid,w in by_id.items() if wid not in existing)
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--event-table-id');args=p.parse_args()
    args.output.write_text(json.dumps(patch_workflows(json.loads(args.input.read_text(encoding='utf-8')),args.event_table_id),
        ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
