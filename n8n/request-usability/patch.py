"""Targeted usability overlay; preserve credentials, endpoints and service writes."""
import copy,json,re,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def policy(path):
    text=(ROOT/path).read_text(encoding='utf-8').strip()
    evidence=(ROOT/'n8n/request-usability/evidence.js').read_text(encoding='utf-8').split("if(typeof module!=='undefined')module.exports=")[0]
    return text.replace("require('../request-usability/evidence.js')",'(()=>{'+evidence+'\nreturn {scopedFiles,category,expiryPreview};})()')

def embed(code,start,markers,replacement):
    marker=next((m for m in markers if m in code),None)
    if not marker or code.count(marker)!=1:raise ValueError('Unknown policy boundary: '+start)
    begin=code.index(start)
    end=code.index(marker)+len(marker)
    return code[:begin]+replacement+'\n'+code[end:].lstrip('\n')

def build(source):
    rows=copy.deepcopy(source);by={w['id']:w for w in rows}
    maintained={w['id'] for w in json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))}
    def nodes(wid):return {n['name']:n for n in by[wid]['nodes']}
    def edge(wid,a,b):by[wid]['connections'][a]={'main':[[{'node':b,'type':'main','index':0}]]}
    policies=[('n8n/my-requests/policy.js','// Owned request navigation.',["if(typeof module!=='undefined')module.exports={MY_ACTION,create,advance,card};"]),
        ('n8n/retention-controls/policy.js','// Confirmation and immutable retention amendments.',["if(typeof module!=='undefined')module.exports={parseChange,prepareChange,planChange,changeCard,guideAction,titleKey};"]),
        ('n8n/request-simplification/policy.js','function validChoice(row,choice)',["if(typeof module!=='undefined')module.exports={transition,selectedChoice,card};","if(typeof module!=='undefined')module.exports={transition,selectedChoice,card,revise};"]),
        ('n8n/recommendations/policy.js','// Personalized recommendation decisions.',["if(typeof module!=='undefined')module.exports={GENRES,RECACTION,history,suggestions,verified,providerItem,librarySearchTitle,availability,record,transition,generation,completed,card};"])]
    for w in rows:
        if w['id'] not in maintained:continue
        for n in w['nodes']:
            p=n.get('parameters',{});body=p.get('jsCode','')
            for path,start,markers in policies:
                if any(m in body for m in markers):body=embed(body,start,markers,policy(path))
            if body:p['jsCode']=body
            if n['name'] in ['Recommendation Callback?','My Requests Callback?']:
                c=p['conditions']['conditions'][0]
                c['leftValue']=c['leftValue'].replace('|change|more)', '|change|more|back)').replace('page_[0-9]{1,2}|refresh|','page_[0-9]{1,2}|filter_(?:all|downloading|ready|expiring)|refresh|')
    preview=nodes('snakePreviewMediaV1')['Select Preview']['parameters']
    start="const i=$('Preview Input').first().json"
    if start not in preview['jsCode']:raise ValueError('Unknown preview selection')
    preview['jsCode']=preview['jsCode'][:preview['jsCode'].index(start)]+"""
const i=$('Preview Input').first().json,field=i.mediaType==='movie'?'tmdbId':'tvdbId',seen=new Set();
const items=$input.all().map(x=>x.json).filter(m=>Number.isSafeInteger(m[field])&&m[field]>0&&typeof m.title==='string'&&m.title.trim()&&(!i.year||m.year===i.year)&&(!i.expectedExternalId||String(m[field])===i.expectedExternalId)&&!seen.has(m[field])&&seen.add(m[field])).slice(0,8);
const m=items[0];if(!m)return [{json:{version:1,status:'notice',text:'No matching title found. Try a more specific title or year.',menuChoices:[{label:'Try another search',action:'request'},{label:'Get recommendations',action:'recommend'}]}}];
let retentionPolicy;try{retentionPolicy=parseRetention(i.context.text,i.mediaType);}catch{return [{json:{version:1,status:'notice',text:'Please specify one retention choice: keep for 14 days, or keep permanently. Use a whole number from 1 to 3650 days.'}}];}
const c={...i.context,retentionPolicy,titleMatches:{active:false,items}};
return [{json:{source:c.source,userId:c.userId,destinationId:c.destinationId,requestKey:[c.source,c.destinationId,c.messageId].join(':'),contextJson:JSON.stringify(c),mediaType:i.mediaType,mediaJson:JSON.stringify(m),state:i.mediaType==='tv'?'scope':'preview',claimId:'',choice:'',expiresAt:new Date(Date.now()+300000).toISOString()}}];
""".strip()
    cn=nodes('snakeConfirmMediaV1');p=cn['Validate Action']['parameters']
    p['jsCode']=p['jsCode'].replace("if(JSON.parse(row.contextJson||'{}').retentionGuide)","if(JSON.parse(row.contextJson||'{}').retentionGuide||(a.action==='retback'&&JSON.parse(row.contextJson||'{}').retentionChange))")
    anchor='return [{json:{row,state,choice:selectedChoice(row,a,state),claimId:String($execution.id)}}];'
    replacement="const revised=revise(row,a,state);return [{json:{row:{...row,contextJson:revised.contextJson,mediaJson:revised.mediaJson},state,choice:selectedChoice(row,a,state),claimId:String($execution.id)}}];"
    if anchor in p['jsCode']:p['jsCode']=p['jsCode'].replace(anchor,replacement)
    elif replacement not in p['jsCode']:raise ValueError('Unknown confirmation claim')
    cols=cn['Claim Choice']['parameters']['columns'];cols['value']['mediaJson']='={{ $json.row.mediaJson }}'
    if not any(s['id']=='mediaJson' for s in cols['schema']):cols['schema'].append({**copy.deepcopy(cols['schema'][0]),'id':'mediaJson','displayName':'mediaJson','type':'string'})
    # Native table reads are bounded; omitted/stale rows produce unknown status.
    status=nodes('snakeStatusV1');events=nodes('snakeCompletionScanV1')['Recent Download Events']
    def reader(wid,name,template,filters=()):
        ns=nodes(wid)
        if name in ns:return
        n=copy.deepcopy(template);n.update(id=str(uuid.uuid5(uuid.NAMESPACE_URL,'snake-usability/'+name)),name=name,position=[0,0],alwaysOutputData=True)
        n['parameters'].update(operation='get',returnAll=False,limit=3000,orderBy=True,orderByColumn='updatedAt',orderByDirection='DESC',matchType='allConditions',filters={'conditions':list(filters)})
        n['parameters'].pop('columns',None);by[wid]['nodes'].append(n)
    def once(wid,name):
        if name not in nodes(wid):by[wid]['nodes'].append({'id':str(uuid.uuid5(uuid.NAMESPACE_URL,'snake-usability/'+name)),'name':name,'type':'n8n-nodes-base.code','typeVersion':2,'parameters':{'jsCode':'return [{json:{}}];'},'position':[0,0]})
    reader('snakeMyRequestsV1','Read Menu Retention',status['Read Status Retention'])
    reader('snakeMyRequestsV1','Read Menu Download Events',events)
    reader('snakeMyRequestsV1','Read Menu Notices',status['Read Status Notices'],[{'keyName':'source','condition':'eq','keyValue':"={{ $('My Requests Input').first().json.source }}"}])
    for name in ['Menu Retention Input','Menu Events Input','Menu Notices Input']:once('snakeMyRequestsV1',name)
    for a,b in [('Read My Requests','Menu Retention Input'),('Menu Retention Input','Read Menu Retention'),('Read Menu Retention','Menu Events Input'),('Menu Events Input','Read Menu Download Events'),('Read Menu Download Events','Menu Notices Input'),('Menu Notices Input','Read Menu Notices'),('Read Menu Notices','Create Request Menu')]:edge('snakeMyRequestsV1',a,b)
    mp=nodes('snakeMyRequestsV1')['Create Request Menu']['parameters'];mark="if(typeof module!=='undefined')module.exports={MY_ACTION,create,advance,card};"
    mp['jsCode']=mp['jsCode'].split(mark)[0]+mark+"\nreturn [{json:{record:create($('My Requests Input').first().json,$('Read My Requests').all().map(x=>x.json),Date.now(),{records:$('Read Menu Retention').all().map(x=>x.json),events:$('Read Menu Download Events').all().map(x=>x.json),notices:$input.all().map(x=>x.json)})}}];"
    reader('snakeRetentionChangePreviewV1','Read Change Expiry Evidence',status['Read Status Retention'])
    once('snakeRetentionChangePreviewV1','Change Evidence Input');edge('snakeRetentionChangePreviewV1','Read Change Requests','Change Evidence Input');edge('snakeRetentionChangePreviewV1','Change Evidence Input','Read Change Expiry Evidence');edge('snakeRetentionChangePreviewV1','Read Change Expiry Evidence','Prepare Retention Change')
    rp=nodes('snakeRetentionChangePreviewV1')['Prepare Retention Change']['parameters'];rp['jsCode']=rp['jsCode'].replace('prepareChange(a,$input.all().map(x=>x.json))',"prepareChange(a,$('Read Change Requests').all().map(x=>x.json),$('Read Change Expiry Evidence').all().map(x=>x.json),Date.now())")
    # Existing dynamic native Telegram sender supports photos, links and cleanup.
    tg=nodes('snakeTelegramCardV1')
    tg['Shared Menu?']['parameters']['conditions']['conditions'][0]['leftValue']='={{ Array.isArray($json.menuChoices) && $json.menuChoices.length>0 && !$json.choices?.length }}'
    tg['Recommendation Card?']['parameters']['conditions']['conditions'][0]['leftValue']="={{ $json.choices?.some(c=>/^(rec_|mr_|match_|wrong$|back$|retback$|retdays_)/.test(c.action))===true }}"
    wrapper="""
const r=$json;let rows=(r.choices||[]).map(c=>({row:{buttons:[{text:c.label,additionalFields:{callback_data:'snake:'+r.pendingId+':'+c.action}}]}}));
if(r.choices?.some(c=>/^rec_genre_/.test(c.action))){const genres=r.choices.filter(c=>/^rec_genre_/.test(c.action));rows=[];for(let i=0;i<genres.length;i+=3)rows.push({row:{buttons:genres.slice(i,i+3).map(c=>({text:c.label,additionalFields:{callback_data:'snake:'+r.pendingId+':'+c.action}}))}});for(const c of r.choices.filter(c=>!/^rec_genre_/.test(c.action)))rows.push({row:{buttons:[{text:c.label,additionalFields:{callback_data:'snake:'+r.pendingId+':'+c.action}}]}});}
for(const c of r.menuChoices||[]){if(!['request','recommend','status','help'].includes(c.action))throw Error('Invalid menu action');rows.push({row:{buttons:[{text:c.label,additionalFields:{callback_data:'snake_menu:'+c.action}}]}});}
const links=[];if(r.localJellyfinUrl)links.push({text:r.jellyfinUrl?'Open locally':'Open in Jellyfin',additionalFields:{url:r.localJellyfinUrl}});if(r.jellyfinUrl)links.push({text:r.localJellyfinUrl?'Open via Tailscale':'Open in Jellyfin',additionalFields:{url:r.jellyfinUrl}});if(links.length)rows.unshift({row:{buttons:links}});
return [{json:{...r,keyboard:{rows}}}];
""".strip()
    marker=policies[3][2][0];body=tg['Recommendation Card Data']['parameters']['jsCode'];tg['Recommendation Card Data']['parameters']['jsCode']=body[:body.index(marker)+len(marker)]+'\n'+wrapper
    def labels(value):
        if isinstance(value,str):return value.replace('Extend 7 days','Extend by 7 days').replace('Extend 30 days','Extend by 30 days')
        if isinstance(value,list):return [labels(v) for v in value]
        if isinstance(value,dict):return {k:labels(v) for k,v in value.items()}
        return value
    for wid in ['snakeTelegramCardV1','0e67KTcphqxEKNsh']:
        for n in by[wid]['nodes']:n['parameters']=labels(n['parameters'])
    return rows

if __name__=='__main__':
    import sys
    Path(sys.argv[2]).write_text(json.dumps(build(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))),ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
