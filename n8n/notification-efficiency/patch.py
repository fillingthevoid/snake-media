"""Apply scoped changes to an exported current bundle; preserve private credentials."""
import copy
import json
from pathlib import Path


def patch_workflows(workflows):
    result=copy.deepcopy(workflows)
    policy=Path(__file__).with_name('policy.js').read_text(encoding='utf-8')
    by_id={w['id']:w for w in result}
    queue=by_id['snakeNotificationQueueV1']
    nodes={n['name']:n for n in queue['nodes']}
    nodes['Validate Queue Action']['parameters']['jsCode']=(
        "const b=$input.first().json.body; "
        "if(b?.action==='poll'){const keys=b.excludeNotificationKeys||[];"
        "if(!Array.isArray(keys)||keys.length>1000||keys.some(k=>typeof k!=='string'||!k.length||k.length>300))"
        "throw new Error('Invalid queue exclusions');return [{json:{action:'poll',excludeNotificationKeys:keys}}];}"
        "if(b?.action==='ack'&&typeof b.notificationKey==='string'&&b.notificationKey.startsWith('discord:')"
        "&&b.notificationKey.length<=300&&typeof b.messageId==='string'&&/^[1-9][0-9]{0,19}$/.test(b.messageId))"
        "return [{json:b}];throw new Error('Invalid queue action');")
    nodes['Queue Batch']['parameters']['jsCode']=policy+(
        "\nreturn [{json:queueBatch($input.all().map(x=>x.json),"
        "$('Validate Queue Action').first().json.excludeNotificationKeys||[])}];")

    scan=by_id['snakeCompletionScanV1']
    nodes={n['name']:n for n in scan['nodes']}
    notices=copy.deepcopy(nodes['Tracked Requests'])
    notices.update(id='read-completion-notices',name='Completion Notices',position=[420,0],alwaysOutputData=True)
    notices['parameters']['dataTableId']=copy.deepcopy(
        next(n for n in queue['nodes'] if n['name']=='Pending Discord Notices')['parameters']['dataTableId'])
    notices['parameters']['filters']={'conditions':[]}
    filter_node={'id':'unfinished-requests','name':'Unfinished Requests','type':'n8n-nodes-base.code',
        'typeVersion':2,'position':[640,0],'parameters':{'jsCode':policy+(
        "\nreturn pendingRequests($('Tracked Requests').all().map(x=>x.json),"
        "$input.all().map(x=>x.json)).map(json=>({json}));")}}
    scan['nodes']=[n for n in scan['nodes'] if n['name'] not in ['Completion Notices','Unfinished Requests']]+[notices,filter_node]
    def edge(name): return {'main':[[{'node':name,'type':'main','index':0}]]}
    scan['connections']['Tracked Requests']=edge('Completion Notices')
    scan['connections']['Completion Notices']=edge('Unfinished Requests')
    if 'Real Requests Only' in nodes:
        scan['connections']['Unfinished Requests']=edge('One Library Read')
        code=nodes['Real Requests Only']['parameters']['jsCode']
        nodes['Real Requests Only']['parameters']['jsCode']=code.replace("$('Tracked Requests').all()","$('Unfinished Requests').all()")

    # This workflow only reads snapshots and formats status. Retain all errors.
    # Mutation coordinators, notification writers and recovery proof are untouched.
    status=by_id['snakeStatusInspectV1']
    status.setdefault('settings',{}).update(saveDataSuccessExecution='none',saveDataErrorExecution='all')
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.write_text(json.dumps(patch_workflows(json.loads(args.input.read_text(encoding='utf-8'))),
                                      ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
