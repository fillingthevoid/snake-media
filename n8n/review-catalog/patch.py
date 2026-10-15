"""Owner-only review catalog service; preserves existing private bindings."""
import copy,importlib.util,json,re
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('catalog_helpers',ROOT/'n8n/recommendations/patch.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)


def build(source):
    rows=copy.deepcopy(source);by={w['id']:w for w in rows}
    review=by['snakeMediaReviewsV1'];rn={n['name']:n for n in review['nodes']}
    review_policy=(ROOT/'n8n/media-reviews/policy.js').read_text(encoding='utf-8').rstrip()
    for n in review['nodes']:
        p=n.get('parameters',{});code=p.get('jsCode','')
        header=review_policy.splitlines()[0]
        if header in code:
            start=code.index(header);mark=code.index("\nif(typeof module!=='undefined')module.exports=",start);end=code.index(';',mark)+1
            p['jsCode']=code[:start]+review_policy+code[end:]
    decision=rn['Review Decision']['parameters']['jsCode'].split('const result=reviewOperation(')[-1]
    users=re.search(r'users:(.*?),owners:',decision).group(1).replace('Read Review Authorization','Read Catalog Authorization')
    owners=re.search(r'owners:(\[[^\]]*\])',decision).group(1)
    channels=re.search(r'channels:(\[[^\]]*\])',decision).group(1)
    policy=(ROOT/'n8n/review-catalog/policy.js').read_text(encoding='utf-8').rstrip()
    auth=(ROOT/'n8n/polish/authorization.js').read_text(encoding='utf-8').rstrip()
    def code(name,body):return h.node(name,'code',{'jsCode':policy+'\n'+body})
    def clone(original,name):
        n=copy.deepcopy(original);n.update(name=name,id='catalog-'+name.lower().replace(' ','-'),position=[0,0],executeOnce=True);return n
    def table(name,template):return clone(template,name)
    def http(original,name,url,query=None,paged=False):
        n=clone(original,name);n.update(alwaysOutputData=True,onError='continueRegularOutput');n.pop('continueOnFail',None)
        p=n['parameters']
        for key in ['sendBody','jsonBody','bodyParameters','specifyBody','sendQuery','queryParameters']:p.pop(key,None)
        p.update(method='GET',url=url,options={'timeout':5000})
        if query:p.update(sendQuery=True,queryParameters={'parameters':[{'name':k,'value':v} for k,v in query.items()]})
        if paged:p['options']['pagination']={'pagination':{'paginationMode':'updateAParameterInEachRequest','parameters':{'parameters':[{'type':'qs','name':'StartIndex','value':'={{ $pageCount * 200 }}'}]},'paginationCompleteWhen':'other','completeExpression':'={{ ($pageCount + 1) * 200 >= $response.body.TotalRecordCount }}','limitPagesFetched':True,'maxRequests':100}}
        return n
    webhook=clone(rn['Review Webhook'],'Catalog Webhook');webhook['webhookId']='snake-review-catalog-v1';webhook['parameters']['path']='snake-media-review-catalog'
    response=clone(rn['Review Response'],'Catalog Response')
    readrows=table('Read Catalog Rows',rn['Read Review Rows'])
    readauth=table('Read Catalog Authorization',rn['Read Review Authorization'])
    events=clone(next(n for n in by['snakeMyRequestsV1']['nodes'] if n['name']=='Read Menu Download Events'),'Read Catalog Import Events')
    events['parameters'].update(returnAll=False,limit=1000)
    deletions=clone(next(n for n in by['snakeMyRequestsV1']['nodes'] if n['name']=='Read Menu Retention'),'Read Catalog Deletions')
    deletions['parameters'].update(returnAll=False,limit=1000)
    prep=code('Prepare Catalog Request',auth+'\nconst p=prepareCatalog({body:$("Catalog Webhook").first().json.body,rows:$("Read Catalog Rows").all().map(x=>x.json),events:$("Read Catalog Import Events").all().map(x=>x.json),deletions:$input.all().map(x=>x.json),users:'+users+',owners:'+owners+',channels:'+channels+',now:Date.now(),claimId:String($execution.id)});return [{json:p}];')
    tableid=rn['Read Review Rows']['parameters']['dataTableId']['value']
    values={k:'={{ $json.row.'+k+' }}' for k in ['source','userId','destinationId','requestKey','contextJson','mediaType','mediaJson','state','claimId','choice','expiresAt']}
    insert=h.table('Initialize Catalog',tableid,'insert',values=values)
    claim=h.table('Claim Catalog Lease',tableid,'update',[h.eq(k,'={{ $json.old.'+k+' }}') for k in ['id','claimId','contextJson','expiresAt']],{k:'={{ $json.row.'+k+' }}' for k in ['claimId','expiresAt']})
    save=h.table('Save Catalog',tableid,'update',[h.eq('id','={{ $json.row.id }}'),h.eq('claimId',"={{ $('Prepare Catalog Request').first().json.claimId }}")],{k:'={{ $json.row.'+k+' }}' for k in ['contextJson','claimId','expiresAt']})
    def read_http(wid,name):return next(n for n in by[wid]['nodes'] if n['name']==name)
    jelly=read_http('snakeRetentionScanV1','Read Jellyfin Users');url=urlsplit(jelly['parameters']['url']);base=urlunsplit((url.scheme,url.netloc,'/Items','',''))
    common={'Recursive':'true','Fields':'Path,ProviderIds','Limit':'200','EnableImages':'false','EnableUserData':'false','CollapseBoxSetItems':'false','IsVirtualItem':'false'}
    movies=http(jelly,'Read Catalog Movies',base,{**common,'IncludeItemTypes':'Movie'},True)
    series=http(jelly,'Read Catalog Series',base,{**common,'IncludeItemTypes':'Series'},True)
    arrmovie=read_http('snakeCommitMediaBodyV2','Find Confirmed Movie');arrseries=read_http('snakeCommitMediaBodyV2','Find Confirmed Series')
    arrm=http(arrmovie,'Read Catalog Radarr',arrmovie['parameters']['url'])
    arrs=http(arrseries,'Read Catalog Sonarr',arrseries['parameters']['url'])
    healthsrc=read_http('snakeServerHealthV1','Read Private Host Health');health=http(healthsrc,'Read Catalog Storage Health',healthsrc['parameters']['url'])
    inv=code('Catalog Inventory',"const p=$('Prepare Catalog Request').first().json;const read=name=>$(name).all().map(x=>x.json).flatMap(x=>Array.isArray(x.body)?x.body:Array.isArray(x)?x:[x]).filter(x=>Object.keys(x).length);const inventory=catalogInventory({state:JSON.parse(p.old.contextJson),moviePages:read('Read Catalog Movies'),seriesPages:read('Read Catalog Series'),movies:read('Read Catalog Radarr'),series:read('Read Catalog Sonarr'),health:$json,now:Date.now()});return [{json:inventory}];")
    target=code('Catalog Episode Targets',"return $json.targets.map(t=>({json:t}));")
    episodes=http(jelly,'Read Catalog Real Episode',base,{'Recursive':'true','IncludeItemTypes':'Episode','Fields':'Path','Limit':'1','IsVirtualItem':'false','ParentId':'={{ $json.jellyfinId }}','EnableImages':'false','EnableUserData':'false'})
    episodes['executeOnce']=False
    proofs=code('Catalog Episode Proofs',"const targets=$('Catalog Episode Targets').all().map(x=>x.json);const proofs=$input.all().map((x,i)=>{const t=targets[i],p=x.json.body||x.json,items=p.Items;const valid=t&&Array.isArray(items)&&items.length<=1&&Number.isSafeInteger(p.TotalRecordCount)&&p.TotalRecordCount>=0&&(p.TotalRecordCount===0?items.length===0:items.length===1);const available=valid&&items.some(e=>e.Type==='Episode'&&e.IsVirtualItem!==true&&(!e.SeriesId||e.SeriesId===t.jellyfinId)&&catalogPath(e.Path)?.startsWith(t.path+'/'));return {mediaKey:t?.mediaKey,ok:!!valid&&(!items.length||available),available:!!available};});return [{json:{proofs}}];")
    finish=code('Finish Catalog',"const plan=$('Prepare Catalog Request').first().json;let inventory=null;if(plan.needsSync)inventory=$('Catalog Inventory').first().json;return [{json:finishCatalog({plan,inventory,proofs:$json.proofs||[],now:Date.now()})}];")
    saved=code('Catalog Saved',"const expected=$('Finish Catalog').first().json;if($json.contextJson!==expected.row.contextJson||$json.claimId!=='')throw Error('Catalog write not confirmed');return [{json:expected.reply}];")
    w={'id':'snakeReviewCatalogV1','name':'Snake Media - Review Library Catalog','active':False,'pinData':{},'settings':{'executionOrder':'v1','executionTimeout':300,'saveDataSuccessExecution':'none','saveDataErrorExecution':'none'},'nodes':[
        webhook,readauth,readrows,events,deletions,prep,h.condition('Catalog Initialize?','$json.mode==="insert"'),insert,
        code('Catalog Initialized',"const p=$('Prepare Catalog Request').first().json;if($json.contextJson!==p.row.contextJson)throw Error('Catalog initialization not confirmed');return [{json:p.reply}];"),
        h.condition('Catalog Claim?','$json.mode==="claim"'),code('Catalog Read Result',"return [{json:$('Prepare Catalog Request').first().json.reply}];"),claim,
        code('Verify Catalog Lease',"const p=$('Prepare Catalog Request').first().json;return [{json:{owned:$json.claimId===p.claimId,plan:p}}];"),h.condition('Catalog Lease Owned?','$json.owned===true'),
        code('Catalog Busy',"return [{json:{version:1,ok:true,busy:true,jobs:[]}}];"),h.condition('Catalog Sync Needed?','$json.plan.needsSync===true'),movies,series,arrm,arrs,health,inv,
        h.condition('Catalog Episodes Needed?','$json.complete===true&&$json.targets.length>0'),target,episodes,proofs,code('Catalog No Episode Proofs','return [{json:{proofs:[]}}];'),finish,save,saved,response], 'connections':{}}
    edges=[('Catalog Webhook','Read Catalog Authorization',0),('Read Catalog Authorization','Read Catalog Rows',0),('Read Catalog Rows','Read Catalog Import Events',0),('Read Catalog Import Events','Prepare Catalog Request',0),('Prepare Catalog Request','Catalog Initialize?',0),('Catalog Initialize?','Initialize Catalog',0),('Initialize Catalog','Catalog Initialized',0),('Catalog Initialized','Catalog Response',0),('Catalog Initialize?','Catalog Claim?',1),('Catalog Claim?','Claim Catalog Lease',0),('Catalog Claim?','Catalog Read Result',1),('Catalog Read Result','Catalog Response',0),('Claim Catalog Lease','Verify Catalog Lease',0),('Verify Catalog Lease','Catalog Lease Owned?',0),('Catalog Lease Owned?','Catalog Sync Needed?',0),('Catalog Lease Owned?','Catalog Busy',1),('Catalog Busy','Catalog Response',0),('Catalog Sync Needed?','Read Catalog Movies',0),('Catalog Sync Needed?','Catalog No Episode Proofs',1),('Read Catalog Movies','Read Catalog Series',0),('Read Catalog Series','Read Catalog Radarr',0),('Read Catalog Radarr','Read Catalog Sonarr',0),('Read Catalog Sonarr','Read Catalog Storage Health',0),('Read Catalog Storage Health','Catalog Inventory',0),('Catalog Inventory','Catalog Episodes Needed?',0),('Catalog Episodes Needed?','Catalog Episode Targets',0),('Catalog Episodes Needed?','Catalog No Episode Proofs',1),('Catalog Episode Targets','Read Catalog Real Episode',0),('Read Catalog Real Episode','Catalog Episode Proofs',0),('Catalog Episode Proofs','Finish Catalog',0),('Catalog No Episode Proofs','Finish Catalog',0),('Finish Catalog','Save Catalog',0),('Save Catalog','Catalog Saved',0),('Catalog Saved','Catalog Response',0)]
    edges=[edge for edge in edges if edge[:2]!=('Read Catalog Import Events','Prepare Catalog Request')]
    edges.extend([('Read Catalog Import Events','Read Catalog Deletions',0),('Read Catalog Deletions','Prepare Catalog Request',0)])
    for a,b,port in edges:h.connect(w,a,b,port)
    for i,n in enumerate(w['nodes']):n['position']=[i%6*280,i//6*220]
    rows=[item for item in rows if item['id']!=w['id']]
    index=next((i for i,item in enumerate(rows) if item['id']=='snakeStatusReviewCardV1'),len(rows))
    rows.insert(index,w)
    return rows


if __name__=='__main__':
    import sys
    original=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'));rows=build(original);old={w['id']:w for w in original};changed=[w for w in rows if w!=old.get(w['id'])]
    for w in changed:
        for k in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived']:w.pop(k,None)
        w.update(active=False,pinData={})
    target=Path(sys.argv[2]);target.write_text(json.dumps(changed,indent=2)+'\n',encoding='utf-8');target.chmod(0o600)
    print('Scoped review catalog workflows:',len(changed))
