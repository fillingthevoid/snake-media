"""Overlay retention controls onto a current export; do not regenerate old routes."""
import copy,json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).parent
# Reuse the status generator's definitions only, without executing its generation.
exec(compile((ROOT.parent/'status/build.py').read_text(encoding='utf-8-sig').split('status=wf(')[0],str(ROOT.parent/'status/build.py'),'exec'),globals())
R=ROOT;OUT=R/'workflows';OUT.mkdir(exist_ok=True)
if len(sys.argv)==1:
 for folder in ['retention/workflows','status/workflows']:
  for p in (R.parent/folder).glob('*.json'):
   w=json.loads(p.read_text(encoding='utf-8-sig'));S[w['id']]=w
P=(R/'policy.js').read_text(encoding='utf-8-sig')
RP=(R.parent/'retention/policy.js').read_text(encoding='utf-8-sig');ENGINE=(R.parent/'retention/engine.js').read_text(encoding='utf-8-sig')

def clone_node(w,name,new):
 n=copy.deepcopy(get(w,name));n.update(name=new,id=str(uuid.uuid5(uuid.NAMESPACE_URL,'snake-amend/'+new)));return n

def native(n,table,op,filters=None,values=None,schema=None):
 out=data(n,table);p=out['parameters'];p['operation']=op
 if op!='get':p.pop('returnAll',None)
 p['filters']={'conditions':filters or []}
 if values is not None:p['columns']={'mappingMode':'defineBelow','value':values,'schema':[{'id':k,'displayName':k,'type':(schema or {}).get(k,'string'),'display':True,'required':False,'defaultMatch':False,'canBeUsedToMatch':True} for k in values]}
 return out

def eq(k,v):return {'keyName':k,'condition':'eq','keyValue':v}
def strictcall(n,wid):
 n=call(n,wid);n.pop('onError',None);return n

pending_fields=['source','userId','destinationId','requestKey','contextJson','mediaType','mediaJson','state','claimId','choice','expiresAt']
preview=wf('snakeRetentionChangePreviewV1','Snake Media - Preview Retention Change',[
 trigger('Change Input'),data('Read Change Requests','snake_media_requests'),
 code('Prepare Retention Change',P+"\nconst a=$('Change Input').first().json;const result=prepareChange(a,$input.all().map(x=>x.json));if(result.notice)return [{json:{version:1,status:'notice',text:result.notice}}];const c=result.change;return [{json:{source:a.source,userId:a.userId,destinationId:a.destinationId,requestKey:'retention:'+a.source+':'+a.destinationId+':'+a.messageId,contextJson:JSON.stringify({...a,retentionChange:c}),mediaType:c.mediaType,mediaJson:JSON.stringify({title:c.title}),state:'preview',claimId:'',choice:'',expiresAt:new Date(Date.now()+30*60000).toISOString()}}];"),
 iff('Change Matches?',"!!$json.requestKey"),
 native('Find Change Preview','snake_media_pending','get',[eq('requestKey','={{ $json.requestKey }}')]),
 code('Resolve Change Preview',"const rows=$input.all().filter(x=>x.json.id);if(rows.length>1)throw Error('Duplicate pending change');return [{json:{existing:rows.length===1,record:rows[0]?.json||$('Prepare Retention Change').first().json}}];"),
 iff('Reuse Change Preview?',"$json.existing"),code('Existing Change Card','return [{json:$json.record}];'),
 native('Store Change Preview','snake_media_pending','insert',values={k:'={{ $json.record.'+k+' }}' for k in pending_fields},schema={'expiresAt':'date'}),
 code('Render Change Preview',P+'\nreturn [{json:changeCard($json)}];')])
chain(preview,'Change Input','Read Change Requests','Prepare Retention Change','Change Matches?','Find Change Preview','Resolve Change Preview','Reuse Change Preview?','Existing Change Card','Render Change Preview')
edge(preview,'Change Matches?','Render Change Preview',1);edge(preview,'Reuse Change Preview?','Store Change Preview',1);edge(preview,'Store Change Preview','Render Change Preview');save(preview)

# Reuse the proven scanner with preview mode forced and one title selected.
scan=copy.deepcopy(S['snakeRetentionScanV1']);scan.update(id='snakeRetentionChangeSnapshotV1',name='Snake Media - Snapshot Retention Change')
get(scan,'Validate Scan Mode')['parameters']['jsCode']="return [{json:{mode:'preview'}}];"
group=get(scan,'Group Retention Requests')['parameters']['jsCode']
needle="r.state==='registered'"
assert needle in group
group=group.replace(needle,needle+"&&r.mediaType===$('Scan Input').first().json.mediaType&&String(r.mediaId)===String($('Scan Input').first().json.mediaId)")
get(scan,'Group Retention Requests')['parameters']['jsCode']=group;save(scan)

apply=wf('snakeRetentionChangeApplyV1','Snake Media - Apply Retention Change',[
 trigger('Amend Input'),native('Read Claimed Change','snake_media_pending','get',[eq('id',"={{ Number($('Amend Input').first().json.id) }}")]),
 code('Validate Claimed Change',"const i=$('Amend Input').first().json;const r=$json;if(!i.owner||r.state!=='processing'||r.claimId!==i.claimId)throw Error('Unclaimed retention change');const c=JSON.parse(r.contextJson).retentionChange;if(!c||c.source!==r.source||c.userId!==r.userId)throw Error('Invalid retention owner');return [{json:{...r,owner:i.owner,change:c,mediaId:c.mediaId,mediaType:c.mediaType}}];"),
 strictcall('Fresh Change Snapshot',scan['id']),data('Read Amend Requests','snake_media_requests'),code('One Amend Record Read','return [{json:{}}];'),data('Read Amend Records','snake_media_retention_records'),
 code('Plan Retention Amendment',P+"\nconst i=$('Validate Claimed Change').first().json;const records=$input.all().map(x=>x.json).filter(x=>x.key);const decisions=($('Fresh Change Snapshot').first().json.groups||[]).flatMap(g=>g.decisions||[]);const event=planChange(i.change,$('Read Amend Requests').all().map(x=>x.json),decisions,records,{pendingId:String(i.id),now:Date.now()});if(event.notice)return [{json:{version:1,status:'notice',text:event.notice}}];return [{json:{owner:i.owner,key:'change:'+i.id,kind:'amendment',payloadJson:JSON.stringify(event)}}];"),
 iff('Amendment Needed?',"!!$json.key"),strictcall('Store Retention Amendment','snakeRetentionStoreV1'),
 code('Refresh Changed Retention',"return [{json:$('Validate Claimed Change').first().json}];"),strictcall('Refresh Change Decisions',scan['id']),
 code('Retention Change Result',"const p=$('Plan Retention Amendment').first().json;if(p.version)return [{json:p}];const e=JSON.parse(p.payloadJson);const dates=e.files.map(f=>Date.parse(f.minimumExpiry));const date=n=>new Intl.DateTimeFormat('en-US',{timeZone:'America/Los_Angeles',month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(n);const text=e.operation==='permanent'?'🗃️ '+e.title+'\\nYour requests are now kept permanently, including future subscribed episodes.':'✅ '+e.title+'\\nExtended '+e.files.length+' imported '+(e.files.length===1?'file':'files')+'.\\nEarliest new minimum expiry: '+date(Math.min(...dates))+'.\\nUpcoming episodes keep their existing retention.';return [{json:{version:1,status:'notice',text}}];"),
 code('Save Retention Reply','return [{json:{reply:$json}}];'),
 native('Complete Retention Choice','snake_media_pending','update',[eq('id',"={{ $('Amend Input').first().json.id }}"),eq('claimId',"={{ $('Amend Input').first().json.claimId }}")],{'state':'done'}),
 code('Return Retention Reply',"if($json.state!=='done')throw Error('Pending completion failed');return [{json:$('Save Retention Reply').first().json.reply}];")])
chain(apply,*[n['name'] for n in apply['nodes']]);edge(apply,'Amendment Needed?','Retention Change Result',1);save(apply)

coord=copy.deepcopy(S['snakeRetentionCoordinatorV1']);coord['nodes'] += [iff('Retention Change Job?',"$json.job==='amend'"),strictcall('Run Locked Retention Change',apply['id'])]
edge(coord,'Commit Job?','Retention Change Job?',1);chain(coord,'Retention Change Job?','Run Locked Retention Change','Save Locked Result');edge(coord,'Retention Change Job?','Run Locked Scan',1);save(coord)

confirm=copy.deepcopy(S['snakeConfirmMediaV1'])
validate=get(confirm,'Validate Action')['parameters']['jsCode'];assert 'transition(row,a,Date.now())' in validate
get(confirm,'Validate Action')['parameters']['jsCode']=validate.replace('transition(row,a,Date.now())',"transition(JSON.parse(row.contextJson||'{}').retentionChange?{...row,mediaType:'movie'}:row,a,Date.now())")
render=get(confirm,'Render Choice')['parameters']['jsCode'];get(confirm,'Render Choice')['parameters']['jsCode']=P+"\nif(!$json.version&&JSON.parse($json.contextJson||'{}').retentionChange)return [{json:changeCard($json)}];\n"+render
confirm['nodes'] += [iff('Retention Choice?',"!!JSON.parse($json.contextJson||'{}').retentionChange"),code('Prepare Retention Job',"return [{json:{...$json,job:'amend'}}];"),strictcall('Apply Retention Choice',coord['id'])]
edge(confirm,'Run Confirmed Media?','Retention Choice?');chain(confirm,'Retention Choice?','Prepare Retention Job','Apply Retention Choice','Mark Accepted Action');edge(confirm,'Retention Choice?','Commit Confirmed Media',1);save(confirm)

worker=copy.deepcopy(S['snakeRetentionMediaV1']);old=get(worker,'Plan Retention')['parameters']['jsCode'];tail=old[old.index("\nconst i=$('Media Input')"):];get(worker,'Plan Retention')['parameters']['jsCode']=RP+'\n'+ENGINE+tail;save(worker)

status=copy.deepcopy(S['snakeStatusInspectV1']);sp=(R.parent/'status/policy.js').read_text(encoding='utf-8-sig');old=get(status,'Describe Status')['parameters']['jsCode'];tail=old[old.index('\nconst pages=$input.all()'):];get(status,'Describe Status')['parameters']['jsCode']=sp+tail;save(status)

for platform,wid,prep,output in [('Discord','HXtTzVTrpNZMZVt3','Validate Discord Request','Respond to Discord'),('Telegram','0e67KTcphqxEKNsh','Prepare Request','Format Interactive Reply')]:
 w=copy.deepcopy(S[wid]);assert not any(n['name']=='Retention Command?' for n in w['nodes'])
 w['nodes'] += [code('Parse Retention Command',P+"\nconst p=$('"+prep+"').first().json;return [{json:{...p,retentionCommand:parseChange(p.text)}}];"),iff('Retention Command?',"$json.retentionCommand!==null"),code('Prepare Retention Actor',"const p=$json;return [{json:{source:'"+platform.lower()+"',userId:String(p.userId),destinationId:String(p.channelId||p.chatId),messageId:String(p.messageId),text:p.text}}];"),call('Preview Retention Change',preview['id'])]
 edge(w,'Status Command?','Parse Retention Command',1);chain(w,'Parse Retention Command','Retention Command?','Prepare Retention Actor','Preview Retention Change',output);edge(w,'Retention Command?','Interpret Media Request',1);save(w)
print('Generated retention control overlay')
