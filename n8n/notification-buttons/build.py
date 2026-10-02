"""Overlay download notice controls on a fresh export of the current workflows."""
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).parent
exec(compile((ROOT.parent/'status/build.py').read_text(encoding='utf-8-sig').split('status=wf(')[0],str(ROOT.parent/'status/build.py'),'exec'),globals())
OUT=ROOT/'workflows';OUT.mkdir(exist_ok=True)
if len(sys.argv)==1:
 for p in (ROOT.parent/'retention-controls/workflows').glob('*.json'):
  w=json.loads(p.read_text(encoding='utf-8-sig'));S[w['id']]=w
P=(ROOT/'policy.js').read_text(encoding='utf-8-sig')
RP=(ROOT.parent/'retention-controls/policy.js').read_text(encoding='utf-8-sig')
preview=copy.deepcopy(S['snakeRetentionChangePreviewV1'])
n=get(preview,'Prepare Retention Change');old=n['parameters']['jsCode']
tail=old[old.index("\nconst a=$('Change Input')"):]
n['parameters']['jsCode']=RP+tail;save(preview)
notice=wf('snakeNoticeRetentionPreviewV1','Snake Media - Preview Download Retention',[
 trigger('Notice Action'),data('Read Notice Ownership','snake_media_notifications'),
 code('One Notice Request Read','return [{json:{}}];'),data('Read Notice Requests','snake_media_requests'),
 code('Resolve Notice Owner',P+"\nreturn [{json:noticeActor($('Notice Action').first().json,$('Read Notice Ownership').all().map(x=>x.json),$input.all().map(x=>x.json),String($execution.id))}];"),
 iff('Notice Owned?',"!!$json.requestKey"),call('Preview Notice Retention','snakeRetentionChangePreviewV1'),
 code('Notice Result','return [{json:$json}];')])
get(notice,'Read Notice Ownership')['parameters']['filters']['conditions']=[{'keyName':'id','condition':'eq','keyValue':"={{ Number($('Notice Action').first().json.pendingId) }}"}]
get(notice,'Preview Notice Retention').pop('onError',None)
chain(notice,*[n['name'] for n in notice['nodes']]);edge(notice,'Notice Owned?','Notice Result',1);save(notice)
for wid,output in [('HXtTzVTrpNZMZVt3','Respond to Discord'),('0e67KTcphqxEKNsh','Format Interactive Reply')]:
 w=copy.deepcopy(S[wid]);assert not any(n['name']=='Download Retention Button?' for n in w['nodes'])
 w['nodes'] += [iff('Download Retention Button?',"['notice_7','notice_30','notice_keep'].includes($json.action)"),call('Preview Download Retention',notice['id'])]
 get(w,'Preview Download Retention').pop('onError',None)
 chain(w,'Prepare Confirmation Action','Download Retention Button?','Preview Download Retention',output)
 edge(w,'Download Retention Button?','Resolve Confirmation',1);save(w)
queue=copy.deepcopy(S['snakeNotificationQueueV1']);n=get(queue,'Queue Batch')
old=n['parameters']['jsCode'];needle='notificationKey:r.notificationKey,destinationId:r.destinationId'
assert needle in old;n['parameters']['jsCode']=old.replace(needle,'id:String(r.id),'+needle);save(queue)
sender=copy.deepcopy(S['snakeTelegramNoticeSendV1']);n=get(sender,'Send Telegram Completion')
n['parameters'].update(replyMarkup='inlineKeyboard',inlineKeyboard="={{ {rows:[{row:{buttons:[{text:'Extend 7 days',additionalFields:{callback_data:'snake:'+$json.id+':notice_7'}},{text:'Extend 30 days',additionalFields:{callback_data:'snake:'+$json.id+':notice_30'}}]}},{row:{buttons:[{text:'Keep permanently',additionalFields:{callback_data:'snake:'+$json.id+':notice_keep'}}]}}]} }}")
save(sender)
print('Generated six notification button workflows')
