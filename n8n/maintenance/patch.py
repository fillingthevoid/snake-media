"""Scoped maintenance overlay using native n8n tables, never SQLite writes."""
import copy
from pathlib import Path

POLICY = (Path(__file__).parent / 'policy.js').read_text(encoding='utf-8')
CHANGED_IDS = ('snakeCompletionScanV1', 'snakeTrackRequestV1', 'snakeQueueCandidateV1',
               '0e67KTcphqxEKNsh', 'snakeTelegramCardV1', 'snakeTelegramNoticeSendV1')
MARKER_COLUMNS = {'requestKey':'string','source':'string','userId':'string',
                  'destinationId':'string','state':'string','queuedAt':'date'}


def node(name, kind, params, **extra):
    return {'id':'maintenance-'+name.lower().replace(' ', '-').replace('?', ''),
            'name':name, 'type':'n8n-nodes-base.'+kind, 'typeVersion':2,
            'parameters':params, 'position':[0, 0], **extra}


def code(name, body):
    return node(name, 'code', {'jsCode': POLICY+'\n'+body})


def connect(w, source, target, port=0):
    branches=w['connections'].setdefault(source, {}).setdefault('main', [])
    while len(branches)<=port:branches.append([])
    branches[port]=[{'node':target,'type':'main','index':0}]


def table(name, table_id, operation='get', filters=None, values=None, columns=None):
    params={'resource':'row','operation':operation,'dataTableId':{'__rl':True,'mode':'id','value':table_id},
            'matchType':'allConditions','filters':{'conditions':filters or []},'options':{}}
    if operation=='get':params['returnAll']=True
    if values is not None:
        params['columns']={'mappingMode':'defineBelow','value':values,'schema':[
            {'id':key,'displayName':key,'type':kind,'display':True,'required':False,
             'defaultMatch':False,'canBeUsedToMatch':True} for key,kind in columns.items()]}
    return node(name, 'dataTable', params, typeVersion=1, alwaysOutputData=operation=='get')


def eq(key, value):return {'keyName':key,'condition':'eq','keyValue':value}


def marker_write(name, index_id):
    return table(name,index_id,'upsert',[eq('requestKey','={{ $json.requestKey }}')],
                 {key:'={{ $json.'+key+' }}' for key in MARKER_COLUMNS},MARKER_COLUMNS)


def seed_nodes(request_id, notice_id, index_id):
    return [table('Read Registered Claims',request_id,filters=[eq('state','registered')]),
            table('Read Completion Proof',notice_id),table('Read Existing Completion Markers',index_id),
            code('Build Completion Markers',"return completionMarkers($('Read Registered Claims').all().map(x=>x.json),$('Read Completion Proof').all().map(x=>x.json),$input.all().map(x=>x.json)).map(json=>({json}));"),
            marker_write('Save Completion Markers',index_id)]


def seed_edges(w, start):
    for target in ['Read Registered Claims','Read Completion Proof','Read Existing Completion Markers','Build Completion Markers','Save Completion Markers']:
        connect(w,start,target);start=target


def setup_workflow(workflows, path, header_credentials):
    by_id={w['id']:w for w in workflows}
    requests=next(n for n in by_id['snakeCompletionScanV1']['nodes'] if n['name']=='Tracked Requests')['parameters']['dataTableId']['value']
    notices=next(n for n in by_id['snakeCompletionScanV1']['nodes'] if n['name']=='Completion Notices')['parameters']['dataTableId']['value']
    webhook=node('Setup Request','webhook',{'httpMethod':'POST','path':path,'authentication':'headerAuth','responseMode':'responseNode','options':{}},credentials=header_credentials,webhookId='snake-maintenance-setup-20261006')
    create=node('Create Completion Index','dataTable',{'resource':'table','operation':'create','tableName':'snake_media_completion_index',
        'columns':{'column':[{'name':key,'type':kind} for key,kind in MARKER_COLUMNS.items()]},'options':{'createIfNotExists':True}},typeVersion=1)
    w={'id':'snakeMaintenanceSetup20261006','name':'VERIFY - Maintenance Index Setup','nodes':[webhook,create,
       *seed_nodes(requests,notices,"={{ $('Create Completion Index').first().json.id }}"),
       code('Setup Summary',"return [{json:{indexId:$('Create Completion Index').first().json.id,markers:$input.all().length,pending:$input.all().filter(x=>x.json.state==='pending').length}}];"),
       node('Setup Response','respondToWebhook',{'respondWith':'json','responseBody':'={{ $json }}','options':{}})],
       'connections':{},'settings':{'executionOrder':'v1','saveDataSuccessExecution':'all','saveDataErrorExecution':'all'},'active':False}
    connect(w,'Setup Request','Create Completion Index');seed_edges(w,'Create Completion Index')
    connect(w,'Save Completion Markers','Setup Summary');connect(w,'Setup Summary','Setup Response')
    return w


def patch_workflows(workflows, index_id):
    result=copy.deepcopy(workflows);by_id={w['id']:w for w in result}
    if any(n['name']=='Read Pending Completion Index' for n in by_id[CHANGED_IDS[0]]['nodes']):return result
    def nodes(w):return {n['name']:n for n in w['nodes']}
    scan=by_id[CHANGED_IDS[0]];sn=nodes(scan)
    request_id=sn['Tracked Requests']['parameters']['dataTableId']['value']
    notice_id=sn['Completion Notices']['parameters']['dataTableId']['value']
    scan['nodes'] += [table('Read Pending Completion Index',index_id,filters=[eq('state','pending')]),
        code('Pending Completion Batches','return pendingBatches($input.all().map(x=>x.json)).map(json=>({json}));'),
        code('Repair Completed Markers',"const requests=$('Tracked Requests').all().map(x=>x.json),notices=$('Completion Notices').all().map(x=>x.json);return completionMarkers(requests,notices,[]).filter(x=>x.state==='complete').map(json=>({json}));"),
        marker_write('Retire Completed Marker',index_id)]
    # Preserve the existing event pruning branch.
    scan['connections']['Every Five Minutes']['main'][0][0]['node']='Read Pending Completion Index'
    connect(scan,'Read Pending Completion Index','Pending Completion Batches');connect(scan,'Pending Completion Batches','Tracked Requests')
    sn['Tracked Requests']['parameters'].update(matchType='anyCondition',filters={'conditions':[
        eq('requestKey','={{ $json.keys['+str(i)+'] ?? $json.keys[0] }}') for i in range(200)]})
    scan['connections']['Completion Notices']['main'][0].append({'node':'Repair Completed Markers','type':'main','index':0})
    connect(scan,'Repair Completed Markers','Retire Completed Marker')

    track=by_id[CHANGED_IDS[1]]
    track['nodes'] += [node('Registration Needs Completion?','if',{'conditions':{'options':{'typeValidation':'strict','version':3},
        'conditions':[{'id':'eligible','leftValue':'={{ $json.baselineCaptured===true && $json.userId!=="1" }}','operator':{'type':'boolean','operation':'true','singleValue':True}}],
        'combinator':'and'},'options':{}},typeVersion=2.3),
        code('Registration Context','return [{json:$json}];'),
        table('Find Completion Marker',index_id,filters=[eq('requestKey','={{ $json.requestKey }}')]),
        code('Prepare Registration Marker',"return completionMarkers([$ ('Registration Context').first().json],[],$input.all().map(x=>x.json)).map(json=>({json}));".replace('$ (','$(')),
        marker_write('Register Completion Marker',index_id),
        code('Restore Registration Context',"return [{json:$('Registration Context').first().json}];")]
    for source in ['Keep Existing','Insert Request']:connect(track,source,'Registration Needs Completion?')
    connect(track,'Registration Needs Completion?','Registration Context');connect(track,'Registration Needs Completion?','Return Tracking Record',1)
    for a,b in [('Registration Context','Find Completion Marker'),('Find Completion Marker','Prepare Registration Marker'),
                ('Prepare Registration Marker','Register Completion Marker'),('Register Completion Marker','Restore Registration Context'),
                ('Restore Registration Context','Return Tracking Record')]:connect(track,a,b)

    queue=by_id[CHANGED_IDS[2]]
    queue['nodes'] += [code('Completion Marker Proof',"const r=$('Candidate Input').first().json.request;return [{json:{requestKey:r.requestKey,source:r.source,userId:r.userId,destinationId:r.destinationId,state:'complete',queuedAt:new Date().toISOString()}}];"),
                       marker_write('Finish Completion Marker',index_id)]
    connect(queue,'Store Completion Notice','Completion Marker Proof');connect(queue,'Completion Marker Proof','Finish Completion Marker')

    telegram=by_id[CHANGED_IDS[3]];tn=nodes(telegram)
    tn['Clear Telegram Text Controls']['parameters'].update(ownerId="={{ String($('Prepare Request').first().json.userId) }}",callbackData="={{ $('On message').first().json.callback_query.data }}")
    body=tn['Format Interactive Reply']['parameters']['jsCode'];needle='chatId:p.chatId,replyText:'
    assert needle in body
    tn['Format Interactive Reply']['parameters']['jsCode']=body.replace(needle,'ownerId:String(p.userId),'+needle)
    credential=copy.deepcopy(tn['Clear Telegram Text Controls']['credentials'])
    def remember(name,owner):
        n=node(name,'code',{})
        n.update(type='CUSTOM.snakeTelegramControls',typeVersion=1,credentials=credential,onError='continueRegularOutput')
        n['parameters']={'operation':'remember','message':'={{ $json }}','ownerId':owner}
        return n
    card=by_id[CHANGED_IDS[4]]
    card['nodes'].append(remember('Remember Interactive Telegram Card',"={{ $('Card Input').first().json.ownerId || '' }}"))
    # Attach registration after a successful send. Photo fallback still uses
    # its original response through a dedicated restoration node.
    for send in list(card['nodes']):
        if send['type']!='n8n-nodes-base.telegram' or send['parameters'].get('operation') not in ['sendMessage','sendPhoto']:continue
        old=copy.deepcopy(card['connections'].get(send['name'],{}))
        if not old:connect(card,send['name'],'Remember Interactive Telegram Card')
        else:
            label='Remember '+send['name'];card['nodes'].append(remember(label,"={{ $('Card Input').first().json.ownerId || '' }}"))
            connect(card,send['name'],label);card['connections'][label]=old
    notices=by_id[CHANGED_IDS[5]]
    notices['nodes'].append(remember('Remember Telegram Completion Card',"={{ String(JSON.parse($('Notice Input').first().json.payloadJson).userId) }}"))
    for source,ports in list(notices['connections'].items()):
        for edges in ports.get('main',[]):
            for edge in edges:
                if edge['node']=='Validate Telegram Delivery':edge['node']='Remember Telegram Completion Card'
    connect(notices,'Remember Telegram Completion Card','Validate Telegram Delivery')

    daily={'id':'snakeCompletionIndexRepairV1','name':'Snake Media - Repair Completion Index','nodes':[
        node('Daily Completion Repair','scheduleTrigger',{'rule':{'interval':[{'field':'days','daysInterval':1,'triggerAtHour':4,'triggerAtMinute':20}]}},typeVersion=1.2),
        *seed_nodes(request_id,notice_id,index_id)],'connections':{},'settings':{'executionOrder':'v1','timezone':'America/Los_Angeles','saveDataSuccessExecution':'none','saveDataErrorExecution':'all'},'active':False}
    seed_edges(daily,'Daily Completion Repair');result.append(daily)
    control={'id':'snakeTelegramControlsRetryV1','name':'Snake Media - Retry Telegram Card Cleanup','nodes':[
        node('Every Five Minutes','scheduleTrigger',{'rule':{'interval':[{'field':'minutes','minutesInterval':5}]}},typeVersion=1.2),
        {**remember('Retry Related Keyboards',""), 'parameters':{'operation':'retry','message':'{}'}}],
        'connections':{},'settings':{'executionOrder':'v1','saveDataSuccessExecution':'none','saveDataErrorExecution':'all'},'active':False}
    connect(control,'Every Five Minutes','Retry Related Keyboards');result.append(control)
    pending_ref=next(n for n in by_id['snakeConfirmMediaV1']['nodes'] if n['name']=='Find Pending')['parameters']['dataTableId']['value']
    retire={'id':'snakeChoiceCompactionV1','name':'Snake Media - Compact Old Choices','nodes':[
        node('Weekly Choice Compaction','scheduleTrigger',{'rule':{'interval':[{'field':'days','daysInterval':7,'triggerAtHour':4,'triggerAtMinute':40}]}},typeVersion=1.2),
        table('Read Old Choices',pending_ref,filters=[{'keyName':'expiresAt','condition':'lt','keyValue':'={{ $now.minus({days:7}).toISO() }}'},
             {'keyName':'state','condition':'neq','keyValue':'processing'}]),
        code('Select Retired Payloads',"return $input.all().map(x=>x.json).filter(r=>r.contextJson!=='{}'||r.mediaJson!=='{}').map(r=>{const compact=retireChoice(r,Date.now());return compact?{json:{...compact,previousState:r.state,previousUpdatedAt:r.updatedAt}}:null;}).filter(Boolean);"),
        table('Retire Choice Payload',pending_ref,'update',[eq('id','={{ $json.id }}'),eq('state','={{ $json.previousState }}'),eq('updatedAt','={{ $json.previousUpdatedAt }}')],
              {'state':'={{ $json.state }}','contextJson':'{}','mediaJson':'{}'}, {'state':'string','contextJson':'string','mediaJson':'string'})],
        'connections':{},'settings':{'executionOrder':'v1','timezone':'America/Los_Angeles','saveDataSuccessExecution':'none','saveDataErrorExecution':'all'},'active':False}
    for a,b in [('Weekly Choice Compaction','Read Old Choices'),('Read Old Choices','Select Retired Payloads'),('Select Retired Payloads','Retire Choice Payload')]:connect(retire,a,b)
    result.append(retire)
    for w in result:
        if w['id'] in CHANGED_IDS or w['id'] in [daily['id'],control['id'],retire['id']]:
            for i,n in enumerate(w['nodes']):n['position']=[i%8*260,i//8*220]
    return result
