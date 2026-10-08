"""Five-minute interactive choice windows; media retention policy is unchanged."""
import copy, importlib.util, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('timeout_helpers',ROOT/'n8n/persistent-menus/patch.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
CHANGED_IDS=('snakeMyRequestsV1','snakeRecommendV1','snakePreviewMediaV1','snakeConfirmMediaV1',
 'snakeRetentionChangePreviewV1','snakeNoticeRetentionPreviewV1','snakeTelegramCardV1',
 'snakeTelegramControlsRetryV1','0e67KTcphqxEKNsh','snakeChoiceCompactionV1')

def node(w,name):return next(n for n in w['nodes'] if n['name']==name)
def edge(name):return {'node':name,'type':'main','index':0}
def expiry_column(n,expression):
 c=n['parameters']['columns'];c['value']['expiresAt']=expression
 if not any(s['id']=='expiresAt' for s in c['schema']):c['schema'].append({'id':'expiresAt','displayName':'expiresAt','type':'date','display':True,'required':False,'defaultMatch':False,'canBeUsedToMatch':True})

def build(source):
 rows=copy.deepcopy(source);by={w['id']:w for w in rows}
 policies={'snakeMyRequestsV1':('my-requests',"if(typeof module!=='undefined')module.exports={MY_ACTION,create,advance,card};"),
 'snakeRecommendV1':('recommendations',"if(typeof module!=='undefined')module.exports={GENRES,RECACTION,history,actorValid,record,transition,completed,card,generation,suggestions,verified,availability,librarySearchTitle};"),
 'snakeNoticeRetentionPreviewV1':('notification-buttons',"if(typeof module!=='undefined')module.exports={noticeActor};"),
 'snakeChoiceCompactionV1':('maintenance',"if(typeof module!=='undefined')module.exports={completionMarkers,pendingBatches,retireChoice};")}
 for wid,(folder,marker) in policies.items():
  # Use each policy's actual export boundary, keeping native wrapper code.
  policy=ROOT/f'n8n/{folder}/policy.js'
  marker=next(s for s in policy.read_text(encoding='utf-8').splitlines() if s.startswith("if(typeof module!=='undefined')module.exports="))
  for n in by[wid]['nodes']:
   code=n['parameters'].get('jsCode','')
   if marker in code:n['parameters']['jsCode']=h.replace_policy(code,policy,marker)
 for wid,name in [('snakePreviewMediaV1','Select Preview'),('snakeRetentionChangePreviewV1','Prepare Retention Change')]:
  p=node(by[wid],name)['parameters'];p['jsCode']=p['jsCode'].replace('30*60000','5*60000')
 expiry_column(node(by['snakeConfirmMediaV1'],'Claim Choice'),'={{ new Date(Date.now()+300000).toISOString() }}')
 for name in ['Claim Recommendation Choice','Save Recommendations']:
  expiry_column(node(by['snakeRecommendV1'],name),'={{ $json.record.expiresAt }}')
 expiry_column(node(by['snakeMyRequestsV1'],'Claim Request Selection'),'={{ $json.record.expiresAt }}')
 p=node(by['snakeMyRequestsV1'],'Plan Request Selection')['parameters']
 p['jsCode']=p['jsCode'].replace('This menu was closed, already selected or belongs to another account.','This menu expired, was closed or belongs to another account. Use /status again.')
 # Owned original notices renew only after the native ownership check succeeds.
 w=by['snakeNoticeRetentionPreviewV1']
 if not any(n['name']=='Touch Notice Controls' for n in w['nodes']):
  touch=copy.deepcopy(node(w,'Read Notice Ownership'));touch.update(id='timeout-touch-notice',name='Touch Notice Controls',position=[1480,-160])
  p=touch['parameters'];p['operation']='update';p.pop('returnAll',None)
  p['filters']['conditions']=[{'keyName':'id','condition':'eq','keyValue':"={{ Number($('Notice Action').first().json.pendingId) }}"},
   {'keyName':'state','condition':'eq','keyValue':'delivered'},
   {'keyName':'source','condition':'eq','keyValue':'={{ $json.source }}'},
   {'keyName':'destinationId','condition':'eq','keyValue':'={{ $json.destinationId }}'}]
  p['columns']={'mappingMode':'defineBelow','value':{'state':'delivered'},'schema':[{'id':'state','displayName':'state','type':'string','display':True,'required':False,'defaultMatch':False,'canBeUsedToMatch':True}]}
  restore={'id':'timeout-restore-notice','name':'Restore Timed Notice Actor','type':'n8n-nodes-base.code','typeVersion':2,'position':[1740,-160],
   'parameters':{'jsCode':"const a=$('Resolve Notice Owner').first().json,id=String($('Notice Action').first().json.pendingId);return [{json:String($json.id)===id?a:{version:1,status:'notice',text:'This notice is not ready or has timed out. Use /extend or /keep.'}}];"}}
  gate=copy.deepcopy(node(w,'Notice Owned?'));gate.update(id='timeout-notice-touched',name='Notice Timer Renewed?',position=[2000,-160])
  w['nodes'].extend([touch,restore,gate]);w['connections']['Notice Owned?']['main'][0]=[edge(touch['name'])]
  w['connections'][touch['name']]={'main':[[edge(restore['name'])]]}
  w['connections'][restore['name']]={'main':[[edge(gate['name'])]]}
  w['connections'][gate['name']]={'main':[[edge('Preview Notice Retention')],[edge('Notice Result')]]}
 # Preserve-parent feedback must enter the transport node so it can renew that card.
 gate=node(by['0e67KTcphqxEKNsh'],'Owned Text Card Cleanup?')['parameters']['conditions']['conditions'][0]
 gate['leftValue']=gate['leftValue'].replace(' && $json.preserveOriginalControls!==true','')
 w=by['0e67KTcphqxEKNsh']
 if not any(n['name']=='Touch Authorized Help Menu' for n in w['nodes']):
  touch=copy.deepcopy(node(w,'Clear Telegram Text Controls'));touch.update(id='timeout-touch-help',name='Touch Authorized Help Menu',position=[650,-160])
  touch['parameters']['operation']='touchMenu';touch['parameters']['message']="={{ $('On message').first().json.callback_query?.message || {} }}"
  touch['parameters']['callbackData']="={{ $('On message').first().json.callback_query?.data || '' }}"
  w['nodes'].append(touch);w['connections']['Authorized User?']['main'][0]=[edge(touch['name'])]
  w['connections'][touch['name']]={'main':[[edge('Confirmation Callback?')]]}
 w=by['snakeTelegramCardV1']
 if not any(n['name']=='Remember Shared Menu' for n in w['nodes']):
  remember=copy.deepcopy(node(w,'Remember Interactive Telegram Card'));remember.update(id='timeout-remember-shared-menu',name='Remember Shared Menu',position=[2080,0])
  w['nodes'].append(remember);w['connections']['Send Shared Menu']={'main':[[edge(remember['name'])]]}
 w=by['snakeTelegramControlsRetryV1'];schedule=next(n for n in w['nodes'] if n['type'].endswith('.scheduleTrigger'))
 old=schedule['name'];schedule['name']='Every Thirty Seconds';schedule['parameters']['rule']['interval']=[{'field':'seconds','secondsInterval':30}]
 if old!=schedule['name']:w['connections'][schedule['name']]=w['connections'].pop(old)
 return rows

if __name__=='__main__':
 import sys
 Path(sys.argv[2]).write_text(json.dumps(build(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))),ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
