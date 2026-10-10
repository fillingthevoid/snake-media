"""Apply multi-season picker and subscription support without changing bindings."""
import copy, importlib.util, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('usability',ROOT/'n8n/request-usability/patch.py')
usability=importlib.util.module_from_spec(spec);spec.loader.exec_module(usability)

def build(source):
    rows=copy.deepcopy(source)
    maintained={w['id'] for w in json.loads((ROOT/'config-templates/n8n-current-media-workflows.json').read_text(encoding='utf-8'))}
    marker="if(typeof module!=='undefined')module.exports={transition,selectedChoice,card,revise};"
    old=" else if(/^season_[1-9][0-9]{0,3}$/.test(choice))selectedSeasons=[Number(choice.slice(7))];"
    # Replace only the subscription choice branch, preserving later retention overlays.
    policy=(ROOT/'n8n/retention/policy.js').read_text(encoding='utf-8')
    branch=policy.split(old)[1].split("\n else throw new Error('Invalid subscription choice');")[0]
    for w in rows:
        if w['id'] not in maintained:continue
        for n in w['nodes']:
            p=n.get('parameters',{});body=p.get('jsCode','')
            if marker in body:
                body=usability.embed(body,'function validChoice(row,choice)',[marker],usability.policy('n8n/request-simplification/policy.js'))
            if old in body and "else if(/^seasons_" not in body:body=body.replace(old,old+branch)
            if body:p['jsCode']=body
            if w['id']=='snakeTelegramCardV1' and n['name']=='Recommendation Card?':
                c=p['conditions']['conditions'][0]
                c['leftValue']=c['leftValue'].replace('retback$|retdays_', 'retback$|review$|season_|page_|retdays_')
    return rows

if __name__=='__main__':
    import sys
    Path(sys.argv[2]).write_text(json.dumps(build(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))),ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
