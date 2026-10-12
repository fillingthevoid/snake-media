"""Replace only the shared expiry-notice authorization policy."""
import copy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def build(source):
    out=copy.deepcopy(source)
    header='// Resolve notification controls from stored ownership, never from a client title.'
    marker="if(typeof module!=='undefined')module.exports={noticeActor};"
    policy=(ROOT/'n8n/notification-buttons/policy.js').read_text(encoding='utf-8').rstrip()
    count=0
    for w in out:
        for n in w['nodes']:
            code=n.get('parameters',{}).get('jsCode','')
            if header in code:
                start=code.index(header);end=code.index(marker,start)+len(marker)
                n['parameters']['jsCode']=code[:start]+policy+code[end:];count+=1
    if count!=1:raise ValueError('Expected exactly one shared notice policy')
    return out
if __name__=='__main__':
    import sys
    source=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'));out=build(source)
    changed=[w for w,old in zip(out,source) if w!=old]
    for w in changed:
        for k in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived']:w.pop(k,None)
        w.update(active=False,pinData={})
    p=Path(sys.argv[2]);p.write_text(json.dumps(changed,indent=2),encoding='utf-8');p.chmod(0o600)
    print('Scoped expiry policy updates:',len(changed))
