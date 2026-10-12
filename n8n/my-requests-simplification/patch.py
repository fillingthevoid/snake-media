"""Scoped card simplification overlay preserving runtime bindings and write paths."""
import copy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
POLICIES=['my-requests/policy.js','retention-controls/policy.js','status/policy.js']
def policy(file):
    text=(ROOT/'n8n'/file).read_text(encoding='utf-8').rstrip()
    if "require('../request-usability/evidence.js')" in text:
        evidence=(ROOT/'n8n/request-usability/evidence.js').read_text(encoding='utf-8').split("if(typeof module!=='undefined')module.exports=")[0]
        text=text.replace("require('../request-usability/evidence.js')",'(()=>{'+evidence+'\nreturn {scopedFiles,category,expiryPreview};})()')
    return text
def build(source):
    rows=copy.deepcopy(source)
    for w in rows:
        for n in w['nodes']:
            p=n.get('parameters',{});code=p.get('jsCode','')
            for file in POLICIES:
                text=policy(file);header=text.splitlines()[0]
                if header not in code:continue
                start=code.index(header);mark=code.index("\nif(typeof module!=='undefined')module.exports=",start)
                end=code.index(';',mark)+1
                code=code[:start]+text+code[end:]
            if code:p['jsCode']=code
            if n['name']=='My Requests Callback?':
                cond=p['conditions']['conditions'][0]
                cond['leftValue']=cond['leftValue'].replace('|refresh|extend|keep|back|close|watch)', '|refresh|details|summary|extend|extend_(?:7|30)|keep|back|close|watch)')
            if w['id']=='snakeStatusInspectV1' and n['name']=='Describe Status':
                code=p['jsCode']
                if 'const projection=describe(' not in code:
                    if 'let result=describe(' not in code or 'now:Date.now()});if(details.length)' not in code:raise ValueError('Unknown status projection')
                    code=code.replace('let result=describe(', 'const projection=describe(',1).replace('now:Date.now()});if(details.length)', 'now:Date.now()},true);let result=projection.text;if(details.length)',1)
                    code=code.replace('text:result,progressState:', 'text:result,summaryText:projection.summaryText,retentionActions:projection.retentionActions,progressState:',1)
                p['jsCode']=code
            if w['id']=='snakeStatusV1' and n['name']=='Format Status Result':
                code=p['jsCode']
                if 'retentionActions:single.retentionActions' not in code:
                    if 'posterUrl:single.posterUrl' not in code:raise ValueError('Unknown status result')
                    code=code.replace('posterUrl:single.posterUrl', "summaryText:($('Recovery Status Warning').first().json.warning||'')+(single.summaryText||text),retentionActions:single.retentionActions,posterUrl:single.posterUrl",1)
                p['jsCode']=code
    return rows
if __name__=='__main__':
    import sys
    source=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'));rows=build(source)
    changed=[w for w,old in zip(rows,source) if w!=old]
    for w in changed:
        for k in ['createdAt','updatedAt','versionId','activeVersionId','versionCounter','shared','triggerCount','meta','isArchived']:w.pop(k,None)
        w.update(active=False,pinData={})
    p=Path(sys.argv[2]);p.write_text(json.dumps(changed,indent=2),encoding='utf-8');p.chmod(0o600)
    print('Scoped card updates:',len(changed))
