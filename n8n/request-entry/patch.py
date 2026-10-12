"""Scoped request entry overlay; commit writes stay unchanged."""
import copy,json,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def embed(code,file):
    policy=(ROOT/'n8n'/file).read_text(encoding='utf-8').rstrip();header=policy.splitlines()[0]
    if header not in code:return code
    start=code.index(header);mark=code.index("\nif(typeof module!=='undefined')module.exports=",start);end=code.index(';',mark)+1
    return code[:start]+policy+code[end:]
def build(source):
    rows=copy.deepcopy(source);by={w['id']:w for w in rows}
    for w in rows:
        for n in w['nodes']:
            p=n.get('parameters',{});code=p.get('jsCode')
            if isinstance(code,str):
                code=embed(code,'request-simplification/policy.js');code=embed(code,'status/policy.js')
                if w['id']=='snakeStatusInspectV1' and n['name']=='Describe Status':code=code.replace('summaryText:projection.summaryText,','summaryText:projection.summaryText,availability:projection.availability,') if 'availability:projection.availability' not in code else code
                if w['id']=='snakeStatusV1' and n['name']=='Format Status Result':code=code.replace('retentionActions:single.retentionActions,','retentionActions:single.retentionActions,availability:single.availability,') if 'availability:single.availability' not in code else code
                p['jsCode']=code
    body=by['snakeCommitMediaBodyV2'];nodes={n['name']:n for n in body['nodes']}
    nodes['Movie Result']['parameters']['jsCode']="const r=$('Movie Snapshot').first().json,t=$('Register Movie Before Search').first().json;return [{json:{version:1,status:'notice',text:'🎬 '+r.title+'\\n'+(r.missing?'Search started.':'Already imported in Radarr.'),title:r.title,mediaType:r.mediaType,mediaId:r.mediaId,source:r.source,userId:r.userId,requestKey:t.requestKey,searchStarted:r.missing===true,repeatRequest:!!$('Existing Movie').first().json.id,query:''}}];"
    nodes['TV Result']['parameters']['jsCode']="const r=$('Selected Episode Snapshot').first().json,t=$('Register TV Before Search').first().json;return [{json:{version:1,status:'notice',text:'📺 '+r.title+'\\n'+(r.missingIds.length?'Search started.':'Selected episodes are tracked in Sonarr.'),title:r.title,mediaType:r.mediaType,mediaId:r.mediaId,source:r.source,userId:r.userId,requestKey:t.requestKey,searchStarted:r.missingIds.length>0,repeatRequest:!!$('Existing Series').first().json.id,query:''}}];"
    wrapper=by['snakeCommitMediaV1'];names={n['name'] for n in wrapper['nodes']}
    def edge(name):return {'node':name,'type':'main','index':0}
    if 'Inspect Commit Result?' not in names:
        condition={'conditions':{'options':{'typeValidation':'strict','version':3},'conditions':[{'id':'inspect-result','leftValue':"={{ $json.busy!==true && $json.status==='notice' && ['movie','tv'].includes($json.mediaType) && !!$json.requestKey && ['discord','telegram'].includes($json.source) && /^[1-9][0-9]{0,19}$/.test($json.userId) }}",'operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}}
        def node(name,kind,params,pos,version=2):return {'id':str(uuid.uuid5(uuid.NAMESPACE_URL,'snake-request-entry/'+name)),'name':name,'type':'n8n-nodes-base.'+kind,'typeVersion':version,'position':pos,'parameters':params}
        inspect=node('Inspect Commit Result?','if',condition,[720,0],2.2)
        read=node('Read Accepted Request Status','executeWorkflow',{'workflowId':{'__rl':True,'mode':'id','value':'snakeStatusV1'},'workflowInputs':{'mappingMode':'passThrough'},'mode':'once','options':{'waitForSubWorkflow':True}},[960,-100],1.3);read['onError']='continueRegularOutput'
        render=node('Format Accepted Request','code',{'jsCode':''},[1200,-100])
        passthrough=node('Return Uninspected Commit','code',{'jsCode':'return [{json:$json}];'},[960,140])
        wrapper['nodes'].extend([inspect,read,render,passthrough])
        wrapper['connections']['Coordinate Commit']={'main':[[edge(inspect['name'])]]}
        wrapper['connections'][inspect['name']]={'main':[[edge(read['name'])],[edge(passthrough['name'])]]}
        wrapper['connections'][read['name']]={'main':[[edge(render['name'])]]}
    render=next(n for n in wrapper['nodes'] if n['name']=='Format Accepted Request')
    render['parameters']['jsCode']=(ROOT/'n8n/request-entry/policy.js').read_text(encoding='utf-8').rstrip()+"\nreturn [{json:accepted($('Coordinate Commit').first().json,$json)}];"
    return rows
if __name__=='__main__':
    import sys
    source=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'));out=build(source)
    changed=[w for w,old in zip(out,source) if w!=old]
    for w in changed:
        for k in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived']:w.pop(k,None)
        w.update(active=False,pinData={})
    p=Path(sys.argv[2]);p.write_text(json.dumps(changed,indent=2),encoding='utf-8');p.chmod(0o600)
    print('Scoped request entry updates:',len(changed))
