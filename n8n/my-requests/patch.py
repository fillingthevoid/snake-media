"""Add My requests navigation using existing native request/pending tables."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('recommend_helpers',ROOT/'n8n/recommendations/patch.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
POLICY=(Path(__file__).parent/'policy.js').read_text(encoding='utf-8')
CHANGED_IDS=('snakeMyRequestsV1','snakeStatusV1','snakeRetentionChangePreviewV1','snakeConfirmMediaV1','HXtTzVTrpNZMZVt3','0e67KTcphqxEKNsh','snakeTelegramCardV1')


def code(name,body):
    return h.node(name,'code',{'jsCode':POLICY+'\n'+body})


def build(source):
    rows=copy.deepcopy(source);by={w['id']:w for w in rows}
    if 'snakeMyRequestsV1' in by:
        return rows
    def nodes(wid):return {n['name']:n for n in by[wid]['nodes']}
    pending=nodes('snakeRecommendV1')['Store Recommendation Menu']['parameters']['dataTableId']['value']
    requests=nodes('snakeStatusV1')['Read Status Requests']['parameters']['dataTableId']['value']
    cols=list(nodes('snakeRecommendV1')['Store Recommendation Menu']['parameters']['columns']['value'])
    values={key:'={{ $json.record.'+key+' }}' for key in cols}
    w={'id':'snakeMyRequestsV1','name':'Snake Media - My Requests','active':False,'nodes':[],
       'connections':{},'settings':{'executionOrder':'v1','executionTimeout':120}}
    w['nodes']=[
      h.node('My Requests Input','executeWorkflowTrigger',{'inputSource':'passthrough'},typeVersion=1.1),
      h.condition('My Requests Action?','typeof $json.action==="string"'),
      code('My Requests Key',"const a=$json;return [{json:{...a,requestKey:['myrequests',a.source,a.destinationId,a.messageId].join(':')}}];"),
      h.table('Find Request Menu',pending,filters=[h.eq(k,'={{ $json.'+k+' }}') for k in ['requestKey','source','userId','destinationId']]),
      code('Resolve Request Menu',"const rows=$input.all().map(x=>x.json).filter(x=>x.id);return [{json:rows.length?{reuse:true,row:rows.length===1?rows[0]:{version:1,status:'notice',text:'This menu could not be opened. Use /status again.'}}:{reuse:false}}];"),
      h.condition('Request Menu Exists?','$json.reuse===true'),
      code('Existing Request Menu','return [{json:card($json.row,Date.now())}];'),
      h.table('Read My Requests',requests,filters=[h.eq('source',"={{ $('My Requests Input').first().json.source }}"),h.eq('userId',"={{ $('My Requests Input').first().json.userId }}"),h.eq('state','registered')]),
      code('Create Request Menu',"return [{json:{record:create($('My Requests Input').first().json,$input.all().map(x=>x.json),Date.now())}}];"),
      h.condition('Request Menu Empty?','$json.record.version===1'),
      code('No Request Titles','return [{json:$json.record}];'),
      h.table('Store Request Menu',pending,'insert',values=values),
      code('Render Request Menu','return [{json:card($json,Date.now())}];'),
      h.table('Find Request Selection',pending,filters=[h.eq('id','={{ Number($json.pendingId) }}')]+[h.eq(k,'={{ $json.'+k+' }}') for k in ['source','userId','destinationId']]),
      code('Plan Request Selection',"try{const rs=$input.all().map(x=>x.json).filter(x=>x.id);if(rs.length!==1)throw Error('Not owned');const old=rs[0];return [{json:{valid:true,old,...advance(old,$('My Requests Input').first().json,Date.now(),String($execution.id))}}];}catch{return [{json:{valid:false,version:1,status:'notice',text:'This menu expired, was already selected or belongs to another account. Use /status again.'}}];}"),
      h.condition('Request Selection Valid?','$json.valid===true'),
      h.table('Claim Request Selection',pending,'update',[h.eq(k,'={{ $json.old.'+k+' }}') for k in ['id','state','claimId','source','userId','destinationId']],{key:'={{ $json.record.'+key+' }}' for key in ['state','claimId','contextJson','expiresAt']}),
      code('Verify Request Claim',"const row=$json,plan=$('Plan Request Selection').first().json;if(row.claimId!==String($execution.id))return [{json:{claimed:false,version:1,status:'notice',text:'This choice was already handled. Use the latest response.'}}];return [{json:{claimed:true,row,statusActor:plan.statusActor,changeActor:plan.changeActor,preference:plan.preference}}];"),
      h.condition('Request Selection Claimed?','$json.claimed===true'),
      code('Request Selection Declined','return [{json:$json}];'),
      h.condition('Request Watch Choice?','$json.preference!==null'),
      code('Prepare Watch Setting','return [{json:{record:$json.preference}}];'),
      h.table('Save Watch Setting',pending,'upsert',[h.eq(k,'={{ $json.record.'+k+' }}') for k in ['requestKey','source','userId','state']],values),
      code('Restore Request After Setting',"const p=$('Verify Request Claim').first().json;if($json.claimId!==String($execution.id))throw Error('Watch setting was not saved');return [{json:p}];"),
      h.condition('Request Expiry Action?','$json.changeActor!==null'),
      code('Prepare Request Expiry','return [{json:$json.changeActor}];'),
      h.call('Preview Request Expiry','snakeRetentionChangePreviewV1'),
      code('Accept Request Expiry','return [{json:{...$json,actionAccepted:true}}];'),
      h.condition('Request Status Needed?','$json.statusActor!==null'),
      code('Prepare Exact Request Status','return [{json:$json.statusActor}];'),
      h.call('Read Exact Request Status','snakeStatusV1'),
      code('Render Selected Request',"const p=$('Verify Request Claim').first().json;const r=card(p.row,Date.now(),$json);if(p.preference)r.text+='\\n✅ Watch address saved: '+JSON.parse(p.preference.contextJson).watchPreference+'.';return [{json:{...r,actionAccepted:true}}];"),
      code('Render Changed Request Menu','return [{json:{...card($json.row,Date.now()),actionAccepted:true}}];'),
    ]
    query=next(n for n in w['nodes'] if n['name']=='Read My Requests')
    query['parameters'].update(limit=200,orderBy=True,orderByColumn='requestedAt',orderByDirection='DESC')
    routes=[('My Requests Input','My Requests Action?',0),('My Requests Action?','Find Request Selection',0),('My Requests Action?','My Requests Key',1),
      ('My Requests Key','Find Request Menu',0),('Find Request Menu','Resolve Request Menu',0),('Resolve Request Menu','Request Menu Exists?',0),
      ('Request Menu Exists?','Existing Request Menu',0),('Request Menu Exists?','Read My Requests',1),('Read My Requests','Create Request Menu',0),
      ('Create Request Menu','Request Menu Empty?',0),('Request Menu Empty?','No Request Titles',0),('Request Menu Empty?','Store Request Menu',1),('Store Request Menu','Render Request Menu',0),
      ('Find Request Selection','Plan Request Selection',0),('Plan Request Selection','Request Selection Valid?',0),('Request Selection Valid?','Claim Request Selection',0),('Request Selection Valid?','Request Selection Declined',1),
      ('Claim Request Selection','Verify Request Claim',0),('Verify Request Claim','Request Selection Claimed?',0),('Request Selection Claimed?','Request Watch Choice?',0),('Request Selection Claimed?','Request Selection Declined',1),
      ('Request Watch Choice?','Prepare Watch Setting',0),('Prepare Watch Setting','Save Watch Setting',0),('Save Watch Setting','Restore Request After Setting',0),('Restore Request After Setting','Request Expiry Action?',0),('Request Watch Choice?','Request Expiry Action?',1),
      ('Request Expiry Action?','Prepare Request Expiry',0),('Prepare Request Expiry','Preview Request Expiry',0),('Preview Request Expiry','Accept Request Expiry',0),('Request Expiry Action?','Request Status Needed?',1),
      ('Request Status Needed?','Prepare Exact Request Status',0),('Prepare Exact Request Status','Read Exact Request Status',0),('Read Exact Request Status','Render Selected Request',0),('Request Status Needed?','Render Changed Request Menu',1)]
    for a,b,port in routes:h.connect(w,a,b,port)
    for i,n in enumerate(w['nodes']):n['position']=[i%6*260,i//6*220]
    rows.append(w)
    # Preserve current status projection, including permanent amendments and
    # shared queues. Only narrow selection when the caller supplies exact IDs.
    select=nodes('snakeStatusV1')['Select Status Requests']['parameters']
    anchor='select($input.all().map(x=>x.json),a)'
    if anchor not in select['jsCode']:raise ValueError('Unknown status selection')
    select['jsCode']=select['jsCode'].replace(anchor,"select($input.all().map(x=>x.json).filter(r=>!a.mediaId||(r.mediaType===a.mediaType&&String(r.mediaId)===a.mediaId)),a)")
    retention=(ROOT/'n8n/retention-controls/policy.js').read_text(encoding='utf-8')
    marker="if(typeof module!=='undefined')module.exports={parseChange,prepareChange,planChange,changeCard,guideAction,titleKey};"
    for name in ['Prepare Retention Change','Render Change Preview']:
        n=nodes('snakeRetentionChangePreviewV1')[name]['parameters'];body=n['jsCode']
        if body.count(marker)!=1:raise ValueError('Unknown retention policy')
        n['jsCode']=retention.rstrip()+'\n'+body.split(marker)[1].lstrip('\n')
    confirm=nodes('snakeConfirmMediaV1')['Validate Action']['parameters']
    anchor="if(JSON.parse($input.first().json.contextJson||'{}').recommendation)"
    if anchor not in confirm['jsCode']:raise ValueError('Unknown confirmation guard')
    confirm['jsCode']=confirm['jsCode'].replace(anchor,"if(JSON.parse($input.first().json.contextJson||'{}').recommendation||JSON.parse($input.first().json.contextJson||'{}').myRequests)")
    for wid,source in [('HXtTzVTrpNZMZVt3','discord'),('0e67KTcphqxEKNsh','telegram')]:
        platform=by[wid];prep='Validate Discord Request' if source=='discord' else 'Prepare Request';dest='channelId' if source=='discord' else 'chatId'
        platform['nodes'] += [h.condition('My Requests Command?',"/^\\/?status(?:@[A-Za-z0-9_]+)?$/i.test($('"+prep+"').first().json.text.trim())"),
          code('Prepare My Requests Actor',"const p=$('"+prep+"').first().json;return [{json:{source:'"+source+"',userId:String(p.userId),destinationId:String(p."+dest+"),messageId:p.messageId,requestedAt:p.requestedAt}}];"),
          h.condition('My Requests Callback?',"/^(?:mr_(?:title_[0-9]{1,3}|page_[0-9]{1,2}|refresh|extend|keep|back|close|watch)|wp_(?:local|tailscale|both))$/.test($json.action)"),h.call('Read My Requests Menu','snakeMyRequestsV1')]
        old=platform['connections']['Recommendation Command?']['main'][1][0]['node']
        h.connect(platform,'Recommendation Command?','My Requests Command?',1);h.connect(platform,'My Requests Command?','Prepare My Requests Actor');h.connect(platform,'My Requests Command?',old,1)
        h.connect(platform,'Prepare My Requests Actor','Read My Requests Menu')
        old=platform['connections']['Recommendation Callback?']['main'][1][0]['node']
        h.connect(platform,'Recommendation Callback?','My Requests Callback?',1);h.connect(platform,'My Requests Callback?','Read My Requests Menu');h.connect(platform,'My Requests Callback?',old,1)
        h.connect(platform,'Read My Requests Menu','Present Media Feedback' if source=='discord' else 'Preserve Telegram Reply')
    gate=nodes('snakeTelegramCardV1')['Recommendation Card?']['parameters']['conditions']['conditions'][0]
    gate['leftValue']=gate['leftValue'].replace('/^rec_/','/^(rec_|mr_)/')
    return rows


if __name__=='__main__':
    import sys
    Path(sys.argv[2]).write_text(json.dumps(build(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))),indent=2)+'\n',encoding='utf-8')
