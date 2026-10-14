"""Native review settings/votes endpoint; no changes to media authorization or jobs."""
import copy
import importlib.util
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('review_helpers',ROOT/'n8n/recommendations/patch.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)

def build(source,env):
    out=copy.deepcopy(source);by={w['id']:w for w in out}
    discord=by['HXtTzVTrpNZMZVt3'];nodes={n['name']:n for n in discord['nodes']}
    pending=next(n for n in by['snakeRecommendV1']['nodes'] if n['name']=='Store Recommendation Menu')
    pending_id=pending['parameters']['dataTableId']['value']
    control_id=nodes['Read Discord Authorization']['parameters']['dataTableId']['value']
    requests_id=next(n for n in by['snakeStatusV1']['nodes'] if n['name']=='Read Status Requests')['parameters']['dataTableId']['value']
    notice_id=next(n for w in out for n in w['nodes'] if n['type'].endswith('.dataTable') and n['name']=='Reminder Notices')['parameters']['dataTableId']['value']
    def code(name,body):
        n=h.node(name,'code',{'jsCode':body});return n
    def read(name,table,filters=()):
        n=h.table(name,table,filters=filters);n['parameters'].pop('limit',None);n['parameters']['returnAll']=True;return n
    web=copy.deepcopy(nodes['Discord Webhook']);web.update(id='reviews-webhook',name='Review Webhook',webhookId='snake-media-reviews-v1')
    web['parameters']['path']='snake-media-reviews'
    response=copy.deepcopy(nodes['Respond to Discord']);response.update(id='reviews-response',name='Review Response')
    response['parameters']['responseBody']='={{ $json }}'
    policy=(ROOT/'n8n/media-reviews/policy.js').read_text(encoding='utf-8')
    auth=(ROOT/'n8n/polish/authorization.js').read_text(encoding='utf-8')
    ids=lambda key:[x.strip() for x in env[key].split(',') if x.strip()]
    user_expression='authorizationUsers($("Read Review Authorization").all().map(x=>x.json),'+json.dumps(ids('ALLOWED_DISCORD_USER_IDS'))+')'
    channels=json.dumps(ids('ALLOWED_DISCORD_CHANNEL_IDS'))
    selection=policy+'\n'+auth+'\nconst b=$("Review Webhook").first().json.body;const p=b&&'+user_expression+'.includes(b.userId)&&["resolve","open","vote"].includes(b.op)&&b.myRequestsId?reviewRequestSelection({body:b,menus:$("Read Owned Review Menu").all().map(x=>x.json),requests:$input.all().map(x=>x.json),channels:'+channels+'}):null;return [{json:{statusActor:p?.statusActor||null}}];'
    decision=policy+'\n'+auth+'\nconst result=reviewOperation({body:$("Review Webhook").first().json.body,rows:$("Read Review Rows").all().map(x=>x.json),notices:$("Read Review Notice").all().map(x=>x.json),requests:$("Read Review Request").all().map(x=>x.json).concat($("Read Owned Review Requests").all().map(x=>x.json)),menus:$("Read Owned Review Menu").all().map(x=>x.json),availability:$input.first().json.availability,users:'+user_expression+',owners:'+json.dumps(ids('ADMIN_DISCORD_USER_IDS'))+',channels:'+channels+'});return [{json:result}];'
    values={k:'={{ $json.row.'+k+' }}' for k in pending['parameters']['columns']['value']}
    # Existing pending schema owns these fields; nullable menu fields have explicit values.
    for k in ('action','resultJson'):
        if k in values:values[k]="={{ $json.row."+k+" || '' }}"
    for k in ('mediaType','claimId','choice'):
        if k in values:values[k]="={{ '' }}"
    if 'mediaJson' in values:values['mediaJson']="={{ '{}' }}"
    write=h.table('Save Review Row',pending_id,'upsert',[h.eq('source','discord'),h.eq('state','review'),h.eq('requestKey','={{ $json.row.requestKey }}')],values)
    verify=read('Verify Review Row',pending_id,[h.eq('source','discord'),h.eq('state','review'),h.eq('requestKey',"={{ $('Review Decision').first().json.row.requestKey }}")])
    w={'id':'snakeMediaReviewsV1','name':'Snake Media - Reviews','active':False,'pinData':{},'settings':{'executionOrder':'v1','executionTimeout':30},'nodes':[
        web,read('Read Review Authorization',control_id),
        read('Read Review Rows',pending_id,[h.eq('source','discord'),h.eq('state','review')]),
        read('Read Review Notice',notice_id,[h.eq('id',"={{ $('Review Webhook').first().json.body.noticeId || '0' }}")]),
        read('Read Review Request',requests_id,[h.eq('requestKey',"={{ $('Read Review Notice').first().json.requestKey || '__review_none__' }}")]),
        read('Read Owned Review Menu',pending_id,[h.eq('id',"={{ $('Review Webhook').first().json.body.myRequestsId || '0' }}"),h.eq('source','discord'),h.eq('userId',"={{ $('Review Webhook').first().json.body.userId || '__none__' }}"),h.eq('destinationId',"={{ $('Review Webhook').first().json.body.channelId || '__none__' }}"),h.eq('state','preview')]),
        read('Read Owned Review Requests',requests_id,[h.eq('source','discord'),h.eq('userId',"={{ $('Review Webhook').first().json.body.myRequestsId ? $('Review Webhook').first().json.body.userId : '__none__' }}")]),
        code('Prepare Review Availability',selection),h.condition('Review Availability Needed?',"!!$json.statusActor"),
        code('Review Availability Actor',"return [{json:$json.statusActor}];"),h.call('Read Review Availability','snakeStatusV1'),
        code('Review No Availability',"return [{json:{availability:null}}];"),
        code('Review Decision',decision),h.condition('Review Write?',"!!$json.row"),h.condition('Review Menu Write?',"$json.row.state==='preview'"),write,verify,
        code('Review Saved',"const d=$('Review Decision').first().json;const rows=$input.all().map(x=>x.json);if(rows.length!==1||rows[0].contextJson!==d.row.contextJson)throw Error('review_write_unconfirmed');return [{json:d.reply}];"),
        code('Review Read Result',"return [{json:$('Review Decision').first().json.reply}];"),response], 'connections':{}}
    w['nodes'] += [h.table('Renew Owned Review Menu',pending_id,'update',[
        h.eq('id','={{ $json.row.id }}'),h.eq('source','discord'),h.eq('userId','={{ $json.row.userId }}'),h.eq('destinationId','={{ $json.row.destinationId }}'),
        h.eq('state','preview'),h.eq('claimId',"={{ $json.menuOriginal.claimId || '' }}"),h.eq('expiresAt','={{ $json.menuOriginal.expiresAt }}')],{'expiresAt':'={{ $json.row.expiresAt }}'}),
        read('Verify Opened Review Menu',pending_id,[h.eq('id',"={{ $('Review Decision').first().json.row.id }}"),h.eq('source','discord'),h.eq('state','preview')]),
        code('Review Menu Saved',"const d=$('Review Decision').first().json;const rows=$input.all().map(x=>x.json);if(rows.length!==1||rows[0].contextJson!==d.row.contextJson||Date.parse(rows[0].expiresAt)!==Date.parse(d.row.expiresAt))throw Error('review_menu_renewal_unconfirmed');return [{json:d.reply}];")]
    initial=['Review Webhook','Read Review Authorization','Read Review Rows','Read Review Notice','Read Review Request','Read Owned Review Menu','Read Owned Review Requests','Prepare Review Availability','Review Availability Needed?']
    for a,b in zip(initial,initial[1:]):h.connect(w,a,b)
    h.connect(w,'Review Availability Needed?','Review Availability Actor');h.connect(w,'Review Availability Actor','Read Review Availability');h.connect(w,'Read Review Availability','Review Decision')
    h.connect(w,'Review Availability Needed?','Review No Availability',1);h.connect(w,'Review No Availability','Review Decision');h.connect(w,'Review Decision','Review Write?')
    h.connect(w,'Review Write?','Review Menu Write?');h.connect(w,'Review Menu Write?','Renew Owned Review Menu');h.connect(w,'Renew Owned Review Menu','Verify Opened Review Menu');h.connect(w,'Verify Opened Review Menu','Review Menu Saved');h.connect(w,'Review Menu Saved','Review Response')
    h.connect(w,'Review Menu Write?','Save Review Row',1);h.connect(w,'Save Review Row','Verify Review Row');h.connect(w,'Verify Review Row','Review Saved');h.connect(w,'Review Saved','Review Response')
    h.connect(w,'Review Write?','Review Read Result',1);h.connect(w,'Review Read Result','Review Response')
    for i,n in enumerate(w['nodes']):n['position']=[i%6*270,i//6*220]
    if any(x['id']==w['id'] for x in out):out=[w if x['id']==w['id'] else x for x in out]
    else:
        index=next((i for i,x in enumerate(out) if x['id']=='snakeExpiryRemindersV1'),len(out))
        out.insert(index,w)
    reminder=(ROOT/'n8n/expiry-reminders/policy.js').read_text(encoding='utf-8').strip()
    pattern=r"// Shared n8n expiry policy[\s\S]*?if\(typeof module!=='undefined'\)module.exports=\{planReminders,reminderValid\};"
    for workflow in out:
        for n in workflow['nodes']:
            body=n.get('parameters',{}).get('jsCode')
            if body and '// Shared n8n expiry policy' in body:n['parameters']['jsCode']=re.sub(pattern,lambda m:reminder,body)
    spec=importlib.util.spec_from_file_location('review_poster_overlay',ROOT/'n8n/review-posters/patch.py')
    posters=importlib.util.module_from_spec(spec);spec.loader.exec_module(posters)
    out=posters.build(out)
    spec=importlib.util.spec_from_file_location('review_comment_recovery',ROOT/'n8n/review-comment-recovery/patch.py')
    recovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(recovery)
    return recovery.build(out)
