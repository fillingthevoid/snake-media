"""Unify ready direct Discord status and My requests title cards."""
import copy,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(name,file):
    s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
cards=load('direct_status_cards','n8n/my-requests-simplification/patch.py')
h=load('direct_status_helpers','n8n/recommendations/patch.py')
CARD_IDS={'0e67KTcphqxEKNsh','HXtTzVTrpNZMZVt3','snakeMyRequestsV1','snakeStatusV1','snakeStatusInspectV1'}
def build(source):
    patched=cards.build(source);rows=[copy.deepcopy(new if old['id'] in CARD_IDS else old) for old,new in zip(source,patched)];by={w['id']:w for w in rows}
    discord=by['HXtTzVTrpNZMZVt3'];prep=next(n for n in discord['nodes'] if n['name']=='Prepare Status Actor')['parameters']
    if 'destinationId' not in prep['jsCode']:
        anchor='query:p.statusQuery';assert prep['jsCode'].count(anchor)==1,'Unknown direct status actor'
        prep['jsCode']=prep['jsCode'].replace(anchor,anchor+',destinationId:String(p.channelId),messageId:p.messageId,requestedAt:p.requestedAt')
    browser=cards.policy('my-requests/policy.js')
    policy=(ROOT/'n8n/status-review/policy.js').read_text(encoding='utf-8').replace("require('../my-requests/policy.js')",'{create,card}')
    def code(name,body):return h.node(name,'code',{'jsCode':browser+'\n'+policy+'\n'+body})
    status=by['snakeStatusV1'];nodes={n['name']:n for n in status['nodes']}
    context=code('Status Review Context',"return [{json:directStatusContext($('Status Input').first().json,$('Inspect Status Groups').all().map(x=>x.json),$json)}];")
    if 'Status Review Context' not in nodes:
        if status['connections'].get('Format Status Result'):raise ValueError('Unknown status response route')
        status['nodes'] += [context,h.condition('Ready Discord Status Card?',"$json.valid===true"),h.call('Create Direct Status Card','snakeStatusReviewCardV1'),h.node('Keep Plain Status','code',{'jsCode':'return [{json:$json.status}];'})]
    else:nodes['Status Review Context']['parameters']=context['parameters']
    h.connect(status,'Format Status Result','Status Review Context');h.connect(status,'Status Review Context','Ready Discord Status Card?')
    h.connect(status,'Ready Discord Status Card?','Create Direct Status Card');h.connect(status,'Ready Discord Status Card?','Keep Plain Status',1)
    store=copy.deepcopy(next(n for n in by['snakeMyRequestsV1']['nodes'] if n['name']=='Store Request Menu'));store.update(id='direct-status-store',name='Store Direct Status Menu')
    w={'id':'snakeStatusReviewCardV1','name':'Snake Media - Direct Status Title Card','active':False,'pinData':{},'settings':{'executionOrder':'v1','executionTimeout':30},'nodes':[
        h.node('Status Review Card Input','executeWorkflowTrigger',{'inputSource':'passthrough'},typeVersion=1.1),store,
        code('Render Direct Status Card',"return [{json:card($json,Date.now(),$('Status Review Card Input').first().json.status)}];")],'connections':{}}
    h.connect(w,'Status Review Card Input','Store Direct Status Menu');h.connect(w,'Store Direct Status Menu','Render Direct Status Card')
    rows=[old for old in rows if old['id']!=w['id']]
    index=next((i for i,old in enumerate(rows) if old['id']=='snakeExpiryRemindersV1'),len(rows))
    rows.insert(index,w)
    for i,n in enumerate(w['nodes']):n['position']=[i*280,0]
    return rows
