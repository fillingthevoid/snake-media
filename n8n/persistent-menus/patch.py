"""Refresh only owned navigation lifetime and maintenance policy."""
import copy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CHANGED_IDS=('snakeMyRequestsV1','snakeChoiceCompactionV1')


def replace_policy(code,path,marker):
    if code.count(marker)!=1:raise ValueError('Unknown embedded policy boundary')
    return path.read_text(encoding='utf-8').rstrip()+'\n'+code.split(marker)[1].lstrip('\n')


def build(source):
    rows=copy.deepcopy(source);by={w['id']:w for w in rows}
    marker="if(typeof module!=='undefined')module.exports={MY_ACTION,create,advance,card};"
    for n in by['snakeMyRequestsV1']['nodes']:
        p=n['parameters'];body=p.get('jsCode','')
        if marker in body:p['jsCode']=replace_policy(body,ROOT/'n8n/my-requests/policy.js',marker)
        if n['name']=='Claim Request Selection':
            p['columns']['value']['expiresAt']='={{ $json.record.expiresAt }}'
            if not any(s['id']=='expiresAt' for s in p['columns']['schema']):
                p['columns']['schema'].append({'id':'expiresAt','displayName':'expiresAt','type':'date','display':True,'required':False,'defaultMatch':False,'canBeUsedToMatch':True})
        if n['name']=='Plan Request Selection':p['jsCode']=p['jsCode'].replace('This menu expired, was already selected or belongs to another account.','This menu was closed, already selected or belongs to another account.')
    marker="if(typeof module!=='undefined')module.exports={completionMarkers,pendingBatches,retireChoice};"
    for n in by['snakeChoiceCompactionV1']['nodes']:
        p=n['parameters'];body=p.get('jsCode','')
        if marker in body:p['jsCode']=replace_policy(body,ROOT/'n8n/maintenance/policy.js',marker)
    return rows


if __name__=='__main__':
    import sys
    Path(sys.argv[2]).write_text(json.dumps(build(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))),ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
