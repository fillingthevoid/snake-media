"""Make scan collection read-only and serialize reconciliation one title at a time."""
import copy
import json
from pathlib import Path
import uuid

ROOT=Path(__file__).resolve().parents[2]
GROUP='snakeRetentionGroupV1'


def make(name,kind,params,version):
    return {'id':str(uuid.uuid5(uuid.NAMESPACE_URL,'snake-short-locks/'+name)),
            'name':name,'type':'n8n-nodes-base.'+kind,'typeVersion':version,
            'position':[0,0],'parameters':params}


def iff(name,expr):
    return make(name,'if',{'conditions':{'options':{'typeValidation':'strict','version':3},
        'conditions':[{'id':name,'leftValue':'={{ '+expr+' }}','operator':{'type':'boolean','operation':'true','singleValue':True}}],
        'combinator':'and'},'options':{}},2.3)


def raw(name,expr):
    return make(name,'set',{'mode':'raw','jsonOutput':'={{ '+expr+' }}','options':{}},3.4)


def code(name,body):
    return make(name,'code',{'jsCode':body},2)


def eq(key,value):
    return {'keyName':key,'condition':'eq','keyValue':value}


def data(template,name,operation,filters,values=None):
    n=copy.deepcopy(template);n.update(id=make(name,'dataTable',{},1.1)['id'],name=name,alwaysOutputData=True)
    p=n['parameters'];p.update(operation=operation,matchType='allConditions',filters={'conditions':filters})
    if operation=='get':
        p['returnAll']=True;p.pop('columns',None)
    else:
        p.pop('returnAll',None)
        p['columns']={'mappingMode':'defineBelow','value':values,'schema':[
            {'id':k,'displayName':k,'type':'string','display':True,'required':False,'defaultMatch':False,'canBeUsedToMatch':True} for k in values]}
    return n


def edge(w,a,b,port=0):
    ports=w['connections'].setdefault(a,{}).setdefault('main',[])
    while len(ports)<=port:ports.append([])
    ports[port]=[{'node':b,'type':'main','index':0}]


def finish(rows):
    workflows={w['id']:w for w in rows}
    coord=workflows['snakeRetentionCoordinatorV1']
    cn={n['name']:n for n in coord['nodes']}
    cn['Run Locked Scan']['alwaysOutputData']=False
    # Lock bookkeeping is expression-only. A shutdown of the Code runner must
    # not prevent ownership checks, dispatch preparation or a verified release.
    for name,expr in {
        'Verify Global Lock':"({owned:$json.owner===String($execution.id)})",
        'Locked Input':"({...$('Coordinator Input').first().json,owner:String($execution.id)})",
        'Save Locked Result':"({result:$json})",
        'Return Locked Result':"$('Save Locked Result').first().json.result",
    }.items():
        replacement=raw(name,expr)
        cn[name].update(type=replacement['type'],typeVersion=replacement['typeVersion'],parameters=replacement['parameters'])
    if 'Global Lock Released?' not in cn:
        coord['nodes'].append(iff('Global Lock Released?',"$json.key==='global'&&$json.owner===''"))
    edge(coord,'Release Global Lock','Global Lock Released?')
    edge(coord,'Global Lock Released?','Return Locked Result')
    edge(coord,'Global Lock Released?','Uncertain Mutation Result',1)
    # Only a genuine busy response may restore a pending confirmation for retry.
    cn['Uncertain Mutation Result']['parameters']['jsonOutput']="={{ ({deferred:true,uncertain:true,reason:'mutation_requires_review',version:1,status:'notice',text:'A media operation needs review. Please check /status before submitting it again.'}) }}"
    if 'Preparing Phase Owned?' not in cn:
        coord['nodes'].append(iff('Preparing Phase Owned?',"$('Mark Preparing Phase').all().length===1&&$json.key==='global-phase'&&$json.owner===String($execution.id)+':preparing'"))
    edge(coord,'Mark Preparing Phase','Preparing Phase Owned?')
    edge(coord,'Preparing Phase Owned?','Restore Prepared Input')
    edge(coord,'Preparing Phase Owned?','Uncertain Mutation Result',1)
    for gate,reader in [('Safe Planning Failure?','Read Failed Phase'),('Other Mutation Phase Owned?','Mark Other Mutation')]:
        condition=cn[gate]['parameters']['conditions']['conditions'][0]
        expr=condition['leftValue']
        prefix="$('"+reader+"').all().length===1&&"
        if prefix not in expr:condition['leftValue']=expr.replace('={{ ','={{ '+prefix,1)
    worker=workflows.get('snakeRetentionMediaV1')
    if worker:
        # Amendments already entered mutating before taking their forced-preview
        # snapshots. Preserve that phase; never downgrade an uncertain operation.
        barrier=next(n for n in worker['nodes'] if n['name']=='Mark Retention Mutation')
        owner=next(f for f in barrier['parameters']['filters']['conditions'] if f['keyName']=='owner')
        owner['keyValue']="={{ $('Media Input').first().json.owner+($('Media Input').first().json.job==='retention_media'?':preparing':$('Media Input').first().json.mode==='preview'?':mutating':':invalid') }}"
        gate=next(n for n in worker['nodes'] if n['name']=='Retention Mutation Phase Owned?')
        condition=gate['parameters']['conditions']['conditions'][0]
        prefix="$('Mark Retention Mutation').all().length===1&&"
        if prefix not in condition['leftValue']:condition['leftValue']=condition['leftValue'].replace('={{ ','={{ '+prefix,1)
    # n8n runs a table reader for every incoming item. Collapse the request rows
    # before reading records, otherwise titles with several claimants duplicate
    # every amendment and fail the planner's duplicate-record protection.
    group=workflows[GROUP]
    if worker:
        # This wrapper waits for the existing worker, including serial file
        # cleanup. Do not introduce a shorter timeout than the original budget.
        budgets=[w.get('settings',{}).get('executionTimeout',600) for w in (coord,worker)]
        if any(type(v) is not int or v<=0 for v in budgets):
            raise ValueError('Unknown bounded retention timeout')
        group.setdefault('settings',{})['executionTimeout']=min(budgets)
    nodes={n['name']:n for n in group['nodes']}
    if 'One Group Record Read' not in nodes:
        group['nodes'].append(code('One Group Record Read','return [{json:{}}];'))
    edge(group,'Read Current Group Requests','One Group Record Read')
    edge(group,'One Group Record Read','Read Current Group Records')
    policy=(ROOT/'n8n/retention-locks/policy.js').read_text(encoding='utf-8')
    nodes['Refresh Group Claims']['parameters']['jsCode']=policy+"\nconst modes=$('Read Current Group Mode').all().map(x=>x.json).filter(r=>r.key==='mode');if(modes.length!==1)throw Error('Invalid current retention mode');return [{json:freshGroup($('Group Input').first().json,$('Read Current Group Requests').all().map(x=>x.json),$('Read Current Group Records').all().map(x=>x.json),modes[0].owner,Date.now())}];"
    return rows


def build(source):
    rows=copy.deepcopy(source);workflows={w['id']:w for w in rows}
    coord=workflows['snakeRetentionCoordinatorV1'];cn={n['name']:n for n in coord['nodes']}
    if 'Run Unlocked Scan' in cn:
        if GROUP not in workflows:raise ValueError('Partial short-lock installation')
        return finish(rows)
    scan=workflows['snakeRetentionScanV1'];sn={n['name']:n for n in scan['nodes']}
    worker=workflows['snakeRetentionMediaV1'];wn={n['name']:n for n in worker['nodes']}
    if cn['Run Locked Scan']['parameters']['workflowId']['value']!='snakeRetentionScanV1':raise ValueError('Unknown coordinator scan route')
    control=cn['Acquire Global Lock']
    # Native nodes on the error path remain usable if the Code runner is unavailable.
    prep=data(control,'Mark Preparing Phase','upsert',[eq('key','global-phase')],
              {'key':'global-phase','owner':"={{ String($execution.id)+':preparing' }}"})
    mark=data(control,'Mark Other Mutation','update',[eq('key','global-phase'),eq('owner',"={{ String($execution.id)+':preparing' }}")],
              {'owner':"={{ String($execution.id)+':mutating' }}"})
    unlocked=copy.deepcopy(cn['Run Locked Scan']);unlocked.update(id=make('Run Unlocked Scan','executeWorkflow',{},1.3)['id'],name='Run Unlocked Scan')
    cn['Run Locked Scan']['parameters']['workflowId']['value']=GROUP
    cn['Run Locked Scan']['onError']='continueErrorOutput'
    coord['nodes'] += [iff('Scan Job?',"$json.job==='scan'"),unlocked,prep,
        raw('Restore Prepared Input',"$('Locked Input').first().json"),
        iff('Retention Media Job?',"$json.job==='retention_media'"),mark,
        iff('Other Mutation Phase Owned?',"$json.key==='global-phase'&&$json.owner===String($execution.id)+':mutating'"),
        raw('Restore Mutation Input',"$('Locked Input').first().json"),
        data(control,'Read Failed Phase','get',[eq('key','global-phase')]),
        iff('Safe Planning Failure?',"$json.key==='global-phase'&&$json.owner===String($execution.id)+':preparing'"),
        data(control,'Release Safe Failed Lock','update',[eq('key','global'),eq('owner','={{ String($execution.id) }}')],{'owner':''}),
        iff('Safe Failed Lock Released?',"$json.key==='global'&&$json.owner===''"),
        raw('Safe Planning Failure Result',"({deferred:true,reason:'planning_failed',mediaType:$('Locked Input').first().json.requests?.[0]?.mediaType,mediaId:$('Locked Input').first().json.requests?.[0]?.mediaId})"),
        raw('Uncertain Mutation Result',"({deferred:true,uncertain:true,reason:'mutation_requires_review',version:1,status:'notice',busy:true,text:'A media operation needs recovery. Please try again in a moment.'})")]
    edge(coord,'Coordinator Input','Scan Job?');edge(coord,'Scan Job?','Run Unlocked Scan');edge(coord,'Scan Job?','Read Global Lock',1)
    edge(coord,'Locked Input','Mark Preparing Phase');edge(coord,'Mark Preparing Phase','Restore Prepared Input');edge(coord,'Restore Prepared Input','Retention Media Job?')
    edge(coord,'Retention Media Job?','Run Locked Scan');edge(coord,'Retention Media Job?','Mark Other Mutation',1)
    edge(coord,'Mark Other Mutation','Other Mutation Phase Owned?');edge(coord,'Other Mutation Phase Owned?','Restore Mutation Input');edge(coord,'Other Mutation Phase Owned?','Uncertain Mutation Result',1)
    edge(coord,'Restore Mutation Input','Commit Job?')
    # Unknown jobs fail closed; legitimate scan jobs already bypassed the lock.
    edge(coord,'Retention Change Job?','Uncertain Mutation Result',1)
    edge(coord,'Run Locked Scan','Read Failed Phase',1)
    edge(coord,'Read Failed Phase','Safe Planning Failure?');edge(coord,'Safe Planning Failure?','Release Safe Failed Lock');edge(coord,'Safe Planning Failure?','Uncertain Mutation Result',1)
    edge(coord,'Release Safe Failed Lock','Safe Failed Lock Released?');edge(coord,'Safe Failed Lock Released?','Safe Planning Failure Result');edge(coord,'Safe Failed Lock Released?','Uncertain Mutation Result',1)

    # Refresh claims and mode after acquiring the per-group mutation lock.
    trigger=copy.deepcopy(wn['Media Input']);trigger.update(id=make('Group Input','executeWorkflowTrigger',{},1.1)['id'],name='Group Input')
    requests=data(sn['Read All Requests'],'Read Current Group Requests','get',[
        eq('mediaType',"={{ $('Group Input').first().json.requests[0].mediaType }}"),
        eq('mediaId',"={{ String($('Group Input').first().json.requests[0].mediaId) }}"),eq('state','registered')])
    records=data(sn['Read All Retention Records'],'Read Current Group Records','get',[])
    mode=data(sn['Read Retention Mode'],'Read Current Group Mode','get',[eq('key','mode')])
    policy=(ROOT/'n8n/retention-locks/policy.js').read_text(encoding='utf-8')
    fresh=code('Refresh Group Claims',policy+"\nreturn [{json:freshGroup($('Group Input').first().json,$('Read Current Group Requests').all().map(x=>x.json),$('Read Current Group Records').all().map(x=>x.json),$('Read Current Group Mode').first().json.owner,Date.now())}];")
    call=copy.deepcopy(sn['Process Each Retention Group']);call.update(id=make('Reconcile Current Group','executeWorkflow',{},1.3)['id'],name='Reconcile Current Group');call['parameters']['mode']='once'
    group={'id':GROUP,'name':'Snake Media - Reconcile Current Retention Group','active':False,
           'nodes':[trigger,mode,requests,records,fresh,iff('Current Group Ready?','!$json.deferred'),call,
                    raw('Group Deferred',"({deferred:true,reason:$json.reason})")],
           'connections':{},'settings':{'executionOrder':'v1','executionTimeout':120},'pinData':{}}
    names=['Group Input','Read Current Group Mode','Read Current Group Requests','Read Current Group Records','Refresh Group Claims','Current Group Ready?','Reconcile Current Group']
    for a,b in zip(names,names[1:]):edge(group,a,b)
    edge(group,'Current Group Ready?','Group Deferred',1);rows.append(group)

    body=sn['Group Retention Requests']['parameters']['jsCode']
    old="owner:$('Scan Input').first().json.owner,"
    if body.count(old)!=1:raise ValueError('Unknown scan grouping owner')
    sn['Group Retention Requests']['parameters']['jsCode']=body.replace(old,"job:'retention_media',snapshotAt:new Date().toISOString(),")
    sn['Process Each Retention Group']['parameters']['workflowId']['value']=coord['id']
    scan['name']='Snake Media - Collect and Reconcile Retention'
    # Every media mutation still runs under an exact-owner global lock.
    barrier=data(control,'Mark Retention Mutation','update',[
        eq('key','global-phase'),eq('owner',"={{ $('Media Input').first().json.owner+':preparing' }}")],
        {'owner':"={{ $('Media Input').first().json.owner+':mutating' }}"})
    worker['nodes'] += [barrier,
        iff('Retention Mutation Phase Owned?',"$json.key==='global-phase'&&$json.owner===$('Media Input').first().json.owner+':mutating'"),
        code('Retention Ownership Lost',"throw Error('Retention mutation ownership lost');")]
    body=wn['Records To Persist']['parameters']['jsCode']
    if 'const p=$json;' not in body:raise ValueError('Unknown retention persistence plan')
    wn['Records To Persist']['parameters']['jsCode']=body.replace('const p=$json;',"const p=$('Plan Retention').first().json;")
    edge(worker,'Plan Retention','Mark Retention Mutation');edge(worker,'Mark Retention Mutation','Retention Mutation Phase Owned?')
    edge(worker,'Retention Mutation Phase Owned?','Records To Persist');edge(worker,'Retention Mutation Phase Owned?','Retention Ownership Lost',1)
    return finish(rows)


if __name__=='__main__':
    import sys
    rows=build(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
    Path(sys.argv[2]).write_text(json.dumps(rows,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')
