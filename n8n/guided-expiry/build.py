"""Targeted overlay on a fresh private export; preserve credentials and routes."""
import copy
import json
import sys
from pathlib import Path

ROOT=Path(__file__).parent
MARKER="if(typeof module!=='undefined')module.exports={parseChange,prepareChange,planChange,changeCard};"


def build(source):
    rows={w['id']:copy.deepcopy(w) for w in source}
    policy=(ROOT.parent/'retention-controls/policy.js').read_text(encoding='utf-8-sig')
    def get(w,name):return next(n for n in w['nodes'] if n['name']==name)
    def replace_policy(w,name):
        node=get(w,name);old=node['parameters']['jsCode']
        if old.count(MARKER)!=1:raise ValueError('Unknown retention policy generation: '+name)
        node['parameters']['jsCode']=policy+'\n'+old.split(MARKER)[1]
        return node
    preview=rows['snakeRetentionChangePreviewV1']
    node=replace_policy(preview,'Prepare Retention Change')
    old=node['parameters']['jsCode']
    expected="const c=result.change;"
    if old.count(expected)!=1:raise ValueError('Unknown preview preparation')
    node['parameters']['jsCode']=old.replace(expected,"const c=result.change||{};")\
        .replace('retentionChange:c','...(result.guide?{retentionGuide:result.guide}:{retentionChange:c})')\
        .replace('mediaType:c.mediaType','mediaType:c.mediaType||\'movie\'')\
        .replace('title:c.title','title:c.title||\'Your requests\'')
    replace_policy(preview,'Render Change Preview')
    confirm=rows['snakeConfirmMediaV1']
    node=replace_policy(confirm,'Render Choice')
    old=node['parameters']['jsCode']
    expected="JSON.parse($json.contextJson||'{}').retentionChange"
    if old.count(expected)!=1:raise ValueError('Unknown change renderer')
    node['parameters']['jsCode']=old.replace(expected,"(JSON.parse($json.contextJson||'{}').retentionChange||JSON.parse($json.contextJson||'{}').retentionGuide)")
    node=get(confirm,'Validate Action');old=node['parameters']['jsCode']
    expected="const state=transition("
    if old.count(expected)!=1:raise ValueError('Unknown action validator')
    # Guidance updates stay preview-only. Existing media/amendment paths remain.
    node['parameters']['jsCode']=policy+'\n'+old.replace(expected,
        "if(JSON.parse(row.contextJson||'{}').retentionGuide){const next=guideAction(row,a,Date.now());return [{json:{row:{...row,contextJson:next.contextJson},state:next.state,choice:next.choice,claimId:String($execution.id)}}];}const state=transition(")
    columns=get(confirm,'Claim Choice')['parameters']['columns']
    columns['value']['contextJson']='={{ $json.row.contextJson }}'
    columns['schema'].append({'id':'contextJson','displayName':'contextJson','type':'string','display':True,'required':False,'defaultMatch':False,'canBeUsedToMatch':True})
    for wid in ['HXtTzVTrpNZMZVt3','0e67KTcphqxEKNsh']:
        replace_policy(rows[wid],'Parse Retention Command')
    telegram=get(rows['0e67KTcphqxEKNsh'],'Prepare Request')
    telegram['parameters']['jsCode']=telegram['parameters']['jsCode'].replace(
        '/extend <title> 7 days — extend an existing request.',
        '/extend or /keep — choose one of your requested titles using buttons.\\n/extend <title> 7 days — extend an existing request.')
    result=[preview,confirm,rows['HXtTzVTrpNZMZVt3'],rows['0e67KTcphqxEKNsh']]
    for w in result:
        for key in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived']:w.pop(key,None)
        w.update(active=False,pinData={})
    return result


if __name__=='__main__':
    source=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
    for w in build(source):
        p=out/(w['id']+'.json');p.write_text(json.dumps(w,indent=2),encoding='utf-8');p.chmod(0o600)
    print('Built four targeted guided-expiry overlays')
