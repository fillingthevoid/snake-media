"""Restore confirmations only after explicit coordinator busy (no work started)."""
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).parent
helpers=(ROOT.parent/'status/build.py').read_text(encoding='utf-8-sig').split('status=wf(')[0]
helpers=helpers.replace("P=(R/'policy.js').read_text(encoding='utf-8-sig')", "P=''")
exec(compile(helpers,str(ROOT.parent/'status/build.py'),'exec'),globals())
OUT=ROOT/'workflows';OUT.mkdir(exist_ok=True)
if len(sys.argv)==1:
 for p in (ROOT.parent/'retention-controls/workflows').glob('*.json'):
  w=json.loads(p.read_text(encoding='utf-8-sig'));S[w['id']]=w
w=copy.deepcopy(S['snakeConfirmMediaV1'])
assert not any(n['name']=='Backend Busy?' for n in w['nodes'])
restore=copy.deepcopy(get(w,'Claim Choice'));restore.update(name='Restore Busy Choice',id=node('Restore Busy Choice','code',{})['id'])
restore['parameters']['filters']['conditions']=[
 {'keyName':'id','condition':'eq','keyValue':"={{ $('Validate Action').first().json.row.id }}"},
 {'keyName':'state','condition':'eq','keyValue':'processing'},
 {'keyName':'claimId','condition':'eq','keyValue':'={{ String($execution.id) }}'}]
restore['parameters']['columns']['value']={k:"={{ $('Validate Action').first().json.row."+k+" }}" for k in ['state','claimId','choice']}
restore['alwaysOutputData']=True
restore.pop('onError',None)
w['nodes'] += [iff('Backend Busy?',"$json.busy===true"),restore,
 code('Busy Retry Reply',"const old=$('Validate Action').first().json.row;const r=$json;if(r.id!==old.id||r.state!==old.state||r.claimId!==old.claimId||r.choice!==old.choice)throw Error('Busy confirmation restore failed');return [{json:{version:1,status:'notice',busy:true,actionAccepted:false,text:'Snake Media is processing another request. Your selection is still available—please click the same button again in a moment.'}}];")]
for name in ['Commit Confirmed Media','Apply Retention Choice']:edge(w,name,'Backend Busy?')
chain(w,'Backend Busy?','Restore Busy Choice','Busy Retry Reply')
edge(w,'Backend Busy?','Mark Accepted Action',1)
n=get(w,'Mark Accepted Action');old=n['parameters']['jsCode']
assert 'accepted=valid&&' in old
n['parameters']['jsCode']=old.replace('accepted=valid&&','accepted=$json.busy!==true&&valid&&')
save(w)
print('Generated guarded busy-retry confirmation overlay')
