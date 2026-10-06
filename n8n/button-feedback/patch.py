"""Scoped callback-feedback overlay; preserves live credentials and policy."""
import copy

CHANGED_IDS=('snakeNoticeRetentionPreviewV1','snakeRetentionChangeApplyV1',
             'snakeConfirmMediaV1','0e67KTcphqxEKNsh')

def patch_workflows(workflows):
    result=copy.deepcopy(workflows)
    by_id={w['id']:w for w in result}
    def node(wid,name):return next(n for n in by_id[wid]['nodes'] if n['name']==name)
    node(CHANGED_IDS[0],'Notice Result')['parameters']['jsCode']="""const r=$json,owner=$('Resolve Notice Owner').first().json;
if(!owner.version&&r.status==='confirmation'&&r.pendingId&&Array.isArray(r.choices))return [{json:{...r,actionAccepted:true,text:'✅ Selected. Confirm below to save this expiry choice.\\n\\n'+r.text}}];
return [{json:r}];"""
    node(CHANGED_IDS[1],'Retention Change Result')['parameters']['jsCode']="""const p=$('Plan Retention Amendment').first().json;if(p.version)return [{json:p}];
const e=JSON.parse(p.payloadJson),dates=e.files.map(f=>Date.parse(f.minimumExpiry));
const date=n=>new Intl.DateTimeFormat('en-US',{timeZone:'America/Los_Angeles',month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(n);
const text=e.operation==='permanent'?'✅ '+e.title+'\\nKept permanently. Your requests and future subscribed episodes will not expire.':
'✅ '+e.title+'\\nExpiry extended for '+e.files.length+' imported '+(e.files.length===1?'file':'files')+'.\\nEarliest new expiry: '+date(Math.min(...dates))+'.\\nUpcoming episodes keep their existing retention.';
return [{json:{version:1,status:'notice',text,retentionUpdated:true}}];"""
    validate=node(CHANGED_IDS[2],'Validate Action')['parameters']
    old="Number.isFinite(Date.parse(row.expiresAt))&&Date.parse(row.expiresAt)<=Date.now()"
    new="(row?.state==='done'||row?.state==='cancelled'||(row?.state!=='processing'&&Number.isFinite(Date.parse(row.expiresAt))&&Date.parse(row.expiresAt)<=Date.now()))"
    if new not in validate['jsCode']:
        assert old in validate['jsCode'],'Unknown stale-control guard'
        validate['jsCode']=validate['jsCode'].replace(old,new)
    gate=node(CHANGED_IDS[3],'Owned Text Card Cleanup?')
    gate['parameters']['conditions']['conditions'][0]['leftValue']="={{ $json.busy!==true && ($json.actionAccepted===true || $json.clearControls===true) && !!($('On message').first().json.callback_query?.message?.message_id) }}"
    clear=node(CHANGED_IDS[3],'Clear Telegram Text Controls')
    clear.update(type='CUSTOM.snakeTelegramControls',typeVersion=1,onError='continueRegularOutput')
    clear['parameters']={'message':"={{ $('On message').first().json.callback_query.message }}"}
    return result
