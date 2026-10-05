"""Scoped, idempotent efficiency overlay for the current workflow bundle."""
import copy
import json
from pathlib import Path

HERE = Path(__file__).parent
POLICY = (HERE/'policy.js').read_text(encoding='utf-8')
CHANGED_IDS = ('snakeStatusV1', 'snakeStatusInspectV1', 'snakeCompletionScanV1',
               'snakeRetentionScanV1', 'snakeRetentionPlayedV1')


def node(name, kind, parameters, version=2, **extra):
    return dict(id='efficiency-'+name.lower().replace(' ', '-').replace('?', ''),
                name=name, type='n8n-nodes-base.'+kind, typeVersion=version,
                parameters=parameters, position=[0, 0], **extra)


def code(name, body):
    return node(name, 'code', {'jsCode':POLICY+'\n'+body})


def condition(name, expression):
    return node(name, 'if', {'conditions':{'options':{'caseSensitive':True,
        'leftValue':'', 'typeValidation':'strict', 'version':3}, 'conditions':[
        {'id':'efficiency-test', 'leftValue':'={{ '+expression+' }}', 'rightValue':'',
         'operator':{'type':'boolean','operation':'true','singleValue':True}}],
        'combinator':'and'}, 'options':{}}, 2.3)


def edge(workflow, source, target, port=0):
    ports = workflow['connections'].setdefault(source, {}).setdefault('main', [])
    while len(ports)<=port: ports.append([])
    ports[port]=[{'node':target,'type':'main','index':0}]


def scope_completion_reads(scan):
    nodes={n['name']:n for n in scan['nodes']}
    nodes['Completion Request Batches']['parameters']['jsCode']=POLICY+'\nreturn completionBatches($input.all().map(x=>x.json)).map(json=>({json}));'
    # Native fixed collections require literal rows with expressions in leaves.
    # Repeated padding keys are harmless in an OR query; batches are never empty.
    nodes['Completion Notices']['parameters'].update(matchType='anyCondition',filters={'conditions':[
        {'keyName':'requestKey','condition':'eq','keyValue':'={{ $json.keys['+str(i)+'] ?? $json.keys[0] }}'}
        for i in range(200)]})


def patch_workflows(workflows):
    result=copy.deepcopy(workflows)
    by_id={w['id']:w for w in result}
    status,inspect,scan,retention,played=(by_id[k] for k in CHANGED_IDS)
    if any(n['name']=='Read Shared Movie Queue' for n in status['nodes']):
        scope_completion_reads(scan)
        return result
    def nodes(w):return {n['name']:n for n in w['nodes']}
    def filters(n,conditions,match='allConditions'):
        n['parameters'].update(matchType=match,filters={'conditions':conditions})
    def eq(k,v):return {'keyName':k,'condition':'eq','keyValue':v}
    sn,ins=nodes(status),nodes(inspect)
    filters(sn['Read Status Requests'],[
        eq('source',"={{ $('Status Input').first().json.source }}"),
        eq('userId',"={{ $('Status Input').first().json.userId }}"),eq('state','registered')])
    status['nodes']=[n for n in status['nodes'] if n['name'] not in ['Read Status Library','One Status Library Read']]
    for old in ['Read Status Library','One Status Library Read']:status['connections'].pop(old,None)
    status['nodes'].append(code('Status Queue Context',
        "return [{json:{selected:$('Select Status Requests').first().json.selected,records:$input.all().map(x=>x.json),movieQueue:[],tvQueue:[]}}];"))
    edge(status,'Read Status Retention','Status Queue Context')
    last='Status Queue Context'
    for label,key in [('Movie','movie'),('TV','tv')]:
        check='Status Needs '+label+' Queue?'
        read='Read Shared '+label+' Queue'
        snapshot='Shared '+label+' Queue Snapshot'
        context='Status Queue Context' if label=='Movie' else 'Shared Movie Queue Snapshot'
        original=copy.deepcopy(ins['Read Status '+label+' Queue'])
        original.update(name=read,id='efficiency-'+read.lower().replace(' ','-'))
        status['nodes'] += [condition(check,"$json.selected.some(g=>g.requests[0].mediaType==='"+key+"')"), original,
            code(snapshot,"const i=$('"+context+"').first().json;const needed=i.selected.some(g=>g.requests[0].mediaType==='"+key+"');return [{json:{...i,"+key+"Queue:needed?queueRows($input.all().map(x=>x.json)):[]}}];")]
        edge(status,last,check);edge(status,check,read);edge(status,read,snapshot);edge(status,check,snapshot,1)
        last=snapshot
    sn['Status Groups']['parameters']['jsCode']=(
        "const i=$input.first().json;return i.selected.map(g=>({json:{...g,records:i.records,queue:g.requests[0].mediaType==='movie'?i.movieQueue:i.tvQueue}}));")
    edge(status,last,'Status Groups')

    # Target lookup replaces the broad outer catalogue for all inspector callers.
    target=node('Read Status Target','executeWorkflow',{
        'workflowId':{'__rl':True,'mode':'id','value':'snakeTargetLibraryV1'},
        'workflowInputs':{'mappingMode':'passThrough'},'mode':'once',
        'options':{'waitForSubWorkflow':True}},1.3)
    inspect['nodes'] += [code('Prepare Status Target',
        "const r=$('Inspect Status Input').first().json.requests[0],media=$('Status Media Snapshot').first().json.media;return [{json:media?{mediaType:r.mediaType,title:media.title,mediaPath:media.path}:{gone:true}}];"),
        condition('Status Media Indexed?', '!$json.gone'),target,
        code('Status Target Snapshot',"return [{json:{jellyfinLibrary:$json.gone?[]:$json.jellyfinLibrary}}];"),
        condition('Status Queue Supplied?',"Array.isArray($('Inspect Status Input').first().json.queue)"),
        code('Use Shared Status Queue',"const queue=$('Inspect Status Input').first().json.queue;return [{json:{records:queue,totalRecords:queue.length}}];")]
    edge(inspect,'Status Episode Snapshot','Prepare Status Target')
    edge(inspect,'Prepare Status Target','Status Media Indexed?')
    edge(inspect,'Status Media Indexed?','Read Status Target')
    edge(inspect,'Read Status Target','Status Target Snapshot')
    edge(inspect,'Status Media Indexed?','Status Target Snapshot',1)
    edge(inspect,'Status Target Snapshot','Status Queue Supplied?')
    edge(inspect,'Status Queue Supplied?','Use Shared Status Queue')
    edge(inspect,'Use Shared Status Queue','Describe Status')
    edge(inspect,'Status Queue Supplied?','Status Movie Queue?',1)
    body=ins['Describe Status']['parameters']['jsCode']
    needle="const i=$('Inspect Status Input').first().json;"
    assert needle in body, 'Unknown status inspector contract'
    body=body.replace(needle,"const i={...$('Inspect Status Input').first().json,library:$('Status Target Snapshot').first().json.jellyfinLibrary};")
    ins['Describe Status']['parameters']['jsCode']=body

    # Filter historical/synthetic records natively, then batch notice reads by key.
    sc=nodes(scan)
    valid=[eq('state','registered'),{'keyName':'baselineCaptured','condition':'isTrue'},
           {'keyName':'userId','condition':'neq','keyValue':'1'}]
    filters(sc['Tracked Requests'],valid)
    scan['nodes'].append(code('Completion Request Batches',
        'return completionBatches($input.all().map(x=>x.json)).map(json=>({json}));'))
    edge(scan,'Tracked Requests','Completion Request Batches')
    edge(scan,'Completion Request Batches','Completion Notices')
    scope_completion_reads(scan)
    sc['Recent Download Events']['parameters']['filters']['conditions'][0]['keyValue']='={{ $now.minus({minutes:30}).toISO() }}'

    # Keep complete watch snapshots and deletion guards; avoid bulky fan-out.
    pn=nodes(played)
    pn['Watched Page Result']['parameters']['jsCode']=POLICY+"\nreturn [{json:{Items:compactWatched($input.all().map(x=>x.json))}}];"
    rn=nodes(retention)
    filters(rn['Read All Requests'],[eq('state','registered'),{'keyName':'userId','condition':'neq','keyValue':'1'}])
    retention['nodes'] += [condition('Retention Has Requests?',"$input.all().some(x=>x.json.requestKey&&x.json.state==='registered'&&x.json.userId!=='1')"),
        code('Empty Retention Summary','return [{json:{scanned:0,groups:[]}}];')]
    edge(retention,'Read All Requests','Retention Has Requests?')
    edge(retention,'Retention Has Requests?','One Retention Read')
    edge(retention,'Retention Has Requests?','Empty Retention Summary',1)
    for w in [status,inspect,scan,retention,played]:
        for i,n in enumerate(w['nodes']):n['position']=[i%7*270,i//7*240]
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.write_text(json.dumps(patch_workflows(json.loads(args.input.read_text(encoding='utf-8'))),indent=2)+'\n',encoding='utf-8')
