"""Patch only preview/action decisions in a current private export."""
import copy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).parent


def build(source):
    rows={w['id']:copy.deepcopy(w) for w in source}
    preview=rows['snakePreviewMediaV1'];action=rows['snakeConfirmMediaV1']
    def get(w,name):return next(n for n in w['nodes'] if n['name']==name)
    policy=(ROOT/'policy.js').read_text(encoding='utf-8-sig')
    for w,name in [(preview,'Render Preview'),(action,'Render Choice')]:
        n=get(w,name);old=n['parameters']['jsCode'];marker='const r=$json;'
        if old.count(marker)!=1:raise ValueError('Unknown renderer')
        n['parameters']['jsCode']=old.split(marker)[0]+policy+'\nreturn [{json:card($json)}];'
    n=get(preview,'Select Preview');old=n['parameters']['jsCode']
    if old.count("state:'preview'")!=1:raise ValueError('Unknown preview state')
    n['parameters']['jsCode']=old.replace("state:'preview'","state:i.mediaType==='tv'?'scope':'preview'")
    n=get(action,'Validate Action');old=n['parameters']['jsCode'];marker='const row=$input.first().json'
    if old.count(marker)!=1 or old.count('choice:a.action')!=1:raise ValueError('Unknown action contract')
    n['parameters']['jsCode']=policy+'\n'+marker+old.split(marker)[1].replace('choice:a.action','choice:selectedChoice(row,a,state)')
    for w in [preview,action]:
        for k in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived']:w.pop(k,None)
        w.update(active=False,pinData={})
    return [preview,action]


if __name__=='__main__':
    output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True)
    for w in build(json.loads(Path(sys.argv[1]).read_text())):
        p=output/(w['id']+'.json');p.write_text(json.dumps(w,indent=2));p.chmod(0o600)
    print('Built targeted preview and action overlays')
