"""Add a read-only health route to a current private Discord workflow export."""
import copy
import json
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).parent


def build(source,collector_url):
    source={w['id']:w for w in source}
    parent=copy.deepcopy(source['HXtTzVTrpNZMZVt3'])
    policy=(ROOT/'policy.js').read_text(encoding='utf-8-sig')
    def node(name,kind,params,**extra):
        versions={'code':2,'if':2.3,'executeWorkflow':1.3,'executeWorkflowTrigger':1.1,'httpRequest':4.4}
        return dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL,'snake-health/'+name)),name=name,type='n8n-nodes-base.'+kind,typeVersion=versions[kind],parameters=params,position=[0,0],**extra)
    def code(name,js): return node(name,'code',{'jsCode':js})
    def edge(w,a,b,port=0):
        ports=w['connections'].setdefault(a,{}).setdefault('main',[])
        while len(ports)<=port: ports.append([])
        ports[port]=[{'node':b,'type':'main','index':0}]
    webhook=next(n for n in parent['nodes'] if n['name']=='Discord Webhook')
    http=node('Read Private Host Health','httpRequest',{'method':'GET','url':collector_url,'authentication':'genericCredentialType','genericAuthType':'httpHeaderAuth','options':{'timeout':25000}},credentials=copy.deepcopy(webhook['credentials']),onError='continueRegularOutput')
    health={'id':'snakeServerHealthV1','name':'Snake Media - Server Health','nodes':[node('Health Input','executeWorkflowTrigger',{'inputSource':'passthrough'}),http,code('Format Health Report',policy+'\nreturn [{json:{version:1,status:"notice",text:report($json)}}];')],'connections':{},'settings':{'executionOrder':'v1','executionTimeout':35},'active':False,'pinData':{}}
    edge(health,'Health Input','Read Private Host Health');edge(health,'Read Private Host Health','Format Health Report')
    if any(n['name']=='Server Health Command?' for n in parent['nodes']): raise ValueError('already_patched')
    replaced=0
    for links in parent['connections'].values():
        for port in links.get('main',[]):
            for link in port:
                if link['node']=='Parse Status Command': link['node']='Parse Server Health Command';replaced+=1
    if replaced!=1: raise ValueError('unexpected_status_route')
    parent['nodes'] += [code('Parse Server Health Command',policy+'\nconst p=$("Validate Discord Request").first().json;return [{json:{...p,serverHealthCommand:command(p.text)}}];'),node('Server Health Command?','if',{'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':3},'conditions':[{'id':'health','leftValue':'={{ $json.serverHealthCommand }}','rightValue':'','operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}}),node('Read Server Health','executeWorkflow',{'workflowId':{'__rl':True,'mode':'id','value':'snakeServerHealthV1'},'workflowInputs':{'mappingMode':'passThrough'},'mode':'once','options':{'waitForSubWorkflow':True}},onError='continueRegularOutput'),code('Normalize Health Reply','return [{json:{version:1,status:"notice",text:typeof $json.text==="string"?$json.text:"⚠️ Server health is temporarily unavailable."}}];')]
    edge(parent,'Parse Server Health Command','Server Health Command?');edge(parent,'Server Health Command?','Read Server Health');edge(parent,'Server Health Command?','Parse Status Command',1);edge(parent,'Read Server Health','Normalize Health Reply');edge(parent,'Normalize Health Reply','Respond to Discord')
    for w in [health,parent]:
        for key in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived']: w.pop(key,None)
        w.update(active=False,pinData={})
        for i,n in enumerate(w['nodes']): n['position']=[i%7*270,i//7*250]
    return [health,parent]


if __name__=='__main__':
    output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True)
    for w in build(json.loads(Path(sys.argv[1]).read_text()),sys.argv[3]):
        p=output/(w['id']+'.json');p.write_text(json.dumps(w,indent=2));p.chmod(0o600)
    print('Built health subworkflow and Discord routing overlay')
