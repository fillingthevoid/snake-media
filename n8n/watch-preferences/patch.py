"""Apply account Watch settings at reply and notification delivery boundaries."""
import copy,importlib.util,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('watch_helpers',ROOT/'n8n/recommendations/patch.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
POLICY=(Path(__file__).parent/'policy.js').read_text(encoding='utf-8')
CHANGED_IDS=('snakeWatchPreferenceV1','HXtTzVTrpNZMZVt3','0e67KTcphqxEKNsh','snakeTelegramNoticeSendV1','snakeNotificationQueueV1')


def code(name,body):return h.node(name,'code',{'jsCode':POLICY+'\n'+body})


def build(source):
    rows=copy.deepcopy(source);by={w['id']:w for w in rows}
    if 'snakeWatchPreferenceV1' in by:return rows
    pending=next(n for n in by['snakeRecommendV1']['nodes'] if n['name']=='Store Recommendation Menu')['parameters']['dataTableId']['value']
    w={'id':'snakeWatchPreferenceV1','name':'Snake Media - Watch Preference','active':False,'nodes':[
      h.node('Watch Preference Input','executeWorkflowTrigger',{'inputSource':'passthrough'},typeVersion=1.1),
      h.table('Read Watch Setting',pending,filters=[h.eq('source','={{ $json.source }}'),h.eq('userId','={{ $json.userId }}'),h.eq('state','settings')]),
      code('Apply Watch Setting',"const a=$('Watch Preference Input').first().json,result=apply(a.result,$input.all().map(x=>x.json),a);return [{json:a.notice?{...a.notice,payload:result}:result}];")],
      'connections':{},'settings':{'executionOrder':'v1','executionTimeout':30}}
    w['nodes'][1]['parameters'].update(limit=1,orderBy=True,orderByColumn='id',orderByDirection='DESC');w['nodes'][1]['onError']='continueRegularOutput'
    h.connect(w,'Watch Preference Input','Read Watch Setting');h.connect(w,'Read Watch Setting','Apply Watch Setting');rows.append(w)
    for wid,source in [('HXtTzVTrpNZMZVt3','discord'),('0e67KTcphqxEKNsh','telegram')]:
        platform=by[wid];prep='Validate Discord Request' if source=='discord' else 'Prepare Request'
        platform['nodes'] += [code('Prepare Watch Reply',"const p=$('"+prep+"').first().json;return [{json:{source:'"+source+"',userId:String(p.userId),result:$json}}];"),
          h.call('Apply Reply Watch Preference','snakeWatchPreferenceV1'),
          code('Restore Preferred Reply',"return [{json:$json.version===1?$json:$('Prepare Watch Reply').first().json.result}];")]
        if source=='discord':
            h.connect(platform,'Present Media Feedback','Prepare Watch Reply');h.connect(platform,'Restore Preferred Reply','Respond to Discord')
        else:
            for outputs in platform['connections'].values():
                for branches in outputs.values():
                    for branch in branches:
                        for edge in branch:
                            if edge['node']=='Format Interactive Reply':edge['node']='Prepare Watch Reply'
            h.connect(platform,'Restore Preferred Reply','Format Interactive Reply')
        h.connect(platform,'Prepare Watch Reply','Apply Reply Watch Preference');h.connect(platform,'Apply Reply Watch Preference','Restore Preferred Reply')
    # Keep the canonical metadata name so existing photo/text fallback expressions
    # and dual-link conditions see the preferred URLs.
    delivery=by['snakeTelegramNoticeSendV1']
    raw=next(n for n in delivery['nodes'] if n['name']=='Completion Card Metadata');raw['name']='Raw Completion Card Metadata'
    old=delivery['connections'].pop('Completion Card Metadata');h.connect(delivery,'Prepare Completion Text','Raw Completion Card Metadata')
    delivery['nodes'] += [code('Prepare Notice Watch Preference',"const p=JSON.parse($json.payloadJson);return [{json:{source:'telegram',userId:p.userId,result:$json}}];"),h.call('Apply Notice Watch Preference','snakeWatchPreferenceV1'),
      code('Completion Card Metadata',"return [{json:$json.payloadJson?$json:$('Raw Completion Card Metadata').first().json}];")]
    h.connect(delivery,'Raw Completion Card Metadata','Prepare Notice Watch Preference');h.connect(delivery,'Prepare Notice Watch Preference','Apply Notice Watch Preference');h.connect(delivery,'Apply Notice Watch Preference','Completion Card Metadata');delivery['connections']['Completion Card Metadata']=old
    queue=by['snakeNotificationQueueV1']
    queue['nodes'] += [h.condition('Queue Has Watch Items?','$json.notifications.length>0'),
      code('Prepare Queue Watch Preferences',"return $json.notifications.map(notice=>({json:{source:'discord',userId:notice.payload.userId,result:notice.payload,notice}}));"),
      h.call('Apply Queue Watch Preferences','snakeWatchPreferenceV1'),code('Collect Preferred Queue',"return [{json:{version:1,notifications:$input.all().map(x=>x.json)}}];")]
    next(n for n in queue['nodes'] if n['name']=='Apply Queue Watch Preferences')['parameters']['mode']='each'
    h.connect(queue,'Queue Batch','Queue Has Watch Items?');h.connect(queue,'Queue Has Watch Items?','Prepare Queue Watch Preferences');h.connect(queue,'Queue Has Watch Items?','Queue Response',1)
    h.connect(queue,'Prepare Queue Watch Preferences','Apply Queue Watch Preferences');h.connect(queue,'Apply Queue Watch Preferences','Collect Preferred Queue');h.connect(queue,'Collect Preferred Queue','Queue Response')
    return rows


if __name__=='__main__':
    import sys
    Path(sys.argv[2]).write_text(json.dumps(build(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))),indent=2)+'\n',encoding='utf-8')
